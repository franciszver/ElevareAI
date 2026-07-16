#!/usr/bin/env python3
"""
Demo Data Seeding Script
Seeds the database with realistic demo data for the AI Study Companion.

Idempotent: running this script multiple times against the same database
will not create duplicate rows. All entities use deterministic UUIDs
(uuid5 derived from a natural key) and are inserted only if missing.

Usage:
    python scripts/seed_demo_data.py
"""

import logging
import random
import subprocess
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.database import SessionLocal, engine  # noqa: E402
from src.models import (  # noqa: E402
    Goal,
    Nudge,
    Override,
    PracticeBankItem,
    QAInteraction,
)
from src.models import Session as TutoringSession  # noqa: E402
from src.models import Subject, Summary, User  # noqa: E402
from src.services.auth import hash_password  # noqa: E402
from src.config.settings import settings  # noqa: E402
from scripts.demo_auth import DEMO_PASSWORD  # noqa: E402

# Silence verbose SQL echo (enabled globally in development) for this script's output
engine.echo = False
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)

# Reproducible "random" demo data across runs
random.seed(42)

# Deterministic IDs are derived via uuid5(NAMESPACE_DNS, natural_key)
NAMESPACE = uuid.NAMESPACE_DNS

DEMO_ACCOUNTS = [
    {"email": "demo@elevare.ai", "role": "student", "name": "Demo Student"},
    {"email": "tutor@elevare.ai", "role": "tutor", "name": "Demo Tutor"},
    {"email": "parent@elevare.ai", "role": "parent", "name": "Demo Parent"},
]

# ============================================================================
# Sample Data Templates
# ============================================================================

SUBJECTS = [
    {"name": "Algebra", "category": "Math"},
    {"name": "Geometry", "category": "Math"},
    {"name": "Calculus", "category": "Math"},
    {"name": "Chemistry", "category": "Science"},
    {"name": "Physics", "category": "Science"},
    {"name": "Biology", "category": "Science"},
    {"name": "SAT Math", "category": "Test Prep"},
    {"name": "SAT English", "category": "Test Prep"},
    {"name": "AP Calculus", "category": "Test Prep"},
    {"name": "AP Chemistry", "category": "Test Prep"},
]

STUDENT_NAMES = [
    "Alex Johnson",
    "Sam Chen",
    "Jordan Martinez",
    "Taylor Williams",
    "Casey Brown",
    "Morgan Davis",
    "Riley Wilson",
    "Quinn Anderson",
    "Avery Thompson",
    "Cameron Lee",
]

TUTOR_NAMES = [
    "Dr. Sarah Mitchell",
    "Prof. James Rodriguez",
    "Ms. Emily Chen",
    "Dr. Michael Park",
    "Ms. Lisa Thompson",
]

TRANSCRIPTS = {
    "normal_algebra": """
    Tutor: "Today we're working on quadratic equations. Can you solve x² + 5x + 6 = 0?"
    Student: "I think I factor it... (x + 2)(x + 3) = 0, so x = -2 or x = -3?"
    Tutor: "Perfect! You've got it. Now let's try a harder one: 2x² - 7x + 3 = 0"
    Student: "Hmm, I need to factor this... (2x - 1)(x - 3) = 0?"
    Tutor: "Excellent work! You're really getting the hang of factoring. For homework, try problems 1-10 in chapter 5."
    """,
    "mixed_subjects": """
    Tutor: "Let's start with factoring polynomials. Can you factor x² + 5x + 6?"
    Student: "That would be (x + 2)(x + 3)."
    Tutor: "Great! Now let's switch to chemistry. How do you balance H₂ + O₂ → H₂O?"
    Student: "2H₂ + O₂ → 2H₂O"
    Tutor: "Perfect! We'll continue with both topics next time."
    """,
    "short_session": """
    Tutor: "We only have 5 minutes today. Let's quickly review your homework."
    Student: "I finished problems 1-5, but I'm stuck on problem 6."
    Tutor: "Let's tackle that next time. Great work today!"
    """,
    "chemistry_advanced": """
    Tutor: "Today we're diving into orbital hybridization. Can you explain sp³ hybridization?"
    Student: "I think it's when one s orbital and three p orbitals combine to form four sp³ orbitals?"
    Tutor: "Exactly! And what shape does this create?"
    Student: "Tetrahedral?"
    Tutor: "Perfect! You've mastered this concept. Let's move on to sp² hybridization next time."
    """,
    "calculus_intro": """
    Tutor: "We're starting derivatives today. What's the derivative of x²?"
    Student: "2x?"
    Tutor: "Correct! And what about 3x³?"
    Student: "9x²?"
    Tutor: "Excellent! You're picking this up quickly. Practice the power rule for homework."
    """,
}

