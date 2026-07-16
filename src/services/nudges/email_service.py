"""
Email Service
Sends nudges via AWS SES
"""

from typing import Optional

import boto3

from src.config.settings import settings


def send_nudge_email(to_email: str, message: str, nudge_id: str) -> bool:
    """
    Send nudge email via AWS SES

    Returns:
        bool: True if sent successfully
    """
    try:
        ses_client = boto3.client("ses", region_name=settings.ses_region)

        # Create email content
        subject = "Your Study Companion - Quick Update"
        body_text = message
        body_html = f"""
        <html>
        <body>
            <p>{message.replace(chr(10), '<br>')}</p>
            <p><small>This is an automated message from your AI Study Companion.</small></p>
        </body>
        </html>
        """

        # Send email
        response = ses_client.send_email(
            Source=settings.ses_from_email,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": body_text, "Charset": "UTF-8"},
                    "Html": {"Data": body_html, "Charset": "UTF-8"},
                },
            },
        )

        return True

    except Exception as e:
        # Log error but don't raise (nudges are non-critical)
        print(f"SES email error: {e}")
        return False
