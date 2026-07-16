"""
Messaging Schemas
Request/response models for messaging endpoints
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CreateThreadRequest(BaseModel):
    """Request to create a new message thread"""

    tutor_id: str = Field(..., description="Tutor user ID")
    student_id: str = Field(..., description="Student user ID")
    subject: str = Field(..., description="Thread subject")
    triggered_by_type: Optional[str] = Field(
        None,
        description="What triggered this thread (flagged_practice, override, qa_escalation, manual)",
    )
    triggered_by_id: Optional[str] = Field(
        None, description="ID of item that triggered the thread"
    )
    initial_message: Optional[str] = Field(None, description="Optional initial message")


class SendMessageRequest(BaseModel):
    """Request to send a message in a thread"""

    content: str = Field(..., description="Message content")
    message_type: str = Field(default="text", description="Message type (text, system)")


class MessageResponse(BaseModel):
    """Message response"""

    message_id: str
    thread_id: str
    sender_id: str
    sender_role: str
    content: str
    message_type: str
    created_at: str
    read_at: Optional[str] = None


class ThreadResponse(BaseModel):
    """Thread response"""

    thread_id: str
    tutor_id: str
    student_id: str
    subject: str
    status: str
    triggered_by_type: Optional[str] = None
    triggered_by_id: Optional[str] = None
    message_count: int
    unread_count: int
    last_message_at: Optional[str] = None
    created_at: str
    messages: List[MessageResponse] = []


class ThreadListResponse(BaseModel):
    """List of threads"""

    threads: List[ThreadResponse]
    total: int