PRACTICE_QUESTIONS = {
    "algebra": [
        {
            "question": "Factor the quadratic: x² + 7x + 12",
            "answer": "(x + 3)(x + 4)",
            "explanation": "Find two numbers that multiply to 12 and add to 7: 3 and 4.",
            "difficulty": 3,
        },
        {
            "question": "Solve for x: 2x² - 8x + 6 = 0",
            "answer": "x = 1 or x = 3",
            "explanation": "Factor to get 2(x - 1)(x - 3) = 0, so x = 1 or x = 3.",
            "difficulty": 5,
        },
        {
            "question": "Simplify: (x + 3)(x - 5)",
            "answer": "x² - 2x - 15",
            "explanation": "Use FOIL: x² - 5x + 3x - 15 = x² - 2x - 15",
            "difficulty": 2,
        },
    ],
    "chemistry": [
        {
            "question": "Balance the equation: CH₄ + O₂ → CO₂ + H₂O",
            "answer": "CH₄ + 2O₂ → CO₂ + 2H₂O",
            "explanation": "Balance atoms: 1 C, 4 H, 4 O on each side.",
            "difficulty": 4,
        },
        {
            "question": "What is the molecular formula for water?",
            "answer": "H₂O",
            "explanation": "Water consists of 2 hydrogen atoms and 1 oxygen atom.",
            "difficulty": 1,
        },
    ],
    "calculus": [
        {
            "question": "Find the derivative of f(x) = 3x² + 5x - 2",
            "answer": "f'(x) = 6x + 5",
            "explanation": "Apply power rule: d/dx(3x²) = 6x, d/dx(5x) = 5, d/dx(-2) = 0",
            "difficulty": 4,
        }
    ],
}

QA_QUERIES = [
    {
        "query": "I don't understand factoring quadratics",
        "expected_confidence": "Medium",
        "context": "algebra",
    },
    {
        "query": "Explain photosynthesis",
        "expected_confidence": "High",
        "context": "biology",
    },
    {
        "query": "Can you explain the Schrödinger equation in detail?",
        "expected_confidence": "Low",
        "context": "physics",
    },
    {
        "query": "What's the weather tomorrow?",
        "expected_confidence": "N/A",
        "context": "out_of_scope",
    },
    {"query": "I don't get this", "expected_confidence": "Low", "context": "ambiguous"},
]


# ============================================================================
# Idempotency helpers
# ============================================================================


def deterministic_id(*parts: str) -> uuid.UUID:
    """Derive a stable UUID from a natural key so re-runs match existing rows."""
    return uuid.uuid5(NAMESPACE, ":".join(parts))


def get_or_create(db, model, id_: uuid.UUID, **fields) -> tuple[Any, bool]:
    """Fetch a row by primary key, or insert it if missing. Returns (obj, created)."""
    obj = db.get(model, id_)
    if obj is not None:
        return obj, False
    obj = model(id=id_, **fields)
    db.add(obj)
    db.flush()
    return obj, True


def get_or_create_user(db, email: str, role: str, **fields) -> tuple[User, bool]:
    user = db.query(User).filter(User.email == email).first()
    if user is not None:
        return user, False
    user = User(
        id=deterministic_id("user", email),
        cognito_sub=str(uuid.uuid5(NAMESPACE, email)),
        email=email,
        role=role,
        **fields,
    )
    db.add(user)
    db.flush()
    return user, True


