"""
Integration Schemas
Request/response models for integration endpoints
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


class IntegrationCreateRequest(BaseModel):
    """Request to create an integration"""

    integration_type: str = Field(..., description="Type: lms, calendar, webhook")
    provider: str = Field(
        ...,
        description="Provider: canvas, blackboard, google_calendar, outlook, custom",
    )
    config: Dict = Field(
        ..., description="Integration configuration (API keys, tokens, etc.)"
    )


class IntegrationResponse(BaseModel):
    """Integration response"""

    id: str
    user_id: str
    integration_type: str
    provider: str
    status: str
    last_sync_at: Optional[str]
    created_at: str


class WebhookCreateRequest(BaseModel):
    """Request to create a webhook"""

    url: HttpUrl = Field(..., description="Webhook URL")
    events: List[str] = Field(..., description="List of events to subscribe to")
    secret: Optional[str] = Field(
        None, description="Optional secret for signature verification"
    )


class WebhookResponse(BaseModel):
    """Webhook response"""

    id: str
    url: str
    events: List[str]
    status: str
    last_triggered_at: Optional[str]
    success_count: int
    error_count: int
    created_at: str


class WebhookTriggerRequest(BaseModel):
    """Request to trigger a webhook"""

    event_type: str = Field(..., description="Event type")
    payload: Dict = Field(..., description="Event payload")
    webhook_id: Optional[str] = Field(None, description="Optional specific webhook ID")
    user_id: Optional[str] = Field(None, description="Optional user ID filter")


class NotificationRequest(BaseModel):
    """Request to send notification"""

    user_id: str = Field(..., description="User ID")
    title: str = Field(..., description="Notification title")
    body: str = Field(..., description="Notification body")
    data: Optional[Dict] = Field(None, description="Optional data payload")
    platform: Optional[str] = Field(None, description="Platform: ios, android, web")


class DeviceTokenRequest(BaseModel):
    """Request to register device token"""

    device_token: str = Field(..., description="Device push token")
    platform: str = Field(..., description="Platform: ios, android, web")
    device_info: Optional[Dict] = Field(None, description="Optional device information")
