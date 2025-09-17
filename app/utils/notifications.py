"""
Notification system for AgentOS
Handles team notifications, alerts, and real-time updates
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import aiohttp
from ..config import settings

class NotificationService:
    """Service for sending notifications to team and users"""

    def __init__(self):
        self.slack_webhook = settings.SLACK_WEBHOOK_URL
        self.discord_webhook = settings.DISCORD_WEBHOOK_URL
        self.teams_webhook = settings.TEAMS_WEBHOOK_URL

    async def notify_team(
        self,
        message: str,
        data: Dict[str, Any] = None,
        severity: str = "info",
        channels: List[str] = None
    ) -> Dict[str, Any]:
        """
        Send notification to team channels

        Args:
            message: Main notification message
            data: Additional data to include
            severity: Notification severity (info, warning, error, critical)
            channels: Specific channels to notify (default: all configured)

        Returns:
            Dict with notification results
        """

        if channels is None:
            channels = ["slack", "discord", "teams"]

        results = {}

        # Prepare notification payload
        notification = {
            "message": message,
            "data": data or {},
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat(),
            "service": "AgentOS"
        }

        # Send to each channel
        if "slack" in channels and self.slack_webhook:
            results["slack"] = await self._send_slack_notification(notification)

        if "discord" in channels and self.discord_webhook:
            results["discord"] = await self._send_discord_notification(notification)

        if "teams" in channels and self.teams_webhook:
            results["teams"] = await self._send_teams_notification(notification)

        return results

    async def _send_slack_notification(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """Send notification to Slack"""

        try:
            # Format message for Slack
            color = {
                "info": "#36a64f",
                "warning": "#ff9800",
                "error": "#f44336",
                "critical": "#d32f2f"
            }.get(notification["severity"], "#36a64f")

            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"AgentOS - {notification['severity'].upper()}",
                        "text": notification["message"],
                        "fields": [
                            {
                                "title": "Timestamp",
                                "value": notification["timestamp"],
                                "short": True
                            }
                        ],
                        "footer": "AgentOS Beta",
                        "footer_icon": "https://agentos.ai/favicon.ico"
                    }
                ]
            }

            # Add data fields if present
            if notification["data"]:
                for key, value in notification["data"].items():
                    payload["attachments"][0]["fields"].append({
                        "title": key.replace("_", " ").title(),
                        "value": str(value),
                        "short": True
                    })

            async with aiohttp.ClientSession() as session:
                async with session.post(self.slack_webhook, json=payload) as response:
                    if response.status == 200:
                        return {"success": True, "channel": "slack"}
                    else:
                        return {"success": False, "error": f"HTTP {response.status}", "channel": "slack"}

        except Exception as e:
            return {"success": False, "error": str(e), "channel": "slack"}

    async def _send_discord_notification(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """Send notification to Discord"""

        try:
            # Format message for Discord
            color = {
                "info": 0x36a64f,
                "warning": 0xff9800,
                "error": 0xf44336,
                "critical": 0xd32f2f
            }.get(notification["severity"], 0x36a64f)

            embed = {
                "title": f"AgentOS - {notification['severity'].upper()}",
                "description": notification["message"],
                "color": color,
                "timestamp": notification["timestamp"],
                "footer": {
                    "text": "AgentOS Beta"
                }
            }

            # Add data fields if present
            if notification["data"]:
                embed["fields"] = []
                for key, value in notification["data"].items():
                    embed["fields"].append({
                        "name": key.replace("_", " ").title(),
                        "value": str(value),
                        "inline": True
                    })

            payload = {
                "embeds": [embed]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(self.discord_webhook, json=payload) as response:
                    if response.status == 204:
                        return {"success": True, "channel": "discord"}
                    else:
                        return {"success": False, "error": f"HTTP {response.status}", "channel": "discord"}

        except Exception as e:
            return {"success": False, "error": str(e), "channel": "discord"}

    async def _send_teams_notification(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """Send notification to Microsoft Teams"""

        try:
            # Format message for Teams
            color = {
                "info": "Good",
                "warning": "Warning",
                "error": "Attention",
                "critical": "Attention"
            }.get(notification["severity"], "Good")

            payload = {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "themeColor": {
                    "info": "36a64f",
                    "warning": "ff9800",
                    "error": "f44336",
                    "critical": "d32f2f"
                }.get(notification["severity"], "36a64f"),
                "summary": f"AgentOS - {notification['severity'].upper()}",
                "sections": [
                    {
                        "activityTitle": f"AgentOS - {notification['severity'].upper()}",
                        "activitySubtitle": notification["timestamp"],
                        "text": notification["message"],
                        "facts": []
                    }
                ]
            }

            # Add data facts if present
            if notification["data"]:
                for key, value in notification["data"].items():
                    payload["sections"][0]["facts"].append({
                        "name": key.replace("_", " ").title(),
                        "value": str(value)
                    })

            async with aiohttp.ClientSession() as session:
                async with session.post(self.teams_webhook, json=payload) as response:
                    if response.status == 200:
                        return {"success": True, "channel": "teams"}
                    else:
                        return {"success": False, "error": f"HTTP {response.status}", "channel": "teams"}

        except Exception as e:
            return {"success": False, "error": str(e), "channel": "teams"}

    async def notify_critical_feedback(self, feedback_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send critical feedback notification"""

        message = f"🚨 Critical feedback received from beta user: {feedback_data.get('user_email', 'Unknown')}"

        return await self.notify_team(
            message=message,
            data={
                "feedback_id": feedback_data.get("feedback_id"),
                "type": feedback_data.get("type"),
                "description": feedback_data.get("description", "")[:200],
                "severity": feedback_data.get("severity"),
                "url": feedback_data.get("url"),
                "user": feedback_data.get("user_email")
            },
            severity="critical"
        )

    async def notify_beta_milestone(self, milestone_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send beta milestone notification"""

        message = f"🎉 Beta milestone reached: {milestone_data.get('milestone_name')}"

        return await self.notify_team(
            message=message,
            data={
                "milestone": milestone_data.get("milestone_name"),
                "user_count": milestone_data.get("user_count"),
                "completion_rate": milestone_data.get("completion_rate"),
                "avg_time": milestone_data.get("avg_time")
            },
            severity="info"
        )

    async def notify_system_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send system alert notification"""

        severity_map = {
            "low": "info",
            "medium": "warning",
            "high": "error",
            "critical": "critical"
        }

        severity = severity_map.get(alert_data.get("severity", "medium"), "warning")
        message = f"⚠️ System Alert: {alert_data.get('title', 'Unknown Alert')}"

        return await self.notify_team(
            message=message,
            data={
                "alert_type": alert_data.get("type"),
                "description": alert_data.get("description"),
                "affected_users": alert_data.get("affected_users"),
                "service": alert_data.get("service"),
                "metric": alert_data.get("metric"),
                "threshold": alert_data.get("threshold"),
                "current_value": alert_data.get("current_value")
            },
            severity=severity
        )

    async def notify_new_beta_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send new beta user notification"""

        message = f"🎉 New beta user joined: {user_data.get('company_name', 'Unknown Company')}"

        return await self.notify_team(
            message=message,
            data={
                "email": user_data.get("email"),
                "company": user_data.get("company_name"),
                "beta_type": user_data.get("beta_type"),
                "features_enabled": ", ".join(user_data.get("features_enabled", [])),
                "signup_date": user_data.get("signup_date")
            },
            severity="info"
        )

# Singleton instance
notification_service = NotificationService()

# Convenience functions
async def notify_team(
    message: str,
    data: Dict[str, Any] = None,
    severity: str = "info",
    channels: List[str] = None
) -> Dict[str, Any]:
    """Send notification to team using global service"""
    return await notification_service.notify_team(message, data, severity, channels)

async def notify_critical_feedback(feedback_data: Dict[str, Any]) -> Dict[str, Any]:
    """Send critical feedback notification"""
    return await notification_service.notify_critical_feedback(feedback_data)

async def notify_beta_milestone(milestone_data: Dict[str, Any]) -> Dict[str, Any]:
    """Send beta milestone notification"""
    return await notification_service.notify_beta_milestone(milestone_data)

async def notify_system_alert(alert_data: Dict[str, Any]) -> Dict[str, Any]:
    """Send system alert notification"""
    return await notification_service.notify_system_alert(alert_data)

async def notify_new_beta_user(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Send new beta user notification"""
    return await notification_service.notify_new_beta_user(user_data)