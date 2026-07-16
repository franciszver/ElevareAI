"""
User Model
"""

import uuid

from sqlalchemy import JSON, Boolean, Column, String
from sqlalchemy.dialects.postgresql import UUID

from src.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cognito_sub = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)
    role = Column(
        String(20), nullable=False, index=True
    )  # student, tutor, parent, admin

    # JSONB columns for flexible schema
    profile = Column(JSON, default={})
    gamification = Column(JSON, default={})
    analytics = Column(JSON, default={})

    disclaimer_shown = Column(Boolean, default=False)

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
