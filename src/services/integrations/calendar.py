"""
Calendar Integration Service
Integration with Google Calendar and Outlook
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class CalendarService:
    """Service for calendar integrations"""

    def __init__(self, db: Session):
        self.db = db

    def sync_google_calendar(
        self,
        access_token: str,
        calendar_id: str = "primary",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict:
        """
        Sync events from Google Calendar

        Args:
            access_token: Google OAuth2 access token
            calendar_id: Calendar ID (default: primary)
            start_date: Start date for events
            end_date: End date for events

        Returns:
            Dict with synced events
        """
        import requests

        if not start_date:
            start_date = datetime.utcnow()
        if not end_date:
            end_date = start_date + timedelta(days=30)

        url = "https://www.googleapis.com/calendar/v3/calendars/{}/events".format(
            calendar_id
        )

        params = {
            "timeMin": start_date.isoformat() + "Z",
            "timeMax": end_date.isoformat() + "Z",
            "singleEvents": "true",
            "orderBy": "startTime",
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            events = data.get("items", [])

            return {
                "success": True,
                "events": events,
                "count": len(events),
                "synced_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Google Calendar API error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "synced_at": datetime.utcnow().isoformat(),
            }

    def create_google_calendar_event(
        self,
        access_token: str,
        calendar_id: str,
        summary: str,
        start_time: datetime,
        end_time: datetime,
        description: Optional[str] = None,
        location: Optional[str] = None,
    ) -> Dict:
        """
        Create event in Google Calendar

        Args:
            access_token: Google OAuth2 access token
            calendar_id: Calendar ID
            summary: Event title
            start_time: Event start time
            end_time: Event end time
            description: Event description
            location: Event location

        Returns:
            Created event data
        """
        import requests

        url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        event_data = {
            "summary": summary,
            "start": {"dateTime": start_time.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end_time.isoformat(), "timeZone": "UTC"},
        }

        if description:
            event_data["description"] = description
        if location:
            event_data["location"] = location

        try:
            response = requests.post(url, headers=headers, json=event_data, timeout=10)
            response.raise_for_status()
            event = response.json()

            return {
                "success": True,
                "event": event,
                "created_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Google Calendar create event error: {str(e)}")
            return {"success": False, "error": str(e)}

    def sync_outlook_calendar(
        self,
        access_token: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict:
        """
        Sync events from Outlook Calendar

        Args:
            access_token: Microsoft OAuth2 access token
            start_date: Start date for events
            end_date: End date for events

        Returns:
            Dict with synced events
        """
        import requests

        if not start_date:
            start_date = datetime.utcnow()
        if not end_date:
            end_date = start_date + timedelta(days=30)

        url = "https://graph.microsoft.com/v1.0/me/calendar/events"

        params = {
            "$filter": f"start/dateTime ge '{start_date.isoformat()}' and end/dateTime le '{end_date.isoformat()}'",
            "$orderby": "start/dateTime",
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            events = data.get("value", [])

            return {
                "success": True,
                "events": events,
                "count": len(events),
                "synced_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Outlook Calendar API error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "synced_at": datetime.utcnow().isoformat(),
            }

    def create_outlook_calendar_event(
        self,
        access_token: str,
        subject: str,
        start_time: datetime,
        end_time: datetime,
        body: Optional[str] = None,
        location: Optional[str] = None,
    ) -> Dict:
        """
        Create event in Outlook Calendar

        Args:
            access_token: Microsoft OAuth2 access token
            subject: Event title
            start_time: Event start time
            end_time: Event end time
            body: Event description
            location: Event location

        Returns:
            Created event data
        """
        import requests

        url = "https://graph.microsoft.com/v1.0/me/calendar/events"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        event_data = {
            "subject": subject,
            "start": {"dateTime": start_time.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end_time.isoformat(), "timeZone": "UTC"},
        }

        if body:
            event_data["body"] = {"contentType": "HTML", "content": body}
        if location:
            event_data["location"] = {"displayName": location}

        try:
            response = requests.post(url, headers=headers, json=event_data, timeout=10)
            response.raise_for_status()
            event = response.json()

            return {
                "success": True,
                "event": event,
                "created_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Outlook Calendar create event error: {str(e)}")
            return {
                "success": False,
                "error": "An internal error occurred while creating Outlook calendar event.",
            }
