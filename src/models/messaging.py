"""
Messaging Models
Message threads between tutors and students
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.models.base import Base, TimestampMixin


class MessageThread(Base, TimestampMixin):
    """Thread of messages between tutor and student"""

    __tablename__ = "message_threads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tutor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Thread metadata
    subject = Column(String(200), nullable=False)
    status = Column(String(20), default="open", index=True)  # open, closed, archived

    # Context - what triggered this thread
    triggered_by_type = Column(
        String(50)
    )  # "flagged_practice", "override", "qa_escalation", "manual"
    triggered_by_id = Column(
        UUID(as_uuid=True), nullable=True
    )  # ID of the item that triggered it

    # Tracking
    last_message_at = Column(DateTime(timezone=True), nullable=True, index=True)
    message_count = Column(Integer, default=0)
    unread_count_tutor = Column(Integer, default=0)
    unread_count_student = Column(Integer, default=0)

    # Relationships
    tutor = relationship(
        "User", foreign_keys=[tutor_id], backref="message_threads_as_tutor"
    )
    student = relationship(
        "User", foreign_keys=[student_id], backref="message_threads_as_student"
    )
    messages = relationship(
        "Message",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    def __repr__(self):
        return f"<MessageThread(id={self.id}, tutor={self.tutor_id}, student={self.student_id}, status={self.status})>"


class Message(Base, TimestampMixin):
    """Individual message in a thread"""

    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(
        UUID(as_uuid=True),
        ForeignKey("message_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Message content
    content = Column(Text, nullable=False)
    message_type = Column(String(20), default="text")  # text, system, attachment

    # Tracking
    read_at = Column(DateTime(timezone=True), nullable=True)
    read_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships
    thread = relationship("MessageThread", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id], backref="sent_messages")
    reader = relationship("User", foreign_keys=[read_by])

    def __repr__(self):
        return (
            f"<Message(id={self.id}, thread={self.thread_id}, sender={self.sender_id})>"
        )
