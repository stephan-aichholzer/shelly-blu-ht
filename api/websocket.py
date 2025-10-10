"""
WebSocket module
Manages WebSocket connections for live log streaming
"""
from typing import List
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections for live log streaming"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Unregister a WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        """
        Broadcast message to all connected WebSocket clients

        Args:
            message: Log line or event message to broadcast
        """
        # Copy list to avoid modification during iteration
        for connection in self.active_connections[:]:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket client: {e}")
                # Remove failed connection
                try:
                    self.active_connections.remove(connection)
                except ValueError:
                    pass  # Already removed


# Global singleton instance
ws_manager = WebSocketManager()