def get_or_create_subject(
    db, name: str, category: str, description: str
) -> tuple[Subject, bool]:
    subject = db.query(Subject).filter(Subject.name == name).first()
    if subject is not None:
        return subject, False
    subject = Subject(
        id=deterministic_id("subject", name),
        name=name,
        category=category,
        description=description,
    )
    db.add(subject)
    db.flush()
    return subject, True


def infer_subject_name(transcript_key: str, transcript_text: str, fallback: str) -> str:
    """Guess a session's subject from its transcript, for seeding purposes."""
    text = transcript_text.lower()
    if "algebra" in transcript_key or "quadratic" in text:
        return "Algebra"
    if "chemistry" in transcript_key or "chemical" in text:
        return "Chemistry"
    if "calculus" in transcript_key:
        return "Calculus"
    return fallback


def build_qa_fields(qa: Dict[str, str]) -> Dict[str, Any]:
    """Map a QA_QUERIES entry to QAInteraction field values.

    DB check constraint only allows High/Medium/Low; out-of-scope queries
    ("N/A") are represented via the out_of_scope flag instead.
    """
    confidence = (
        "Low" if qa["expected_confidence"] == "N/A" else qa["expected_confidence"]
    )
    return {
        "query": qa["query"],
        "answer": f"Sample answer for: {qa['query']}",
        "confidence": confidence,
        "confidence_score": (
            random.uniform(0.5, 0.95) if qa["expected_confidence"] != "N/A" else None
        ),
        "context_subjects": (
            [qa["context"]] if qa["context"] != "out_of_scope" else []
        ),
        "clarification_requested": qa["context"] == "ambiguous",
        "out_of_scope": qa["context"] == "out_of_scope",
        "tutor_escalation_suggested": qa["expected_confidence"] == "Low",
        "disclaimer_shown": True,
    }


# ============================================================================
# Migrations
# ============================================================================


def run_migrations() -> None:
    """Apply DB migrations so a virgin database is ready to seed."""
    print("Running migrations...")
    setup_script = Path(__file__).parent / "setup_db.py"
    subprocess.run(
        [sys.executable, str(setup_script)],
        cwd=str(Path(__file__).parent.parent),
        check=True,
    )


# ============================================================================
# Seed Functions
# ============================================================================


def seed_headline_accounts(db) -> Dict[str, User]:
    """Create the 3 known-credential demo accounts used for live demos."""
    if not settings.demo_password:
        raise SystemExit(
            "DEMO_PASSWORD not set — add it to .env (see README)"
        )
    accounts = {}
    for account in DEMO_ACCOUNTS:
        user, created = get_or_create_user(
            db,
            email=account["email"],
            role=account["role"],
            password_hash=hash_password(DEMO_PASSWORD),
            profile={"name": account["name"]},
            gamification={},
            analytics={},
            disclaimer_shown=True,
        )
        if created:
            print(
                f"  + Created headline account: {account['email']} ({account['role']})"
            )
        accounts[account["role"]] = user

    # Link the demo parent to the demo student for a coherent demo narrative
    parent = accounts["parent"]
    student = accounts["student"]
    student_id_str = str(student.id)
    if parent.profile.get("student_id") != student_id_str:
        profile = dict(parent.profile or {})
        profile["student_id"] = student_id_str
        parent.profile = profile

    return accounts


def seed_subjects(db) -> List[Subject]:
    subjects = []
    for subj in SUBJECTS:
        subject, _ = get_or_create_subject(
            db,
            name=subj["name"],
            category=subj["category"],
            description=f"Study materials for {subj['name']}",
        )
        subjects.append(subject)
    return subjects


