"""
WhatsApp Business API Integration for AgentOS
Complete WhatsApp Business integration with message handling, media, and webhooks
"""

import httpx
from typing import Dict, List, Optional, Any, Tuple
import json
from datetime import datetime, timedelta
import asyncio
from dataclasses import dataclass, field
import hmac
import hashlib
import base64
import tempfile
import os
import logging
from enum import Enum
import time
from collections import deque

logger = logging.getLogger(__name__)

class MessageType(Enum):
    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    LOCATION = "location"
    CONTACTS = "contacts"
    TEMPLATE = "template"
    INTERACTIVE = "interactive"
    STICKER = "sticker"

class MessageStatus(Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"

class InteractiveType(Enum):
    BUTTON = "button"
    LIST = "list"
    FLOW = "flow"

@dataclass
class WhatsAppMessage:
    to: str
    type: MessageType
    content: Any
    message_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    status: MessageStatus = MessageStatus.QUEUED
    error: Optional[str] = None

@dataclass
class MediaItem:
    id: str
    url: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    caption: Optional[str] = None

@dataclass
class Contact:
    name: str
    phone: str
    email: Optional[str] = None
    organization: Optional[str] = None

@dataclass
class Location:
    latitude: float
    longitude: float
    name: Optional[str] = None
    address: Optional[str] = None

@dataclass
class WebhookEvent:
    event_type: str
    phone_number: str
    message_id: Optional[str] = None
    status: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = field(default_factory=dict)

class WhatsAppIntegration:
    def __init__(
        self,
        access_token: str,
        phone_number_id: str,
        business_account_id: str,
        webhook_verify_token: str,
        webhook_secret: Optional[str] = None
    ):
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.business_account_id = business_account_id
        self.webhook_verify_token = webhook_verify_token
        self.webhook_secret = webhook_secret

        self.api_version = "v18.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

        # Rate limiting - WhatsApp allows 80 messages per second
        self.rate_limit = 80
        self.rate_limit_window = deque(maxlen=self.rate_limit)

        # Message tracking
        self.sent_messages: Dict[str, WhatsAppMessage] = {}
        self.webhook_events: List[WebhookEvent] = []

        # Template cache
        self.templates_cache: Dict[str, Dict] = {}
        self.templates_last_updated: Optional[datetime] = None

        # Media cache
        self.media_cache: Dict[str, MediaItem] = {}

        # Error tracking
        self.error_counts = {
            "rate_limit": 0,
            "invalid_token": 0,
            "network_error": 0,
            "invalid_number": 0,
            "media_error": 0
        }

    # === Message Sending ===

    async def send_text_message(
        self,
        to: str,
        text: str,
        preview_url: bool = True
    ) -> Dict[str, Any]:
        """Send text message"""

        if not text.strip():
            raise ValueError("Message text cannot be empty")

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._format_phone_number(to),
            "type": "text",
            "text": {
                "preview_url": preview_url,
                "body": text[:4096]  # WhatsApp text limit
            }
        }

        return await self._send_message(payload)

    async def send_media_message(
        self,
        to: str,
        media_type: MessageType,
        media_url: Optional[str] = None,
        media_id: Optional[str] = None,
        caption: Optional[str] = None,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send media message (image, document, audio, video)"""

        if not media_url and not media_id:
            raise ValueError("Either media_url or media_id must be provided")

        if media_type not in [MessageType.IMAGE, MessageType.DOCUMENT, MessageType.AUDIO, MessageType.VIDEO]:
            raise ValueError(f"Invalid media type: {media_type}")

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._format_phone_number(to),
            "type": media_type.value
        }

        media_obj = {}

        if media_id:
            media_obj["id"] = media_id
        else:
            media_obj["link"] = media_url

        if caption and media_type in [MessageType.IMAGE, MessageType.DOCUMENT, MessageType.VIDEO]:
            media_obj["caption"] = caption[:1024]  # Caption limit

        if filename and media_type == MessageType.DOCUMENT:
            media_obj["filename"] = filename

        payload[media_type.value] = media_obj

        return await self._send_message(payload)

    async def send_location_message(
        self,
        to: str,
        latitude: float,
        longitude: float,
        name: Optional[str] = None,
        address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send location message"""

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._format_phone_number(to),
            "type": "location",
            "location": {
                "latitude": latitude,
                "longitude": longitude
            }
        }

        if name:
            payload["location"]["name"] = name
        if address:
            payload["location"]["address"] = address

        return await self._send_message(payload)

    async def send_contacts_message(
        self,
        to: str,
        contacts: List[Contact]
    ) -> Dict[str, Any]:
        """Send contact information"""

        if not contacts:
            raise ValueError("At least one contact must be provided")

        contacts_data = []
        for contact in contacts:
            contact_obj = {
                "name": {
                    "formatted_name": contact.name
                },
                "phones": [
                    {
                        "phone": self._format_phone_number(contact.phone),
                        "type": "CELL"
                    }
                ]
            }

            if contact.email:
                contact_obj["emails"] = [
                    {
                        "email": contact.email,
                        "type": "WORK"
                    }
                ]

            if contact.organization:
                contact_obj["org"] = {
                    "company": contact.organization
                }

            contacts_data.append(contact_obj)

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._format_phone_number(to),
            "type": "contacts",
            "contacts": contacts_data
        }

        return await self._send_message(payload)

    async def send_template_message(
        self,
        to: str,
        template_name: str,
        language_code: str = "en",
        components: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Send message with pre-approved template"""

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._format_phone_number(to),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": language_code
                }
            }
        }

        if components:
            payload["template"]["components"] = components

        return await self._send_message(payload)

    async def send_interactive_buttons(
        self,
        to: str,
        body_text: str,
        buttons: List[Dict[str, str]],
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send interactive message with buttons"""

        if len(buttons) > 3:
            raise ValueError("Maximum 3 buttons allowed")

        button_components = []
        for i, button in enumerate(buttons):
            button_components.append({
                "type": "reply",
                "reply": {
                    "id": button.get("id", f"btn_{i}"),
                    "title": button.get("title", f"Button {i+1}")[:20]  # Button title limit
                }
            })

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._format_phone_number(to),
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": body_text
                },
                "action": {
                    "buttons": button_components
                }
            }
        }

        if header_text:
            payload["interactive"]["header"] = {
                "type": "text",
                "text": header_text
            }

        if footer_text:
            payload["interactive"]["footer"] = {
                "text": footer_text
            }

        return await self._send_message(payload)

    async def send_interactive_list(
        self,
        to: str,
        body_text: str,
        button_text: str,
        sections: List[Dict],
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send interactive message with list"""

        if len(sections) > 10:
            raise ValueError("Maximum 10 sections allowed")

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._format_phone_number(to),
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {
                    "text": body_text
                },
                "action": {
                    "button": button_text,
                    "sections": sections
                }
            }
        }

        if header_text:
            payload["interactive"]["header"] = {
                "type": "text",
                "text": header_text
            }

        if footer_text:
            payload["interactive"]["footer"] = {
                "text": footer_text
            }

        return await self._send_message(payload)

    # === Media Management ===

    async def upload_media(
        self,
        file_path: str,
        media_type: str
    ) -> MediaItem:
        """Upload media file and return media ID"""

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Validate file size (WhatsApp limits)
        file_size = os.path.getsize(file_path)
        max_sizes = {
            "image": 5 * 1024 * 1024,      # 5MB
            "document": 100 * 1024 * 1024,  # 100MB
            "audio": 16 * 1024 * 1024,      # 16MB
            "video": 16 * 1024 * 1024,      # 16MB
            "sticker": 100 * 1024           # 100KB
        }

        if file_size > max_sizes.get(media_type, 16 * 1024 * 1024):
            raise ValueError(f"File too large for {media_type}: {file_size} bytes")

        url = f"{self.base_url}/{self.phone_number_id}/media"

        # Determine MIME type
        import mimetypes
        mime_type, _ = mimetypes.guess_type(file_path)

        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(file_path, 'rb') as f:
                files = {
                    'file': (os.path.basename(file_path), f, mime_type),
                    'type': (None, media_type),
                    'messaging_product': (None, 'whatsapp')
                }

                headers = {
                    "Authorization": f"Bearer {self.access_token}"
                }

                response = await client.post(
                    url,
                    files=files,
                    headers=headers
                )

        if response.status_code != 200:
            self.error_counts["media_error"] += 1
            raise Exception(f"Media upload failed: {response.status_code} - {response.text}")

        data = response.json()
        media_id = data.get("id")

        media_item = MediaItem(
            id=media_id,
            mime_type=mime_type,
            file_size=file_size
        )

        self.media_cache[media_id] = media_item

        logger.info(f"Uploaded media: {file_path} -> {media_id}")

        return media_item

    async def download_media(self, media_id: str, output_dir: Optional[str] = None) -> str:
        """Download media file by ID"""

        # First get media URL
        url = f"{self.base_url}/{media_id}"

        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get media info
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                raise Exception(f"Failed to get media info: {response.status_code} - {response.text}")

            media_info = response.json()
            media_url = media_info.get("url")
            mime_type = media_info.get("mime_type")

            if not media_url:
                raise Exception("Media URL not found in response")

            # Download media
            response = await client.get(media_url, headers=headers)

            if response.status_code != 200:
                raise Exception(f"Failed to download media: {response.status_code}")

            # Determine file extension
            import mimetypes
            extension = mimetypes.guess_extension(mime_type) or ".bin"

            # Save to file
            if output_dir is None:
                output_dir = tempfile.gettempdir()

            filename = f"{media_id}{extension}"
            output_path = os.path.join(output_dir, filename)

            with open(output_path, 'wb') as f:
                f.write(response.content)

            logger.info(f"Downloaded media: {media_id} -> {output_path}")

            return output_path

    async def delete_media(self, media_id: str) -> bool:
        """Delete media file"""

        url = f"{self.base_url}/{media_id}"

        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        async with httpx.AsyncClient() as client:
            response = await client.delete(url, headers=headers)

        if response.status_code == 200:
            if media_id in self.media_cache:
                del self.media_cache[media_id]
            return True

        return False

    # === Webhook Handling ===

    def verify_webhook(
        self,
        mode: str,
        token: str,
        challenge: str
    ) -> Optional[str]:
        """Verify webhook during setup"""

        if mode == "subscribe" and token == self.webhook_verify_token:
            logger.info("Webhook verified successfully")
            return challenge

        logger.warning(f"Webhook verification failed: mode={mode}, token={token}")
        return None

    def verify_webhook_signature(
        self,
        signature: str,
        payload: bytes
    ) -> bool:
        """Verify webhook signature for security"""

        if not self.webhook_secret:
            logger.warning("Webhook secret not configured, skipping signature verification")
            return True

        # Extract signature from header (format: sha256=signature)
        if not signature.startswith("sha256="):
            logger.warning("Invalid signature format")
            return False

        provided_signature = signature[7:]  # Remove "sha256=" prefix

        # Calculate expected signature
        expected_signature = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        is_valid = hmac.compare_digest(expected_signature, provided_signature)

        if not is_valid:
            logger.warning("Webhook signature verification failed")

        return is_valid

    async def process_webhook(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process incoming webhook from WhatsApp"""

        processed_events = []

        try:
            for entry in data.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})

                    # Process incoming messages
                    for message in value.get("messages", []):
                        event = await self._process_incoming_message(message)
                        if event:
                            processed_events.append(event)

                    # Process message statuses
                    for status in value.get("statuses", []):
                        event = await self._process_message_status(status)
                        if event:
                            processed_events.append(event)

        except Exception as e:
            logger.error(f"Error processing webhook: {e}")

        return processed_events

    async def _process_incoming_message(self, message: Dict) -> Optional[Dict[str, Any]]:
        """Process incoming message"""

        message_id = message.get("id")
        from_number = message.get("from")
        timestamp = datetime.fromtimestamp(int(message.get("timestamp", 0)))
        msg_type = message.get("type")

        # Extract message content based on type
        content = self._extract_message_content(message)

        # Mark message as read
        if message_id:
            try:
                await self.mark_as_read(message_id)
            except Exception as e:
                logger.warning(f"Failed to mark message as read: {e}")

        event = {
            "event_type": "message_received",
            "message_id": message_id,
            "from": from_number,
            "timestamp": timestamp,
            "type": msg_type,
            "content": content,
            "context": message.get("context", {})
        }

        # Store webhook event
        webhook_event = WebhookEvent(
            event_type="message_received",
            phone_number=from_number,
            message_id=message_id,
            timestamp=timestamp,
            data=event
        )
        self.webhook_events.append(webhook_event)

        logger.info(f"Processed incoming message: {message_id} from {from_number}")

        return event

    async def _process_message_status(self, status: Dict) -> Optional[Dict[str, Any]]:
        """Process message status update"""

        message_id = status.get("id")
        recipient_id = status.get("recipient_id")
        status_value = status.get("status")
        timestamp = datetime.fromtimestamp(int(status.get("timestamp", 0)))

        # Update sent message status if we have it
        if message_id in self.sent_messages:
            sent_msg = self.sent_messages[message_id]
            try:
                sent_msg.status = MessageStatus(status_value)
            except ValueError:
                logger.warning(f"Unknown message status: {status_value}")

        event = {
            "event_type": "message_status",
            "message_id": message_id,
            "recipient_id": recipient_id,
            "status": status_value,
            "timestamp": timestamp
        }

        # Store webhook event
        webhook_event = WebhookEvent(
            event_type="message_status",
            phone_number=recipient_id,
            message_id=message_id,
            status=status_value,
            timestamp=timestamp,
            data=event
        )
        self.webhook_events.append(webhook_event)

        logger.debug(f"Message {message_id} status: {status_value}")

        return event

    def _extract_message_content(self, message: Dict) -> Any:
        """Extract content from message based on type"""

        msg_type = message.get("type")

        if msg_type == "text":
            return message.get("text", {}).get("body")

        elif msg_type == "image":
            return {
                "media_id": message.get("image", {}).get("id"),
                "caption": message.get("image", {}).get("caption"),
                "mime_type": message.get("image", {}).get("mime_type")
            }

        elif msg_type == "document":
            return {
                "media_id": message.get("document", {}).get("id"),
                "filename": message.get("document", {}).get("filename"),
                "caption": message.get("document", {}).get("caption"),
                "mime_type": message.get("document", {}).get("mime_type")
            }

        elif msg_type == "audio":
            return {
                "media_id": message.get("audio", {}).get("id"),
                "mime_type": message.get("audio", {}).get("mime_type")
            }

        elif msg_type == "video":
            return {
                "media_id": message.get("video", {}).get("id"),
                "caption": message.get("video", {}).get("caption"),
                "mime_type": message.get("video", {}).get("mime_type")
            }

        elif msg_type == "location":
            location = message.get("location", {})
            return {
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
                "name": location.get("name"),
                "address": location.get("address")
            }

        elif msg_type == "contacts":
            return message.get("contacts", [])

        elif msg_type == "button":
            return {
                "text": message.get("button", {}).get("text"),
                "payload": message.get("button", {}).get("payload")
            }

        elif msg_type == "interactive":
            interactive = message.get("interactive", {})
            return {
                "type": interactive.get("type"),
                "list_reply": interactive.get("list_reply"),
                "button_reply": interactive.get("button_reply")
            }

        elif msg_type == "sticker":
            return {
                "media_id": message.get("sticker", {}).get("id"),
                "mime_type": message.get("sticker", {}).get("mime_type")
            }

        return None

    # === Business Profile Management ===

    async def get_business_profile(self) -> Dict[str, Any]:
        """Get business profile information"""

        url = f"{self.base_url}/{self.phone_number_id}/business_profile"

        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)

        if response.status_code != 200:
            raise Exception(f"Failed to get business profile: {response.status_code} - {response.text}")

        return response.json()

    async def update_business_profile(
        self,
        about: Optional[str] = None,
        address: Optional[str] = None,
        description: Optional[str] = None,
        email: Optional[str] = None,
        websites: Optional[List[str]] = None,
        profile_picture_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update business profile"""

        url = f"{self.base_url}/{self.phone_number_id}/business_profile"

        data = {}
        if about:
            data["about"] = about[:139]  # WhatsApp limit
        if address:
            data["address"] = address
        if description:
            data["description"] = description[:512]  # WhatsApp limit
        if email:
            data["email"] = email
        if websites:
            data["websites"] = websites[:2]  # Maximum 2 websites
        if profile_picture_url:
            data["profile_picture_url"] = profile_picture_url

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=data,
                headers=headers
            )

        if response.status_code != 200:
            raise Exception(f"Failed to update business profile: {response.status_code} - {response.text}")

        return response.json()

    # === Template Management ===

    async def get_message_templates(self, refresh: bool = False) -> List[Dict[str, Any]]:
        """Get available message templates"""

        # Use cache if available and not refreshing
        if not refresh and self.templates_cache and self.templates_last_updated:
            if datetime.utcnow() - self.templates_last_updated < timedelta(hours=1):
                return list(self.templates_cache.values())

        url = f"{self.base_url}/{self.business_account_id}/message_templates"

        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)

        if response.status_code != 200:
            raise Exception(f"Failed to get templates: {response.status_code} - {response.text}")

        data = response.json()
        templates = data.get("data", [])

        # Update cache
        self.templates_cache = {t["name"]: t for t in templates}
        self.templates_last_updated = datetime.utcnow()

        return templates

    async def get_template_by_name(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Get specific template by name"""

        if template_name in self.templates_cache:
            return self.templates_cache[template_name]

        # Refresh cache and try again
        templates = await self.get_message_templates(refresh=True)

        return self.templates_cache.get(template_name)

    # === Utility Methods ===

    async def mark_as_read(self, message_id: str) -> Dict[str, Any]:
        """Mark message as read"""

        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }

        url = f"{self.base_url}/{self.phone_number_id}/messages"

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                headers=headers
            )

        return response.json()

    async def _send_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send message with rate limiting and error handling"""

        # Check rate limit
        await self._check_rate_limit()

        url = f"{self.base_url}/{self.phone_number_id}/messages"

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers
                )

            if response.status_code == 429:
                self.error_counts["rate_limit"] += 1
                raise Exception("Rate limit exceeded")

            elif response.status_code == 401:
                self.error_counts["invalid_token"] += 1
                raise Exception("Invalid access token")

            elif response.status_code != 200:
                error_data = response.json().get("error", {})
                error_message = error_data.get("message", "Unknown error")

                if "phone number" in error_message.lower():
                    self.error_counts["invalid_number"] += 1

                raise Exception(f"WhatsApp API error: {response.status_code} - {error_message}")

            # Success
            data = response.json()
            message_id = data.get("messages", [{}])[0].get("id")

            # Track sent message
            if message_id:
                whatsapp_msg = WhatsAppMessage(
                    to=payload.get("to"),
                    type=MessageType(payload.get("type")),
                    content=payload,
                    message_id=message_id,
                    timestamp=datetime.utcnow(),
                    status=MessageStatus.SENT
                )
                self.sent_messages[message_id] = whatsapp_msg

            logger.info(f"Sent WhatsApp message: {message_id}")

            return data

        except httpx.RequestError as e:
            self.error_counts["network_error"] += 1
            logger.error(f"Network error sending WhatsApp message: {e}")
            raise Exception(f"Network error: {e}")

    async def _check_rate_limit(self):
        """Check and enforce rate limiting"""

        now = time.time()

        # Remove old timestamps
        while self.rate_limit_window and now - self.rate_limit_window[0] > 1:
            self.rate_limit_window.popleft()

        # Check if we're at the limit
        if len(self.rate_limit_window) >= self.rate_limit:
            sleep_time = 1 - (now - self.rate_limit_window[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        # Add current timestamp
        self.rate_limit_window.append(now)

    def _format_phone_number(self, phone: str) -> str:
        """Format phone number for WhatsApp API"""

        # Remove all non-digit characters
        phone = ''.join(filter(str.isdigit, phone))

        # Remove leading + or 00
        if phone.startswith("00"):
            phone = phone[2:]
        elif phone.startswith("0"):
            phone = phone[1:]

        # Ensure it has a country code
        if len(phone) == 10:  # Assume US/Canada if 10 digits
            phone = "1" + phone

        return phone

    # === Analytics and Reporting ===

    def get_message_stats(self) -> Dict[str, Any]:
        """Get message statistics"""

        total_sent = len(self.sent_messages)

        status_counts = {}
        for msg in self.sent_messages.values():
            status = msg.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_sent": total_sent,
            "status_breakdown": status_counts,
            "error_counts": self.error_counts.copy(),
            "webhook_events": len(self.webhook_events),
            "templates_cached": len(self.templates_cache),
            "media_cached": len(self.media_cache)
        }

    def get_recent_webhook_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent webhook events"""

        recent_events = self.webhook_events[-limit:] if self.webhook_events else []

        return [
            {
                "event_type": event.event_type,
                "phone_number": event.phone_number,
                "message_id": event.message_id,
                "status": event.status,
                "timestamp": event.timestamp.isoformat(),
                "data": event.data
            }
            for event in recent_events
        ]

    async def health_check(self) -> Dict[str, Any]:
        """Check integration health"""

        try:
            # Test API connection by getting business profile
            profile = await self.get_business_profile()

            return {
                "status": "healthy",
                "api_accessible": True,
                "business_profile": profile.get("data", [{}])[0].get("about", ""),
                "rate_limit_status": f"{len(self.rate_limit_window)}/{self.rate_limit}",
                "error_counts": self.error_counts,
                "last_activity": max(
                    [msg.timestamp for msg in self.sent_messages.values()],
                    default=datetime.min
                ).isoformat() if self.sent_messages else None
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "api_accessible": False
            }

# Singleton instance for global use
whatsapp_integration: Optional[WhatsAppIntegration] = None

def initialize_whatsapp(
    access_token: str,
    phone_number_id: str,
    business_account_id: str,
    webhook_verify_token: str,
    webhook_secret: Optional[str] = None
) -> WhatsAppIntegration:
    """Initialize global WhatsApp integration"""

    global whatsapp_integration

    whatsapp_integration = WhatsAppIntegration(
        access_token=access_token,
        phone_number_id=phone_number_id,
        business_account_id=business_account_id,
        webhook_verify_token=webhook_verify_token,
        webhook_secret=webhook_secret
    )

    logger.info("WhatsApp integration initialized")

    return whatsapp_integration

def get_whatsapp_integration() -> Optional[WhatsAppIntegration]:
    """Get global WhatsApp integration instance"""
    return whatsapp_integration