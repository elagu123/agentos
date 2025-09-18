"""
Optimized WebSocket connection management for AgentOS.

This module provides:
- Efficient connection pooling
- Channel-based broadcasting
- Heartbeat monitoring
- Automatic reconnection
- Performance monitoring
"""
from typing import Dict, Set, List, Optional, Any
import json
import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass
from fastapi import WebSocket, WebSocketDisconnect
import structlog

from app.core.cache import cache_manager

logger = structlog.get_logger(__name__)


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""
    websocket: WebSocket
    user_id: str
    organization_id: str
    channels: Set[str]
    connected_at: float
    last_ping: float


class ConnectionPool:
    """
    Efficient WebSocket connection pooling with channel-based broadcasting.

    Features:
    - Group connections by channels for efficient broadcasting
    - Heartbeat monitoring to detect dead connections
    - Automatic cleanup of disconnected clients
    - Performance metrics and monitoring
    """

    def __init__(self):
        # Channel-based connection mapping for efficient broadcasting
        self.connections: Dict[str, Set[WebSocket]] = defaultdict(set)

        # User-specific connection mapping
        self.user_connections: Dict[str, ConnectionInfo] = {}

        # Organization-based grouping
        self.org_connections: Dict[str, Set[str]] = defaultdict(set)

        # Connection statistics
        self.stats = {
            'total_connections': 0,
            'active_connections': 0,
            'messages_sent': 0,
            'messages_failed': 0,
            'channels_active': 0
        }

        # Configuration
        self.heartbeat_interval = 30  # seconds
        self.connection_timeout = 60  # seconds

        # Background tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start_background_tasks(self):
        """Start background monitoring tasks."""
        if not self._heartbeat_task:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_monitor())

        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_stale_connections())

        logger.info("WebSocket background tasks started")

    async def stop_background_tasks(self):
        """Stop background monitoring tasks."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None

        logger.info("WebSocket background tasks stopped")

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        organization_id: str,
        channels: List[str]
    ):
        """
        Add a new WebSocket connection to the pool.

        Args:
            websocket: The WebSocket connection
            user_id: User identifier
            organization_id: Organization identifier
            channels: List of channels to subscribe to
        """
        try:
            await websocket.accept()

            # Create connection info
            connection_info = ConnectionInfo(
                websocket=websocket,
                user_id=user_id,
                organization_id=organization_id,
                channels=set(channels),
                connected_at=time.time(),
                last_ping=time.time()
            )

            # Add to user mapping
            if user_id in self.user_connections:
                # Disconnect existing connection
                await self._disconnect_user(user_id)

            self.user_connections[user_id] = connection_info

            # Add to organization mapping
            self.org_connections[organization_id].add(user_id)

            # Subscribe to channels
            for channel in channels:
                self.connections[channel].add(websocket)

            # Update statistics
            self.stats['total_connections'] += 1
            self.stats['active_connections'] = len(self.user_connections)
            self.stats['channels_active'] = len(self.connections)

            # Send connection confirmation
            await self._send_to_websocket(websocket, {
                'type': 'connection_established',
                'channels': channels,
                'timestamp': time.time()
            })

            logger.info(
                f"WebSocket connected",
                user_id=user_id,
                organization_id=organization_id,
                channels=channels,
                total_connections=self.stats['active_connections']
            )

            # Cache connection status
            await cache_manager.cache_user_session(
                user_id=user_id,
                session_data={
                    'websocket_connected': True,
                    'connected_at': connection_info.connected_at,
                    'channels': list(channels)
                },
                expire_time=3600
            )

        except Exception as e:
            logger.error(f"Failed to establish WebSocket connection: {e}")
            raise

    async def disconnect(self, user_id: str):
        """
        Remove a connection from the pool.

        Args:
            user_id: User identifier
        """
        await self._disconnect_user(user_id)

    async def _disconnect_user(self, user_id: str):
        """Internal method to disconnect a user."""
        if user_id not in self.user_connections:
            return

        connection_info = self.user_connections[user_id]

        try:
            # Remove from all channels
            for channel in connection_info.channels:
                self.connections[channel].discard(connection_info.websocket)

            # Remove from organization mapping
            self.org_connections[connection_info.organization_id].discard(user_id)

            # Remove from user mapping
            del self.user_connections[user_id]

            # Update statistics
            self.stats['active_connections'] = len(self.user_connections)

            # Clean up empty channels
            empty_channels = [
                channel for channel, sockets in self.connections.items()
                if not sockets
            ]
            for channel in empty_channels:
                del self.connections[channel]

            self.stats['channels_active'] = len(self.connections)

            # Clear session cache
            await cache_manager.cache_user_session(
                user_id=user_id,
                session_data={'websocket_connected': False},
                expire_time=60
            )

            logger.info(
                f"WebSocket disconnected",
                user_id=user_id,
                organization_id=connection_info.organization_id,
                total_connections=self.stats['active_connections']
            )

        except Exception as e:
            logger.warning(f"Error during disconnect cleanup: {e}")

    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any]):
        """
        Broadcast message to all connections in a channel.

        Args:
            channel: Channel name
            message: Message to broadcast
        """
        if channel not in self.connections:
            logger.debug(f"No connections in channel: {channel}")
            return

        connections = list(self.connections[channel])  # Copy to avoid modification during iteration
        if not connections:
            return

        # Add timestamp to message
        message_with_timestamp = {
            **message,
            'timestamp': time.time(),
            'channel': channel
        }

        # Broadcast concurrently to all connections
        tasks = [
            self._send_to_websocket(websocket, message_with_timestamp)
            for websocket in connections
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count success/failure
        success_count = sum(1 for result in results if not isinstance(result, Exception))
        failure_count = len(results) - success_count

        self.stats['messages_sent'] += success_count
        self.stats['messages_failed'] += failure_count

        logger.debug(
            f"Broadcast to channel {channel}",
            connections=len(connections),
            success=success_count,
            failed=failure_count
        )

    async def send_to_user(self, user_id: str, message: Dict[str, Any]):
        """
        Send message to a specific user.

        Args:
            user_id: User identifier
            message: Message to send
        """
        if user_id not in self.user_connections:
            logger.debug(f"User not connected: {user_id}")
            return False

        connection_info = self.user_connections[user_id]
        message_with_timestamp = {
            **message,
            'timestamp': time.time(),
            'recipient': user_id
        }

        try:
            await self._send_to_websocket(connection_info.websocket, message_with_timestamp)
            self.stats['messages_sent'] += 1
            return True
        except Exception as e:
            logger.warning(f"Failed to send message to user {user_id}: {e}")
            self.stats['messages_failed'] += 1
            # Remove dead connection
            await self.disconnect(user_id)
            return False

    async def broadcast_to_organization(self, org_id: str, message: Dict[str, Any]):
        """
        Broadcast message to all users in an organization.

        Args:
            org_id: Organization identifier
            message: Message to broadcast
        """
        user_ids = list(self.org_connections.get(org_id, set()))

        if not user_ids:
            logger.debug(f"No connections for organization: {org_id}")
            return

        # Send to all users in organization
        tasks = [self.send_to_user(user_id, message) for user_id in user_ids]
        results = await asyncio.gather(*tasks)

        success_count = sum(1 for result in results if result)
        logger.debug(
            f"Broadcast to organization {org_id}",
            users=len(user_ids),
            success=success_count
        )

    async def _send_to_websocket(self, websocket: WebSocket, message: Dict[str, Any]):
        """
        Send message to a WebSocket with error handling.

        Args:
            websocket: WebSocket connection
            message: Message to send
        """
        try:
            await websocket.send_json(message)
        except WebSocketDisconnect:
            # Connection already closed
            raise
        except Exception as e:
            logger.warning(f"WebSocket send error: {e}")
            raise

    async def _heartbeat_monitor(self):
        """Background task to monitor connection health."""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                current_time = time.time()
                dead_connections = []

                # Check all connections
                for user_id, connection_info in self.user_connections.items():
                    try:
                        # Send ping
                        await self._send_to_websocket(connection_info.websocket, {
                            'type': 'ping',
                            'timestamp': current_time
                        })

                        # Update last ping time
                        connection_info.last_ping = current_time

                    except Exception:
                        # Connection is dead
                        dead_connections.append(user_id)

                # Clean up dead connections
                for user_id in dead_connections:
                    await self.disconnect(user_id)

                if dead_connections:
                    logger.info(f"Cleaned up {len(dead_connections)} dead connections")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat monitor error: {e}")

    async def _cleanup_stale_connections(self):
        """Background task to clean up stale connections."""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute

                current_time = time.time()
                stale_connections = []

                # Find stale connections
                for user_id, connection_info in self.user_connections.items():
                    if current_time - connection_info.last_ping > self.connection_timeout:
                        stale_connections.append(user_id)

                # Clean up stale connections
                for user_id in stale_connections:
                    await self.disconnect(user_id)

                if stale_connections:
                    logger.info(f"Cleaned up {len(stale_connections)} stale connections")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup task error: {e}")

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            **self.stats,
            'channels': {
                channel: len(connections)
                for channel, connections in self.connections.items()
            },
            'organizations': {
                org_id: len(user_ids)
                for org_id, user_ids in self.org_connections.items()
            }
        }

    async def get_user_channels(self, user_id: str) -> List[str]:
        """Get channels for a specific user."""
        if user_id in self.user_connections:
            return list(self.user_connections[user_id].channels)
        return []

    async def subscribe_to_channel(self, user_id: str, channel: str):
        """Subscribe user to a new channel."""
        if user_id not in self.user_connections:
            return False

        connection_info = self.user_connections[user_id]
        if channel not in connection_info.channels:
            connection_info.channels.add(channel)
            self.connections[channel].add(connection_info.websocket)

            await self.send_to_user(user_id, {
                'type': 'channel_subscribed',
                'channel': channel
            })

            return True
        return False

    async def unsubscribe_from_channel(self, user_id: str, channel: str):
        """Unsubscribe user from a channel."""
        if user_id not in self.user_connections:
            return False

        connection_info = self.user_connections[user_id]
        if channel in connection_info.channels:
            connection_info.channels.remove(channel)
            self.connections[channel].discard(connection_info.websocket)

            await self.send_to_user(user_id, {
                'type': 'channel_unsubscribed',
                'channel': channel
            })

            return True
        return False


# Global connection pool instance
connection_pool = ConnectionPool()


# Convenience functions for common operations
async def broadcast_workflow_update(workflow_id: str, status: str, data: Dict[str, Any]):
    """Broadcast workflow status update to subscribers."""
    await connection_pool.broadcast_to_channel(
        f"workflow:{workflow_id}",
        {
            'type': 'workflow_update',
            'workflow_id': workflow_id,
            'status': status,
            'data': data
        }
    )


async def broadcast_agent_activity(org_id: str, agent_type: str, activity: str):
    """Broadcast agent activity to organization members."""
    await connection_pool.broadcast_to_organization(
        org_id,
        {
            'type': 'agent_activity',
            'agent_type': agent_type,
            'activity': activity
        }
    )


async def notify_user_message(user_id: str, message: str, source: str = 'system'):
    """Send notification message to specific user."""
    await connection_pool.send_to_user(
        user_id,
        {
            'type': 'notification',
            'message': message,
            'source': source
        }
    )