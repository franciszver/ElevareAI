"""
Subject Model
"""

import uuid

from sqlalchemy import ARRAY, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from src.models.base import Base


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    category = Column(String(50), index=True)  # Math, Science, Test Prep
    description = Column(Text)
    related_subjects = Column(ARRAY(UUID(as_uuid=True)))  # Array of related subject IDs
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self):
        return f"<Subject(id={self.id}, name={self.name}, category={self.category})>"
