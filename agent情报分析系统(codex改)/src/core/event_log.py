"""
事件日志模块 - 完整审计链

确保：
1. 每个关键状态变更都产生事件
2. 业务状态和事件日志在同一事务内更新
3. 事件不可篡改（追加式，带哈希链）
"""

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class EventType(str, Enum):
    """事件类型"""
    TASK_CREATED = "task.created"
    TASK_UPDATED = "task.updated"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    FORECAST_REGISTERED = "forecast.registered"
    FORECAST_SETTLED = "forecast.settled"
    PERMISSION_GRANTED = "permission.granted"
    PERMISSION_REVOKED = "permission.revoked"
    CHECKPOINT_CREATED = "checkpoint.created"
    CHECKPOINT_UPDATED = "checkpoint.updated"
    VALIDATION_PASSED = "validation.passed"
    VALIDATION_FAILED = "validation.failed"
    RED_TEAM_BLOCKED = "red_team.blocked"


@dataclass
class Event:
    """事件记录"""
    event_id: str
    event_type: EventType
    aggregate_id: str  # 关联的业务实体ID（task_id, forecast_id等）
    actor_id: str  # 执行者（user, system, agent）
    timestamp: datetime
    before_hash: Optional[str] = None  # 变更前哈希
    after_hash: Optional[str] = None   # 变更后哈希
    correlation_id: Optional[str] = None  # 关联多个相关事件
    schema_version: str = "1.0"
    payload: Dict[str, Any] = field(default_factory=dict)
    previous_event_hash: Optional[str] = None  # 哈希链：指向前一个事件


class EventStore:
    """
    事件存储
    
    特性：
    1. 追加式写入，不可修改
    2. 哈希链保证完整性
    3. 支持按aggregate_id查询
    """
    
    def __init__(self, db_path: str = "data/events.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                aggregate_id TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                before_hash TEXT,
                after_hash TEXT,
                correlation_id TEXT,
                schema_version TEXT NOT NULL,
                payload TEXT NOT NULL,
                previous_event_hash TEXT,
                event_hash TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_aggregate 
            ON events(aggregate_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_type 
            ON events(event_type)
        """)
        conn.commit()
        conn.close()
    
    def _compute_hash(self, event: Event) -> str:
        """计算事件哈希"""
        data = f"{event.event_id}{event.event_type}{event.aggregate_id}{event.timestamp.isoformat()}{json.dumps(event.payload, sort_keys=True)}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def _get_last_event_hash(self) -> Optional[str]:
        """获取最后一个事件的哈希"""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT event_hash FROM events ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return row[0] if row else None
    
    def append_event(self, event: Event) -> str:
        """
        追加事件
        
        返回：事件哈希
        """
        # 设置前一个事件的哈希（哈希链）
        event.previous_event_hash = self._get_last_event_hash()
        
        # 计算当前事件哈希
        event_hash = self._compute_hash(event)
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO events (
                event_id, event_type, aggregate_id, actor_id, timestamp,
                before_hash, after_hash, correlation_id, schema_version,
                payload, previous_event_hash, event_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.event_id,
            event.event_type.value,
            event.aggregate_id,
            event.actor_id,
            event.timestamp.isoformat(),
            event.before_hash,
            event.after_hash,
            event.correlation_id,
            event.schema_version,
            json.dumps(event.payload, sort_keys=True),
            event.previous_event_hash,
            event_hash
        ))
        conn.commit()
        conn.close()
        
        return event_hash
    
    def get_events_by_aggregate(self, aggregate_id: str) -> List[Event]:
        """获取实体的所有事件"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT * FROM events WHERE aggregate_id = ? ORDER BY timestamp",
            (aggregate_id,)
        ).fetchall()
        conn.close()
        
        return [self._row_to_event(row) for row in rows]
    
    def get_events_by_type(self, event_type: EventType) -> List[Event]:
        """获取特定类型的事件"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT * FROM events WHERE event_type = ? ORDER BY timestamp DESC LIMIT 100",
            (event_type.value,)
        ).fetchall()
        conn.close()
        
        return [self._row_to_event(row) for row in rows]
    
    def verify_integrity(self) -> bool:
        """
        验证哈希链完整性
        
        返回：True 如果链完整
        """
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT * FROM events ORDER BY timestamp"
        ).fetchall()
        conn.close()
        
        if not rows:
            return True
        
        events = [self._row_to_event(row) for row in rows]
        
        for i, event in enumerate(events):
            expected_hash = self._compute_hash(event)
            stored_hash = conn.execute(
                "SELECT event_hash FROM events WHERE event_id = ?",
                (event.event_id,)
            ).fetchone()[0]
            
            if expected_hash != stored_hash:
                return False
            
            if i > 0:
                if event.previous_event_hash != events[i-1]._compute_hash():
                    return False
        
        return True
    
    def _row_to_event(self, row) -> Event:
        """数据库行转Event对象"""
        return Event(
            event_id=row[0],
            event_type=EventType(row[1]),
            aggregate_id=row[2],
            actor_id=row[3],
            timestamp=datetime.fromisoformat(row[4]),
            before_hash=row[5],
            after_hash=row[6],
            correlation_id=row[7],
            schema_version=row[8],
            payload=json.loads(row[9]),
            previous_event_hash=row[10]
        )


# 全局实例
_event_store: Optional[EventStore] = None

def get_event_store(db_path: Optional[str] = None) -> EventStore:
    global _event_store
    if _event_store is None:
        _event_store = EventStore(db_path or "data/events.db")
    return _event_store