def seed_students(db, subjects: List[Subject]) -> List[User]:
    students = []
    for i, name in enumerate(STUDENT_NAMES):
        first_name = name.split()[0]
        email = f"{first_name.lower()}.student@example.com"

        if i < 3:
            progress_data = [
                {"subject": "Algebra", "completion": 85, "streak": 7, "xp": 1200},
                {"subject": "Chemistry", "completion": 70, "streak": 5, "xp": 900},
            ]
        elif i < 7:
            progress_data = [
                {"subject": "Geometry", "completion": 50, "streak": 3, "xp": 600},
                {"subject": "Biology", "completion": 40, "streak": 2, "xp": 400},
            ]
        else:
            progress_data = [
                {"subject": "Calculus", "completion": 20, "streak": 1, "xp": 150},
            ]

        student, _ = get_or_create_user(
            db,
            email=email,
            role="student",
            profile={
                "goals": [],
                "subjects": [s.name for s in random.sample(subjects, 2)],
                "preferences": {
                    "learning_style": random.choice(["visual", "textual", "mixed"]),
                    "nudge_frequency_cap": 1,
                },
                "progress": {"multi_goal_tracking": progress_data},
            },
            gamification={
                "xp": sum(p["xp"] for p in progress_data),
                "level": random.randint(1, 10),
                "badges": [],
                "streaks": max(p["streak"] for p in progress_data)
                if progress_data
                else 0,
                "meta_rewards": [],
            },
            analytics={
                "override_count": 0,
                "confidence_distribution": {
                    "High": "60%",
                    "Medium": "30%",
                    "Low": "10%",
                },
                "nudge_engagement": {"opened": "70%", "clicked": "50%"},
            },
            disclaimer_shown=i < 5,
        )
        students.append(student)
    return students


def seed_tutors(db, subjects: List[Subject]) -> List[User]:
    tutors = []
    for name in TUTOR_NAMES:
        first_name = (
            name.replace("Dr.", "")
            .replace("Prof.", "")
            .replace("Ms.", "")
            .strip()
            .split()[0]
        )
        email = f"{first_name.lower()}.tutor@example.com"

        tutor, _ = get_or_create_user(
            db,
            email=email,
            role="tutor",
            profile={
                "specializations": random.sample([s.name for s in subjects], 2),
                "years_experience": random.randint(3, 15),
            },
        )
        tutors.append(tutor)
    return tutors


def seed_admin(db) -> User:
    admin, _ = get_or_create_user(
        db, email="admin@example.com", role="admin", profile={}
    )
    return admin


def seed_demo_goals(db, student: User, subjects: List[Subject]) -> List[Goal]:
    """Give the headline demo student (demo@elevare.ai) a demo-worthy set of
    goals: a mix of active (partial progress) and completed, across subjects."""
    subject_by_name = {s.name: s for s in subjects}

    goal_specs = [
        {
            "goal_type": "General",
            "subject_name": "Algebra",
            "completion": 65,
            "status": "active",
            "streak": 6,
        },
        {
            "goal_type": "AP",
            "subject_name": "AP Chemistry",
            "completion": 35,
            "status": "active",
            "streak": 3,
        },
        {
            "goal_type": "SAT",
            "subject_name": "SAT Math",
            "completion": 100,
            "status": "completed",
            "streak": 0,
            "completed_days_ago": 8,
        },
        {
            "goal_type": "General",
            "subject_name": "Calculus",
            "completion": 100,
            "status": "completed",
            "streak": 0,
            "completed_days_ago": 18,
        },
    ]

    goals = []
    for i, spec in enumerate(goal_specs):
        subject = subject_by_name.get(spec["subject_name"])
        goal, _ = get_or_create(
            db,
            Goal,
            deterministic_id("goal", student.email, str(i)),
            student_id=student.id,
            created_by=student.id,
            subject_id=subject.id if subject else None,
            goal_type=spec["goal_type"],
            title=f"{spec['goal_type']} {spec['subject_name']}",
            description=f"Master {spec['subject_name']} for {spec['goal_type']} preparation",
            target_completion_date=(datetime.now() + timedelta(days=90)).date(),
            status=spec["status"],
            completion_percentage=spec["completion"],
            current_streak=spec["streak"],
            xp_earned=spec["completion"] * 10,
            completed_at=(
                datetime.now() - timedelta(days=spec.get("completed_days_ago", 0))
                if spec["status"] == "completed"
                else None
            ),
        )
        goals.append(goal)

    return goals


