"""
WebSocket module
Manages WebSocket connections for live log streaming
"""
from typing import List
from collections import deque
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections for live log streaming"""

    def __init__(self, history_size: int = 20):
        self.active_connections: List[WebSocket] = []
        self.log_history: deque = deque(maxlen=history_size)  # Circular buffer for last N messages

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection and send history"""
        from datetime import datetime

        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

        # Send connection message first
        try:
            await websocket.send_text(
                f"{datetime.utcnow().isoformat()}Z - Connected - showing last {len(self.log_history)} log entries..."
            )
        except Exception as e:
            logger.error(f"Error sending connection message: {e}")

        # Then send recent log history to new client
        if self.log_history:
            for historical_message in self.log_history:
                try:
                    await websocket.send_text(historical_message)
                except Exception as e:
                    logger.error(f"Error sending history to WebSocket client: {e}")

    def disconnect(self, websocket: WebSocket):
        """Unregister a WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        """
        Broadcast message to all connected WebSocket clients and store in history

        Args:
            message: Log line or event message to broadcast
        """
        # Store in history (automatically removes oldest if full)
        self.log_history.append(message)

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
