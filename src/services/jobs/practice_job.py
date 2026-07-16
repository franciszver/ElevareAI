"""
Practice Generation Job Service
Handles async practice generation in background
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.job import Job, JobStatus
from src.models.practice import PracticeAssignment, PracticeBankItem
from src.models.subject import Subject
from src.models.user import User
from src.services.integrations.webhooks import WebhookService
from src.services.practice.adaptive import AdaptivePracticeService
from src.services.practice.generator import PracticeGenerator
from src.services.practice.utils import generate_choices_from_answer

logger = logging.getLogger(__name__)


class PracticeJobService:
    """Service for async practice generation jobs"""

    def __init__(self, db: Session):
        self.db = db
        self.generator = PracticeGenerator()
        self.adaptive_service = AdaptivePracticeService(db)
        self.webhook_service = WebhookService(db)

    def _broadcast_progress(self, job_id: UUID, progress: int, message: str):
        """Helper to broadcast progress updates via WebSocket"""
        try:
            import asyncio

            from src.api.handlers.jobs import broadcast_job_update

            asyncio.create_task(
                broadcast_job_update(
                    job_id,
                    {
                        "type": "status",
                        "status": "processing",
                        "progress_percent": progress,
                        "progress_message": message,
                    },
                )
            )
        except:
            pass  # WebSocket not critical

    def create_job(
        self,
        student_id: str,
        subject: str,
        topic: Optional[str] = None,
        num_items: int = 5,
        goal_tags: Optional[list[str]] = None,
        webhook_url: Optional[str] = None,
    ) -> Job:
        """
        Create a practice generation job

        Returns:
            Created job with PENDING status
        """
        job = Job(
            job_type="practice_generation",
            status=JobStatus.PENDING.value,
            student_id=UUID(student_id),
            parameters={
                "student_id": student_id,
                "subject": subject,
                "topic": topic,
                "num_items": num_items,
                "goal_tags": goal_tags or [],
            },
            webhook_url=webhook_url,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        logger.info(
            f"Created practice generation job {job.id} for student {student_id}"
        )
        return job

    def process_job(self, job_id: UUID) -> Dict:
        """
        Process a practice generation job

        This runs in the background and updates the job status
        """
        job = self.db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return {"success": False, "error": "Job not found"}

        try:
            # Update status to processing
            job.status = JobStatus.PROCESSING.value
            job.progress_percent = 0
            job.progress_message = "Starting practice generation..."
            self.db.commit()

            # Broadcast status update
            try:
                import asyncio

                from src.api.handlers.jobs import broadcast_job_update

                asyncio.create_task(
                    broadcast_job_update(
                        job.id,
                        {
                            "type": "status",
                            "status": "processing",
                            "progress_percent": 0,
                            "progress_message": "Starting practice generation...",
                        },
                    )
                )
            except:
                pass  # WebSocket not critical

            params = job.parameters
            student_id = params["student_id"]
            subject = params["subject"]
            topic = params.get("topic")
            num_items = params.get("num_items", 5)
            goal_tags = params.get("goal_tags", [])

            # Get subject
            subject_obj = (
                self.db.query(Subject)
                .filter(func.lower(Subject.name) == func.lower(subject))
                .first()
            )

            if not subject_obj:
                raise ValueError(f"Subject '{subject}' not found")

            # Get student
            student = self.db.query(User).filter(User.id == student_id).first()
            if not student:
                raise ValueError("Student not found")

            # Get student rating
            job.progress_percent = 10
            job.progress_message = "Calculating difficulty level..."
            self.db.commit()
            self._broadcast_progress(job.id, 10, "Calculating difficulty level...")

            student_rating = self.adaptive_service.get_student_rating(
                student_id, str(subject_obj.id)
            )
            (
                difficulty_min,
                difficulty_max,
            ) = self.adaptive_service.select_difficulty_range(student_rating)

            # Get previous assignments
            job.progress_percent = 20
            job.progress_message = "Checking previous assignments..."
            self.db.commit()
            self._broadcast_progress(job.id, 20, "Checking previous assignments...")

            previous_assignments = (
                self.db.query(
                    PracticeAssignment.bank_item_id, PracticeAssignment.ai_question_text
                )
                .filter(PracticeAssignment.student_id == student_id)
                .all()
            )

            excluded_bank_item_ids = set()
            excluded_question_texts = set()
            bank_item_ids_to_fetch = set()

            for prev_assignment in previous_assignments:
                if prev_assignment.bank_item_id:
                    excluded_bank_item_ids.add(prev_assignment.bank_item_id)
                    bank_item_ids_to_fetch.add(prev_assignment.bank_item_id)
                if prev_assignment.ai_question_text:
                    excluded_question_texts.add(
                        prev_assignment.ai_question_text.strip().lower()
                    )

            if bank_item_ids_to_fetch:
                bank_items_with_texts = (
                    self.db.query(PracticeBankItem.question_text)
                    .filter(
                        PracticeBankItem.id.in_(bank_item_ids_to_fetch),
                        PracticeBankItem.question_text.isnot(None),
                    )
                    .all()
                )
                for bank_item in bank_items_with_texts:
                    if bank_item.question_text:
                        excluded_question_texts.add(
                            bank_item.question_text.strip().lower()
                        )

            # Find bank items
            job.progress_percent = 30
            job.progress_message = "Finding practice questions..."
            self.db.commit()
            self._broadcast_progress(job.id, 30, "Finding practice questions...")

            bank_items = self.adaptive_service.find_bank_items(
                subject_id=str(subject_obj.id),
                difficulty_min=difficulty_min,
                difficulty_max=difficulty_max,
                goal_tags=goal_tags,
                limit=num_items * 3,
            )

            if len(bank_items) == 0:
                # Expand difficulty range
                expanded_min = max(1, difficulty_min - 2)
                expanded_max = min(10, difficulty_max + 2)
                bank_items = self.adaptive_service.find_bank_items(
                    subject_id=str(subject_obj.id),
                    difficulty_min=expanded_min,
                    difficulty_max=expanded_max,
                    goal_tags=None,
                    limit=num_items * 3,
                )

            items = []
            assignment_id = uuid.uuid4()
            used_bank_item_ids = set(excluded_bank_item_ids)
            used_question_texts = set(excluded_question_texts)

            # Use bank items first
            job.progress_percent = 40
            job.progress_message = "Selecting practice questions..."
            self.db.commit()
            self._broadcast_progress(job.id, 40, "Selecting practice questions...")

            for bank_item in bank_items:
                if len(items) >= num_items:
                    break
                if bank_item.id in used_bank_item_ids:
                    continue
                if (
                    bank_item.question_text
                    and bank_item.question_text.strip().lower() in used_question_texts
                ):
                    continue
                if bank_item.id in excluded_bank_item_ids:
                    continue
                if (
                    bank_item.question_text
                    and bank_item.question_text.strip().lower()
                    in excluded_question_texts
                ):
                    continue

                assignment = PracticeAssignment(
                    id=uuid.uuid4(),
                    student_id=UUID(student_id),
                    source="bank",
                    bank_item_id=bank_item.id,
                    subject_id=subject_obj.id,
                    difficulty_level=bank_item.difficulty_level,
                    goal_tags=goal_tags or [],
                    student_rating_before=student_rating,
                    assigned_at=datetime.now(timezone.utc),
                    created_at=datetime.now(timezone.utc),
                )
                self.db.add(assignment)

                used_bank_item_ids.add(bank_item.id)
                if bank_item.question_text:
                    used_question_texts.add(bank_item.question_text.strip().lower())

                choices, correct_answer = generate_choices_from_answer(
                    bank_item.answer_text
                )

                items.append(
                    {
                        "item_id": str(assignment.id),
                        "source": "bank",
                        "question": bank_item.question_text,
                        "answer": bank_item.answer_text,
                        "choices": choices,
                        "correct_answer": correct_answer,
                        "explanation": bank_item.explanation,
                        "difficulty": bank_item.difficulty_level,
                        "subject": subject,
                        "goal_tags": bank_item.goal_tags or [],
                    }
                )

            # Generate AI items if needed
            needed = num_items - len(items)
            if needed > 0:
                job.progress_percent = 50
                job.progress_message = f"Generating {needed} AI practice questions..."
                self.db.commit()
                self._broadcast_progress(
                    job.id, 50, f"Generating {needed} AI practice questions..."
                )

                max_attempts_per_item = 5
                attempts = 0
                items_generated = 0

                while (
                    len(items) < num_items and attempts < needed * max_attempts_per_item
                ):
                    attempts += 1
                    progress = 50 + int((items_generated / needed) * 40)
                    job.progress_percent = progress
                    job.progress_message = (
                        f"Generating AI question {items_generated + 1} of {needed}..."
                    )
                    self.db.commit()

                    ai_item_data = self.generator.generate_practice_item(
                        subject=subject,
                        topic=topic or subject,
                        difficulty_level=(difficulty_min + difficulty_max) // 2,
                        goal_tags=goal_tags,
                    )

                    question_text = (
                        ai_item_data.get("question_text", "").strip().lower()
                    )
                    if (
                        question_text in used_question_texts
                        or question_text in excluded_question_texts
                    ):
                        continue

                    assignment = PracticeAssignment(
                        id=uuid.uuid4(),
                        student_id=UUID(student_id),
                        source="ai_generated",
                        ai_question_text=ai_item_data["question_text"],
                        ai_answer_text=ai_item_data["answer_text"],
                        ai_explanation=ai_item_data["explanation"],
                        flagged=True,
                        subject_id=subject_obj.id,
                        difficulty_level=(difficulty_min + difficulty_max) // 2,
                        goal_tags=goal_tags or [],
                        student_rating_before=student_rating,
                        assigned_at=datetime.now(timezone.utc),
                        created_at=datetime.now(timezone.utc),
                    )
                    self.db.add(assignment)

                    used_question_texts.add(question_text)

                    choices = ai_item_data.get("choices", [])
                    correct_answer = ai_item_data.get("correct_answer", "A")
                    if not choices or len(choices) < 4:
                        choices, correct_answer = generate_choices_from_answer(
                            ai_item_data["answer_text"]
                        )

                    items.append(
                        {
                            "item_id": str(assignment.id),
                            "source": "ai_generated",
                            "flagged": True,
                            "question": ai_item_data["question_text"],
                            "answer": ai_item_data["answer_text"],
                            "choices": choices,
                            "correct_answer": correct_answer,
                            "explanation": ai_item_data["explanation"],
                            "difficulty": (difficulty_min + difficulty_max) // 2,
                            "subject": subject,
                            "goal_tags": goal_tags or [],
                            "requires_tutor_review": True,
                            "note": "AI-generated item - flagged for tutor review",
                        }
                    )

                    items_generated += 1

            # Commit all assignments
            job.progress_percent = 95
            job.progress_message = "Finalizing assignment..."
            self.db.commit()
            self._broadcast_progress(job.id, 95, "Finalizing assignment...")

            # Build result
            result = {
                "success": True,
                "data": {
                    "assignment_id": str(assignment_id),
                    "items": items,
                    "metadata": {
                        "student_rating_before": student_rating,
                        "selected_difficulty_range": f"{difficulty_min}-{difficulty_max}",
                        "bank_items_used": len(
                            [i for i in items if i.get("source") == "bank"]
                        ),
                        "ai_items_generated": len(
                            [i for i in items if i.get("source") == "ai_generated"]
                        ),
                        "all_ai_generated": len(bank_items) == 0,
                    },
                },
            }

            # Update job as completed
            job.status = JobStatus.COMPLETED.value
            job.progress_percent = 100
            job.progress_message = "Practice assignment ready!"
            job.result = result
            self.db.commit()

            # Trigger webhook if provided
            if job.webhook_url:
                try:
                    self.webhook_service.trigger_webhook(
                        event_type="practice.assignment.completed",
                        payload={
                            "job_id": str(job.id),
                            "student_id": student_id,
                            "result": result,
                        },
                        webhook_url=job.webhook_url,
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to trigger webhook for job {job.id}: {str(e)}"
                    )

            # Broadcast to WebSocket connections
            try:
                import asyncio

                from src.api.handlers.jobs import broadcast_job_update

                asyncio.create_task(
                    broadcast_job_update(
                        job.id, {"type": "completed", "result": result}
                    )
                )
            except Exception as e:
                logger.debug(f"WebSocket broadcast not available: {str(e)}")

            logger.info(f"Job {job_id} completed successfully")
            return result

        except Exception as e:
            logger.error(f"Job {job_id} failed: {str(e)}", exc_info=True)
            job.status = JobStatus.FAILED.value
            job.error_message = str(e)
            job.progress_message = f"Error: {str(e)}"
            self.db.commit()

            # Trigger webhook for failure
            if job.webhook_url:
                try:
                    self.webhook_service.trigger_webhook(
                        event_type="practice.assignment.failed",
                        payload={
                            "job_id": str(job.id),
                            "student_id": params.get("student_id"),
                            "error": str(e),
                        },
                        webhook_url=job.webhook_url,
                    )
                except Exception as webhook_error:
                    logger.warning(
                        f"Failed to trigger failure webhook: {str(webhook_error)}"
                    )

            # Broadcast to WebSocket connections
            try:
                import asyncio

                from src.api.handlers.jobs import broadcast_job_update

                asyncio.create_task(
                    broadcast_job_update(job.id, {"type": "failed", "error": str(e)})
                )
            except Exception as e:
                logger.debug(f"WebSocket broadcast not available: {str(e)}")

            return {"success": False, "error": str(e)}