def seed_demo_sessions(
    db, student: User, tutor: User, subjects: List[Subject]
) -> List[TutoringSession]:
    """Give the headline demo student 7 sessions spread across the past 3 weeks,
    tutored by tutor@elevare.ai."""
    sessions = []
    transcript_keys = list(TRANSCRIPTS.keys())

    for i in range(7):
        session_date = datetime.now() - timedelta(days=1 + i * 3)
        transcript_key = transcript_keys[i % len(transcript_keys)]
        transcript_text = TRANSCRIPTS[transcript_key]
        subject_name = infer_subject_name(transcript_key, transcript_text, "Algebra")

        subject = next((s for s in subjects if s.name == subject_name), subjects[0])

        session, _ = get_or_create(
            db,
            TutoringSession,
            deterministic_id("session", student.email, str(i)),
            student_id=student.id,
            tutor_id=tutor.id,
            session_date=session_date,
            duration_minutes=45 + (i % 3) * 15,
            subject_id=subject.id,
            transcript_text=transcript_text.strip(),
            transcript_storage_url=None,
            transcript_available=True,
            topics_covered=[subject_name],
            notes=f"Session {i+1} notes",
        )
        sessions.append(session)

    return sessions


def seed_demo_qa_interactions(db, student: User) -> List[QAInteraction]:
    """Give the headline demo student a Q&A history with varied confidence
    levels, spread over the past few weeks."""
    interactions = []

    for i in range(9):
        qa = QA_QUERIES[i % len(QA_QUERIES)]
        created_at = datetime.now() - timedelta(days=1 + i * 2)

        interaction, _ = get_or_create(
            db,
            QAInteraction,
            deterministic_id("qa", student.email, str(i)),
            student_id=student.id,
            created_at=created_at,
            **build_qa_fields(qa),
        )
        interactions.append(interaction)

    return interactions


def seed_goals(db, students: List[User]) -> List[Goal]:
    goals = []
    goal_types = ["SAT", "AP", "General"]
    subject_choices = ["Algebra", "Chemistry", "Calculus", "SAT Math", "AP Chemistry"]

    for student in students:
        num_goals = random.randint(1, 3)
        subjects_used: List[str] = []

        for i in range(num_goals):
            goal_type = random.choice(goal_types)
            subject_name = random.choice(subject_choices)

            # Avoid duplicate subjects per student; if the draw collides,
            # deterministically fall back to the next unused subject so
            # num_goals is still honored.
            if subject_name in subjects_used:
                subject_name = next(
                    (s for s in subject_choices if s not in subjects_used),
                    subject_name,
                )
            subjects_used.append(subject_name)

            completion = random.randint(20, 95) if random.random() > 0.2 else 100
            status = "completed" if completion == 100 else "active"

            goal, _ = get_or_create(
                db,
                Goal,
                deterministic_id("goal", student.email, str(i)),
                student_id=student.id,
                created_by=student.id,
                goal_type=goal_type,
                title=f"{goal_type} {subject_name}",
                description=f"Master {subject_name} for {goal_type} preparation",
                target_completion_date=(
                    datetime.now() + timedelta(days=random.randint(30, 180))
                ).date(),
                status=status,
                completion_percentage=completion,
                current_streak=random.randint(1, 10) if status == "active" else 0,
                xp_earned=completion * 10,
                completed_at=datetime.now() - timedelta(days=random.randint(1, 7))
                if status == "completed"
                else None,
            )
            goals.append(goal)

    return goals


def seed_sessions(
    db, students: List[User], tutors: List[User], subjects: List[Subject]
) -> List[TutoringSession]:
    sessions = []
    transcript_keys = list(TRANSCRIPTS.keys())

    for student in students[:8]:
        num_sessions = random.randint(2, 5)
        tutor = random.choice(tutors)

        for i in range(num_sessions):
            session_date = datetime.now() - timedelta(days=random.randint(1, 30))
            transcript_key = random.choice(transcript_keys)
            transcript_text = TRANSCRIPTS[transcript_key]
            subject_name = infer_subject_name(
                transcript_key,
                transcript_text,
                random.choice(["Algebra", "Chemistry", "Geometry"]),
            )

            subject = next((s for s in subjects if s.name == subject_name), subjects[0])

            session, _ = get_or_create(
                db,
                TutoringSession,
                deterministic_id("session", student.email, str(i)),
                student_id=student.id,
                tutor_id=tutor.id,
                session_date=session_date,
                duration_minutes=random.randint(30, 90),
                subject_id=subject.id,
                transcript_text=transcript_text.strip(),
                transcript_storage_url=None,
                transcript_available=True,
                topics_covered=[subject_name],
                notes=f"Session {i+1} notes",
            )
            sessions.append(session)

    return sessions


