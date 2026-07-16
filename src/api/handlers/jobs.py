"""
Job Status Handler
GET /jobs/{job_id} - Get job status
WebSocket /jobs/{job_id}/ws - Real-time job updates
"""

import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session as DBSession

from src.api.middleware.auth import get_current_user_optional
from src.config.database import get_db
from src.models.job import Job, JobStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])

# Store active WebSocket connections
active_connections: dict[UUID, list[WebSocket]] = {}


@router.get("/{job_id}")
async def get_job_status(
    job_id: UUID,
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Get job status by ID

    Returns:
        Job status, progress, and result (if completed)
    """
    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    response = {
        "job_id": str(job.id),
        "job_type": job.job_type,
        "status": job.status,
        "progress_percent": job.progress_percent,
        "progress_message": job.progress_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }

    if job.status == JobStatus.COMPLETED.value and job.result:
        response["result"] = job.result
    elif job.status == JobStatus.FAILED.value:
        response["error"] = job.error_message

    return {"success": True, "data": response}


@router.websocket("/{job_id}/ws")
async def websocket_job_updates(websocket: WebSocket, job_id: UUID):
    """
    WebSocket endpoint for real-time job updates

    Connects to a job and receives updates as the job progresses.
    Automatically disconnects when job completes or fails.
    """
    await websocket.accept()

    # Add to active connections
    if job_id not in active_connections:
        active_connections[job_id] = []
    active_connections[job_id].append(websocket)

    logger.info(f"WebSocket connected for job {job_id}")

    try:
        # Get initial job state
        from src.config.database import SessionLocal

        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                await websocket.send_json({"type": "error", "message": "Job not found"})
                await websocket.close()
                return

            # Send initial state
            await websocket.send_json(
                {
                    "type": "status",
                    "status": job.status,
                    "progress_percent": job.progress_percent,
                    "progress_message": job.progress_message,
                }
            )

            # If already completed, send result and close
            if job.status == JobStatus.COMPLETED.value:
                await websocket.send_json({"type": "completed", "result": job.result})
                await websocket.close()
                return
            elif job.status == JobStatus.FAILED.value:
                await websocket.send_json(
                    {"type": "failed", "error": job.error_message}
                )
                await websocket.close()
                return

            # Poll for updates
            last_status = job.status
            last_progress = job.progress_percent

            while True:
                await asyncio.sleep(1)  # Poll every second

                # Refresh job from database
                db.refresh(job)

                # Check if status changed
                if job.status != last_status or job.progress_percent != last_progress:
                    await websocket.send_json(
                        {
                            "type": "status",
                            "status": job.status,
                            "progress_percent": job.progress_percent,
                            "progress_message": job.progress_message,
                        }
                    )

                    last_status = job.status
                    last_progress = job.progress_percent

                # Check if completed
                if job.status == JobStatus.COMPLETED.value:
                    await websocket.send_json(
                        {"type": "completed", "result": job.result}
                    )
                    break

                # Check if failed
                if job.status == JobStatus.FAILED.value:
                    await websocket.send_json(
                        {"type": "failed", "error": job.error_message}
                    )
                    break

        finally:
            db.close()

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {str(e)}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        # Remove from active connections
        if job_id in active_connections:
            active_connections[job_id].remove(websocket)
            if not active_connections[job_id]:
                del active_connections[job_id]


async def broadcast_job_update(job_id: UUID, update: dict):
    """
    Broadcast job update to all connected WebSocket clients

    Called by the job service when job status changes
    """
    if job_id not in active_connections:
        return

    disconnected = []
    for websocket in active_connections[job_id]:
        try:
            await websocket.send_json(update)
        except:
            disconnected.append(websocket)

    # Remove disconnected clients
    for ws in disconnected:
        active_connections[job_id].remove(ws)

    if not active_connections[job_id]:
        del active_connections[job_id]
