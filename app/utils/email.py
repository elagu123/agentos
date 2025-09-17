"""
Email utilities for AgentOS
Handles sending emails with templates and tracking
"""

import smtplib
import ssl
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from email.mime.base import MimeBase
from email import encoders
import os
from typing import Dict, Any, List, Optional
from jinja2 import Environment, FileSystemLoader
import aiosmtplib
from ..config import settings

class EmailService:
    """Email service for sending templated emails"""

    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.FROM_EMAIL
        self.from_name = settings.FROM_NAME

        # Setup Jinja2 for templates
        template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates', 'email')
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=True
        )

    async def send_email(
        self,
        to: str,
        subject: str,
        template: str = None,
        html_content: str = None,
        text_content: str = None,
        data: Dict[str, Any] = None,
        attachments: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send email with optional template rendering

        Args:
            to: Recipient email address
            subject: Email subject
            template: Template name (without .html extension)
            html_content: Raw HTML content (if not using template)
            text_content: Plain text content
            data: Template variables
            attachments: List of attachment dicts with 'filename' and 'content'

        Returns:
            Dict with success status and details
        """

        try:
            # Create message
            message = MimeMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to

            # Render template if provided
            if template:
                html_content = await self._render_template(template, data or {})

            # Add text part
            if text_content:
                text_part = MimeText(text_content, "plain")
                message.attach(text_part)

            # Add HTML part
            if html_content:
                html_part = MimeText(html_content, "html")
                message.attach(html_part)

            # Add attachments
            if attachments:
                for attachment in attachments:
                    await self._add_attachment(message, attachment)

            # Send email
            await self._send_message(message)

            return {
                "success": True,
                "message": f"Email sent successfully to {to}",
                "recipient": to,
                "subject": subject
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "recipient": to,
                "subject": subject
            }

    async def _render_template(self, template_name: str, data: Dict[str, Any]) -> str:
        """Render email template with data"""

        try:
            template = self.jinja_env.get_template(f"{template_name}.html")
            return template.render(**data)
        except Exception as e:
            raise Exception(f"Template rendering failed: {str(e)}")

    async def _add_attachment(self, message: MimeMultipart, attachment: Dict[str, Any]):
        """Add attachment to email message"""

        filename = attachment.get("filename")
        content = attachment.get("content")
        content_type = attachment.get("content_type", "application/octet-stream")

        part = MimeBase(*content_type.split("/"))
        part.set_payload(content)
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {filename}",
        )
        message.attach(part)

    async def _send_message(self, message: MimeMultipart):
        """Send email message via SMTP"""

        # Use aiosmtplib for async sending
        await aiosmtplib.send(
            message,
            hostname=self.smtp_server,
            port=self.smtp_port,
            username=self.smtp_username,
            password=self.smtp_password,
            use_tls=True
        )

    async def send_bulk_emails(
        self,
        recipients: List[str],
        subject: str,
        template: str,
        data_list: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send bulk emails with personalized data

        Args:
            recipients: List of email addresses
            subject: Email subject
            template: Template name
            data_list: List of template data dicts (one per recipient)

        Returns:
            Dict with success/failure counts and details
        """

        results = {
            "total": len(recipients),
            "successful": 0,
            "failed": 0,
            "errors": []
        }

        for i, recipient in enumerate(recipients):
            try:
                # Get data for this recipient
                recipient_data = data_list[i] if data_list and i < len(data_list) else {}

                # Send email
                result = await self.send_email(
                    to=recipient,
                    subject=subject,
                    template=template,
                    data=recipient_data
                )

                if result["success"]:
                    results["successful"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "recipient": recipient,
                        "error": result["error"]
                    })

            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "recipient": recipient,
                    "error": str(e)
                })

        return results

# Email templates data
EMAIL_TEMPLATES = {
    "beta_welcome": {
        "subject": "🚀 Bienvenido al Beta de AgentOS",
        "description": "Welcome email for new beta users"
    },
    "beta_day1_tips": {
        "subject": "💡 Día 1: Tips para maximizar AgentOS",
        "description": "Day 1 productivity tips"
    },
    "beta_workflow_check": {
        "subject": "🔧 ¿Cómo va tu primer workflow?",
        "description": "Day 3 workflow progress check"
    },
    "beta_weekly_checkin": {
        "subject": "📊 Check-in semanal - ¿Cómo va tu experiencia?",
        "description": "Weekly progress and feedback check"
    },
    "beta_feature_discovery": {
        "subject": "🔍 Descubre funciones avanzadas de AgentOS",
        "description": "Advanced features introduction"
    },
    "beta_feedback_survey": {
        "subject": "📝 Tu opinión importa - Encuesta de feedback",
        "description": "30-day feedback survey"
    }
}

# Singleton instance
email_service = EmailService()

# Convenience function
async def send_email(
    to: str,
    subject: str,
    template: str = None,
    html_content: str = None,
    text_content: str = None,
    data: Dict[str, Any] = None,
    attachments: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Send email using the global email service"""
    return await email_service.send_email(
        to=to,
        subject=subject,
        template=template,
        html_content=html_content,
        text_content=text_content,
        data=data,
        attachments=attachments
    )

async def send_beta_welcome_email(email: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Send beta welcome email with predefined template"""
    return await send_email(
        to=email,
        subject=EMAIL_TEMPLATES["beta_welcome"]["subject"],
        template="beta_welcome",
        data=data
    )

async def send_beta_tips_email(email: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Send beta tips email"""
    return await send_email(
        to=email,
        subject=EMAIL_TEMPLATES["beta_day1_tips"]["subject"],
        template="beta_day1_tips",
        data=data
    )