def seed_summaries(db, sessions: List[TutoringSession]) -> List[Summary]:
    summaries = []

    for session in sessions:
        transcript = (session.transcript_text or "").lower()

        if "brief" in transcript or "5 minutes" in transcript:
            narrative = "Session was brief. We only had 5 minutes today. Quick review of homework progress."
            next_steps = [
                "Review last practice before next session",
                "Attempt problem 6 and note specific questions",
            ]
            summary_type = "brief"
        elif "algebra" in transcript and "chemistry" in transcript:
            narrative = "We reviewed factoring polynomials, then pivoted to balancing chemical equations. Strong understanding demonstrated in both areas."
            next_steps = [
                "Practice factoring polynomials: x² - 9, x² + 7x + 12",
                "Review balancing equations: CH₄ + O₂ → CO₂ + 2H₂O",
            ]
            summary_type = "normal"
        else:
            topic = session.topics_covered[0] if session.topics_covered else "the topic"
            narrative = f"Great session covering {topic}. Student showed strong grasp of concepts and completed practice problems successfully."
            next_steps = [
                f"Continue practicing {topic} problems",
                "Review key concepts before next session",
            ]
            summary_type = "normal"

        summary, _ = get_or_create(
            db,
            Summary,
            deterministic_id("summary", str(session.id)),
            session_id=session.id,
            student_id=session.student_id,
            tutor_id=session.tutor_id,
            narrative=narrative,
            next_steps=next_steps,
            subjects_covered=session.topics_covered,
            summary_type=summary_type,
            overridden=False,
        )
        summaries.append(summary)

    return summaries


def seed_practice_bank_items(db, subjects: List[Subject]) -> List[PracticeBankItem]:
    bank_items = []

    for subject in subjects:
        subject_name = subject.name.lower()

        questions = []
        if "algebra" in subject_name or "math" in subject_name:
            questions = PRACTICE_QUESTIONS.get("algebra", [])
        elif "chemistry" in subject_name:
            questions = PRACTICE_QUESTIONS.get("chemistry", [])
        elif "calculus" in subject_name:
            questions = PRACTICE_QUESTIONS.get("calculus", [])

        for q in questions:
            item, _ = get_or_create(
                db,
                PracticeBankItem,
                deterministic_id("practice", subject.name, q["question"]),
                question_text=q["question"],
                answer_text=q["answer"],
                explanation=q["explanation"],
                subject_id=subject.id,
                difficulty_level=q["difficulty"],
                goal_tags=["SAT", "AP"]
                if "SAT" in subject.name or "AP" in subject.name
                else ["General"],
                topic_tags=[subject.name.lower()],
                created_by=None,
                version=1,
                is_active=True,
            )
            bank_items.append(item)

    return bank_items


def seed_qa_interactions(db, students: List[User]) -> List[QAInteraction]:
    interactions = []

    for student in students[:6]:
        num_interactions = random.randint(2, 5)

        for i in range(num_interactions):
            qa = random.choice(QA_QUERIES)

            interaction, _ = get_or_create(
                db,
                QAInteraction,
                deterministic_id("qa", student.email, str(i)),
                student_id=student.id,
                **build_qa_fields(qa),
            )
            interactions.append(interaction)

    return interactions


