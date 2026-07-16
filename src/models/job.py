"""
Job Models
For tracking async background jobs (e.g., practice generation)
"""

import enum
import uuid

from sqlalchemy import JSON, Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.base import Base, TimestampMixin


class JobStatus(str, enum.Enum):
    """Job status enumeration"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(Base, TimestampMixin):
    """Background job tracking"""

    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type = Column(
        String(50), nullable=False, index=True
    )  # e.g., "practice_generation"
    status = Column(
        String(20), default=JobStatus.PENDING.value, nullable=False, index=True
    )

    # Job context
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Job parameters (stored as JSON)
    parameters = Column(JSON, nullable=False)  # Input parameters for the job

    # Job results
    result = Column(JSON, nullable=True)  # Output/result data
    error_message = Column(Text, nullable=True)  # Error message if failed

    # Progress tracking
    progress_percent = Column(Integer, default=0)  # 0-100
    progress_message = Column(String(255), nullable=True)

    # Webhook callback
    webhook_url = Column(
        String(500), nullable=True
    )  # Optional webhook URL for completion notification

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="jobs")
    student = relationship("User", foreign_keys=[student_id])

    def __repr__(self):
        return f"<Job(id={self.id}, type={self.job_type}, status={self.status.value})>"
