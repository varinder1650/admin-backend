from datetime import datetime
from typing import Dict, List, Set
from fastapi import WebSocket
import logging
import asyncio

logger = logging.getLogger(__name__)

class AdminConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.connection_info: Dict[WebSocket, dict] = {}
        self.subscriptions: Dict[str, Set[WebSocket]] = {}
        self.admin_views: Dict[WebSocket, Set[str]] = {}
    
    async def connect(self, websocket: WebSocket, admin_info: dict):
        self.active_connections.add(websocket)
        self.connection_info[websocket] = {
            **admin_info,
            "connected_at": datetime.utcnow().isoformat()
        }
        self.admin_views[websocket] = set()
        
        # Notify other admins
        await self.broadcast_admin_status({
            "type": "admin_connected",
            "admin": admin_info.get("name", admin_info.get("email")),
            "total_admins": len(self.active_connections)
        })
        
        logger.info(f"Admin {admin_info.get('email')} connected")
    
    def disconnect(self, websocket: WebSocket):
        info = self.connection_info.get(websocket)
        if not info:
            return
        
        # Remove from all subscriptions
        for channel, connections in self.subscriptions.items():
            connections.discard(websocket)
        
        # Remove connection info
        self.active_connections.discard(websocket)
        self.connection_info.pop(websocket, None)
        self.admin_views.pop(websocket, None)
        
        logger.info(f"Admin {info.get('email')} disconnected")
        
        # Notify other admins
        asyncio.create_task(
            self.broadcast_admin_status({
                "type": "admin_disconnected",
                "admin": info.get("name", info.get("email")),
                "total_admins": len(self.active_connections)
            })
        )
    
    async def subscribe(self, websocket: WebSocket, channel: str):
        """Subscribe admin to specific data channel"""
        if channel not in self.subscriptions:
            self.subscriptions[channel] = set()
        
        self.subscriptions[channel].add(websocket)
        if websocket in self.admin_views:
            self.admin_views[websocket].add(channel)
        
        logger.info(f"Admin subscribed to {channel}")
    
    async def unsubscribe(self, websocket: WebSocket, channel: str):
        """Unsubscribe from a channel"""
        if channel in self.subscriptions:
            self.subscriptions[channel].discard(websocket)
        
        if websocket in self.admin_views:
            self.admin_views[websocket].discard(channel)
    
    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """Send a message to a specific WebSocket connection"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.disconnect(websocket)
    
    async def broadcast_to_channel(self, channel: str, message: dict):
        """Send data to all admins subscribed to a channel"""
        if channel in self.subscriptions:
            disconnected = []
            
            for ws in self.subscriptions[channel]:
                try:
                    await ws.send_json(message)
                except:
                    disconnected.append(ws)
            
            # Clean up disconnected
            for ws in disconnected:
                self.disconnect(ws)
    
    async def broadcast_admin_status(self, message: dict):
        """Broadcast admin status to all connected admins"""
        disconnected = []
        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except:
                disconnected.append(ws)
        
        for ws in disconnected:
            self.disconnect(ws)
    
    def get_admin_stats(self):
        """Get current admin activity stats"""
        return {
            "total_admins": len(self.active_connections),
            "admins": [
                {
                    "email": info.get("email"),
                    "name": info.get("name"),
                    "connected_at": info.get("connected_at"),
                    "viewing": list(self.admin_views.get(ws, set()))
                }
                for ws, info in self.connection_info.items()
            ]
        }

# Global instance
manager = AdminConnectionManager()