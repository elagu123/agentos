"""
FastAPI WebSocket endpoints for real-time communication in AgentOS.

This module provides:
- WebSocket connection management
- Real-time agent updates
- Chat message streaming
- Workflow status broadcasting
- Organization-wide notifications
"""
from typing import List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.security import HTTPBearer
import json
import structlog

from app.core.websocket_manager import connection_pool
from app.core.auth import verify_token, get_current_user
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)
router = APIRouter()
security = HTTPBearer()

# Initialize background tasks on startup
async def startup_websocket_tasks():
    """Start WebSocket background tasks."""
    await connection_pool.start_background_tasks()

async def shutdown_websocket_tasks():
    """Stop WebSocket background tasks."""
    await connection_pool.stop_background_tasks()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    token: Optional[str] = None,
    channels: Optional[str] = None
):
    """
    Main WebSocket endpoint for real-time communication.

    Args:
        websocket: WebSocket connection
        user_id: User identifier
        token: JWT authentication token (can be passed as query param)
        channels: Comma-separated list of channels to subscribe to
    """
    try:
        # Extract token from query parameters if not in header
        if not token:
            token = websocket.query_params.get("token")

        if not token:
            await websocket.close(code=4001, reason="Authentication required")
            return

        # Verify authentication
        try:
            payload = verify_token(token)
            authenticated_user_id = payload.get("sub")

            # Ensure user can only connect as themselves
            if authenticated_user_id != user_id:
                await websocket.close(code=4003, reason="Unauthorized")
                return

            organization_id = payload.get("org_id")
            if not organization_id:
                await websocket.close(code=4003, reason="Organization required")
                return

        except Exception as e:
            logger.warning(f"WebSocket authentication failed: {e}")
            await websocket.close(code=4001, reason="Invalid token")
            return

        # Parse channels
        channel_list = []
        if channels:
            channel_list = [ch.strip() for ch in channels.split(",") if ch.strip()]

        # Default channels for all users
        default_channels = [
            f"user:{user_id}",  # Personal notifications
            f"org:{organization_id}",  # Organization-wide updates
            "system"  # System-wide announcements
        ]

        all_channels = list(set(default_channels + channel_list))

        # Connect to WebSocket pool
        await connection_pool.connect(
            websocket=websocket,
            user_id=user_id,
            organization_id=organization_id,
            channels=all_channels
        )

        logger.info(
            f"WebSocket connected successfully",
            user_id=user_id,
            organization_id=organization_id,
            channels=all_channels
        )

        # Handle incoming messages
        try:
            while True:
                # Receive message from client
                data = await websocket.receive_text()

                try:
                    message = json.loads(data)
                    await handle_websocket_message(websocket, user_id, organization_id, message)
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON format"
                    })
                except Exception as e:
                    logger.error(f"Error handling WebSocket message: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Failed to process message"
                    })

        except WebSocketDisconnect:
            pass  # Normal disconnection
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            # Clean up connection
            await connection_pool.disconnect(user_id)
            logger.info(f"WebSocket disconnected", user_id=user_id)

    except Exception as e:
        logger.error(f"WebSocket endpoint error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass  # Connection might already be closed

async def handle_websocket_message(
    websocket: WebSocket,
    user_id: str,
    organization_id: str,
    message: dict
):
    """
    Handle incoming WebSocket messages from clients.

    Args:
        websocket: WebSocket connection
        user_id: User identifier
        organization_id: Organization identifier
        message: Parsed JSON message
    """
    message_type = message.get("type")

    if message_type == "ping":
        # Respond to ping with pong
        await websocket.send_json({
            "type": "pong",
            "timestamp": message.get("timestamp")
        })

    elif message_type == "subscribe":
        # Subscribe to additional channels
        channel = message.get("channel")
        if channel:
            success = await connection_pool.subscribe_to_channel(user_id, channel)
            await websocket.send_json({
                "type": "subscription_result",
                "channel": channel,
                "success": success
            })

    elif message_type == "unsubscribe":
        # Unsubscribe from channels
        channel = message.get("channel")
        if channel:
            success = await connection_pool.unsubscribe_from_channel(user_id, channel)
            await websocket.send_json({
                "type": "unsubscription_result",
                "channel": channel,
                "success": success
            })

    elif message_type == "broadcast_to_org":
        # Broadcast message to organization (admin only)
        # TODO: Add admin permission check
        content = message.get("content")
        if content:
            await connection_pool.broadcast_to_organization(
                organization_id,
                {
                    "type": "org_broadcast",
                    "content": content,
                    "sender": user_id
                }
            )

    elif message_type == "get_stats":
        # Send connection statistics (admin only)
        # TODO: Add admin permission check
        stats = connection_pool.get_connection_stats()
        await websocket.send_json({
            "type": "stats",
            "data": stats
        })

    elif message_type == "get_channels":
        # Get user's current channels
        channels = await connection_pool.get_user_channels(user_id)
        await websocket.send_json({
            "type": "channels",
            "channels": channels
        })

    else:
        await websocket.send_json({
            "type": "error",
            "message": f"Unknown message type: {message_type}"
        })

# REST endpoints for WebSocket management

@router.get("/ws/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics."""
    stats = connection_pool.get_connection_stats()
    return {
        "status": "success",
        "data": stats
    }

@router.post("/ws/broadcast/channel/{channel}")
async def broadcast_to_channel(
    channel: str,
    message: dict,
    current_user = Depends(get_current_user)
):
    """
    Broadcast message to all users in a specific channel.

    Args:
        channel: Channel name
        message: Message content
        current_user: Authenticated user
    """
    try:
        await connection_pool.broadcast_to_channel(channel, {
            **message,
            "sender": current_user.id,
            "sender_type": "api"
        })

        return {
            "status": "success",
            "message": f"Message broadcasted to channel: {channel}"
        }
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        raise HTTPException(status_code=500, detail="Failed to broadcast message")

@router.post("/ws/send/user/{user_id}")
async def send_to_user(
    user_id: str,
    message: dict,
    current_user = Depends(get_current_user)
):
    """
    Send message to a specific user.

    Args:
        user_id: Target user ID
        message: Message content
        current_user: Authenticated user
    """
    try:
        success = await connection_pool.send_to_user(user_id, {
            **message,
            "sender": current_user.id,
            "sender_type": "api"
        })

        if success:
            return {
                "status": "success",
                "message": f"Message sent to user: {user_id}"
            }
        else:
            return {
                "status": "warning",
                "message": f"User not connected: {user_id}"
            }
    except Exception as e:
        logger.error(f"Send message error: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")

@router.post("/ws/broadcast/organization")
async def broadcast_to_organization(
    message: dict,
    current_user = Depends(get_current_user)
):
    """
    Broadcast message to all users in the current organization.

    Args:
        message: Message content
        current_user: Authenticated user
    """
    try:
        await connection_pool.broadcast_to_organization(
            current_user.organization_id,
            {
                **message,
                "sender": current_user.id,
                "sender_type": "api"
            }
        )

        return {
            "status": "success",
            "message": "Message broadcasted to organization"
        }
    except Exception as e:
        logger.error(f"Organization broadcast error: {e}")
        raise HTTPException(status_code=500, detail="Failed to broadcast to organization")

# Health check endpoint
@router.get("/ws/health")
async def websocket_health():
    """WebSocket system health check."""
    stats = connection_pool.get_connection_stats()

    return {
        "status": "healthy",
        "active_connections": stats.get("active_connections", 0),
        "total_connections": stats.get("total_connections", 0),
        "active_channels": stats.get("channels_active", 0),
        "uptime": "WebSocket manager is running"
    }