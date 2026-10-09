"""
WebSocket 处理器
集成到 FastAPI 应用
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
import json

from ..infra.websocket import get_ws_manager, WebSocketMessage

router = APIRouter()


class ConnectionManager:
    """连接管理器"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.ws_manager = get_ws_manager()
    
    async def connect(self, websocket: WebSocket, client_id: str, channels: List[str] = None):
        """连接WebSocket"""
        await websocket.accept()
        self.active_connections.append(websocket)
        await self.ws_manager.connect(websocket, client_id, channels)
    
    def disconnect(self, websocket: WebSocket):
        """断开连接"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)


manager = ConnectionManager()


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str, channels: str = "general"):
    """WebSocket端点"""
    channel_list = channels.split(",")
    await manager.connect(websocket, client_id, channel_list)
    
    try:
        while True:
            data = await websocket.receive_text()
            # 处理客户端消息
            message = json.loads(data)
            
            # 可以处理客户端发送的命令
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.ws_manager.disconnect(client_id)


@router.get("/ws/status")
async def websocket_status():
    """WebSocket状态"""
    ws_manager = get_ws_manager()
    return {
        "connected_clients": ws_manager.get_connected_clients(),
        "channels": {
            "general": ws_manager.get_connected_clients("general"),
            "alerts": ws_manager.get_connected_clients("alerts"),
            "tasks": ws_manager.get_connected_clients("tasks")
        }
    }