def seed_nudges(db, students: List[User]) -> List[Nudge]:
    nudges = []
    nudge_types = ["inactivity", "cross_subject", "login"]

    for student in students[:5]:
        nudge_type = random.choice(nudge_types)

        if nudge_type == "inactivity":
            message = "Hi! We noticed you haven't been active recently. Regular practice is key to success!"
        elif nudge_type == "cross_subject":
            message = "Congratulations on your progress! Based on your success, you might enjoy exploring Physics or Biology."
        else:
            message = "Welcome back! Ready to continue your learning journey?"

        sent_at = datetime.now() - timedelta(days=random.randint(1, 7))
        opened = random.random() > 0.3

        nudge, _ = get_or_create(
            db,
            Nudge,
            deterministic_id("nudge", student.email),
            user_id=student.id,
            type=nudge_type,
            channel=random.choice(["in_app", "email", "both"]),
            message=message,
            personalized=True,
            sent_at=sent_at,
            opened_at=(sent_at + timedelta(hours=random.randint(1, 24)))
            if opened
            else None,
            clicked_at=(sent_at + timedelta(hours=random.randint(2, 48)))
            if opened and random.random() > 0.3
            else None,
            trigger_reason=f"{nudge_type} trigger",
            suggestions_made=["Physics", "Biology"]
            if nudge_type == "cross_subject"
            else [],
        )
        nudges.append(nudge)

    return nudges


def seed_overrides(db, tutors: List[User], summaries: List[Summary]) -> List[Override]:
    overrides = []

    for tutor in tutors[:3]:
        num_overrides = random.randint(1, 2)

        for i in range(num_overrides):
            if not summaries:
                break
            summary = random.choice(summaries)

            override, _ = get_or_create(
                db,
                Override,
                deterministic_id("override", tutor.email, str(i)),
                tutor_id=tutor.id,
                student_id=summary.student_id,
                override_type="summary",
                action="Modified next steps",
                summary_id=summary.id,
                original_content={"next_steps": summary.next_steps},
                new_content={
                    "next_steps": [
                        "Focus on chapter 5 exercises only",
                        "Skip practice problems, review theory instead",
                    ]
                },
                reason="AI suggestions too advanced for current level",
            )
            overrides.append(override)

    return overrides


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    print("=" * 60)
    print("AI Study Companion - Demo Data Seeder")
    print("=" * 60)
    print()

    run_migrations()
    print()

    print("Seeding demo data...")
    db = SessionLocal()
    try:
        accounts = seed_headline_accounts(db)

        subjects = seed_subjects(db)
        print(f"  Subjects: {len(subjects)}")

        demo_student = accounts["student"]
        demo_tutor = accounts["tutor"]
        demo_goals = seed_demo_goals(db, demo_student, subjects)
        demo_sessions = seed_demo_sessions(db, demo_student, demo_tutor, subjects)
        demo_summaries = seed_summaries(db, demo_sessions)
        demo_qa_interactions = seed_demo_qa_interactions(db, demo_student)
        print(
            f"  Demo account (demo@elevare.ai): goals={len(demo_goals)}, "
            f"sessions={len(demo_sessions)}, summaries={len(demo_summaries)}, "
            f"qa_interactions={len(demo_qa_interactions)}"
        )

        students = seed_students(db, subjects)
        tutors = seed_tutors(db, subjects)
        admin = seed_admin(db)
        print(f"  Students: {len(students)}, Tutors: {len(tutors)}, Admins: 1")

        goals = seed_goals(db, students)
        print(f"  Goals: {len(goals)}")

        sessions = seed_sessions(db, students, tutors, subjects)
        print(f"  Sessions: {len(sessions)}")

        summaries = seed_summaries(db, sessions)
        print(f"  Summaries: {len(summaries)}")

        practice_items = seed_practice_bank_items(db, subjects)
        print(f"  Practice bank items: {len(practice_items)}")

        qa_interactions = seed_qa_interactions(db, students)
        print(f"  Q&A interactions: {len(qa_interactions)}")

        nudges = seed_nudges(db, students)
        print(f"  Nudges: {len(nudges)}")

        overrides = seed_overrides(db, tutors, summaries)
        print(f"  Overrides: {len(overrides)}")

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print()
    print("=" * 60)
    print("[SUCCESS] Demo data seeding complete!")
    print("=" * 60)
    print()
    print("Demo login credentials:")
    for account in DEMO_ACCOUNTS:
        print(f"  {account['role']:<8} {account['email']:<20} {DEMO_PASSWORD}")
    print()


if __name__ == "__main__":
    main()
