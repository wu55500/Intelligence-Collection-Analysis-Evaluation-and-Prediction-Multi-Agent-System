"""
WebSocket 实时推送管理器
支持任务状态更新、告警通知、进度推送
"""

import asyncio
import json
from typing import Set, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
import uuid


@dataclass
class WebSocketMessage:
    """WebSocket 消息"""
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    msg_type: str = "info"  # info, alert, progress, error
    channel: str = "general"
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_json(self) -> str:
        return json.dumps({
            "msg_id": self.msg_id,
            "type": self.msg_type,
            "channel": self.channel,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        }, ensure_ascii=False)


class WebSocketManager:
    """
    WebSocket 连接管理器

    支持：
    - 多客户端连接
    - 频道订阅
    - 消息广播
    - 点对点推送
    """

    def __init__(self):
        self._connections: Dict[str, Set] = {}  # channel -> set of websocket
        self._client_info: Dict[str, Dict] = {}  # client_id -> info

    async def connect(self, websocket, client_id: str, channels: Optional[list] = None):
        """客户端连接"""
        channels = channels or ["general"]

        for channel in channels:
            if channel not in self._connections:
                self._connections[channel] = set()
            self._connections[channel].add(websocket)

        self._client_info[client_id] = {
            "websocket": websocket,
            "channels": channels,
            "connected_at": datetime.now()
        }

    async def disconnect(self, client_id: str):
        """客户端断开"""
        info = self._client_info.pop(client_id, None)
        if info:
            for channel in info["channels"]:
                if channel in self._connections:
                    self._connections[channel].discard(info["websocket"])

    async def broadcast(self, message: WebSocketMessage):
        """广播消息到指定频道"""
        channel = message.channel
        if channel not in self._connections:
            return

        disconnected = set()
        for websocket in self._connections[channel]:
            try:
                await websocket.send_text(message.to_json())
            except Exception:
                disconnected.add(websocket)

        for ws in disconnected:
            self._connections[channel].discard(ws)

    async def send_to_client(self, client_id: str, message: WebSocketMessage):
        """发送消息到指定客户端"""
        info = self._client_info.get(client_id)
        if not info:
            return

        try:
            await info["websocket"].send_text(message.to_json())
        except Exception:
            await self.disconnect(client_id)

    async def send_progress(self, channel: str, task_id: str, progress: float, step: str = ""):
        """发送进度更新"""
        msg = WebSocketMessage(
            msg_type="progress",
            channel=channel,
            data={
                "task_id": task_id,
                "progress": progress,
                "step": step,
                "percent": f"{progress * 100:.1f}%"
            }
        )
        await self.broadcast(msg)

    async def send_alert(self, channel: str, alert_type: str, content: str, severity: str = "warning"):
        """发送告警"""
        msg = WebSocketMessage(
            msg_type="alert",
            channel=channel,
            data={
                "alert_type": alert_type,
                "content": content,
                "severity": severity,
                "timestamp": datetime.now().isoformat()
            }
        )
        await self.broadcast(msg)

    async def send_task_update(self, channel: str, task_id: str, status: str, details: Dict = None):
        """发送任务状态更新"""
        msg = WebSocketMessage(
            msg_type="info",
            channel=channel,
            data={
                "task_id": task_id,
                "status": status,
                "details": details or {},
                "timestamp": datetime.now().isoformat()
            }
        )
        await self.broadcast(msg)

    def get_connected_clients(self, channel: Optional[str] = None) -> int:
        """获取连接的客户端数"""
        if channel:
            return len(self._connections.get(channel, set()))
        return len(self._client_info)


# 全局实例
_ws_manager: Optional[WebSocketManager] = None

def get_ws_manager() -> WebSocketManager:
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager
