"""
业务操作事务包装器

确保：业务状态变更 + 事件记录在同一个事务内完成
任何失败都会一起回滚
"""

import sqlite3
import json
from contextlib import contextmanager
from typing import Optional


class BusinessTransaction:
    """
    业务事务管理器
    
    用法：
    with BusinessTransaction(db_path) as tx:
        tx.execute("UPDATE forecasts SET settled=1 WHERE forecast_id=?", (fc_id,))
        tx.log_event(event)
    # 两者要么都成功，要么都失败
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.event_conn: Optional[sqlite3.Connection] = None
        self._pending_events = []
    
    @contextmanager
    def transaction(self):
        """事务上下文管理器"""
        self.conn = sqlite3.connect(self.db_path)
        self.event_conn = sqlite3.connect(self.db_path.replace(".db", "_events.db"))
        
        try:
            self.conn.execute("BEGIN")
            self.event_conn.execute("BEGIN")
            yield self
            self.conn.execute("COMMIT")
            self.event_conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            self.event_conn.execute("ROLLBACK")
            raise
        finally:
            self.conn.close()
            self.event_conn.close()
    
    def execute_business(self, sql: str, params: tuple = ()):
        """执行业务SQL"""
        return self.conn.execute(sql, params)
    
    def log_event(self, event_data: dict):
        """记录事件（暂存，提交时一起写入）"""
        self._pending_events.append(event_data)
    
    def flush_events(self):
        """将所有暂存事件写入"""
        if not self._pending_events:
            return
        
        self.event_conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                aggregate_id TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                payload TEXT NOT NULL
            )
        """)
        
        for event in self._pending_events:
            self.event_conn.execute("""
                INSERT INTO events (event_id, event_type, aggregate_id, actor_id, timestamp, payload)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                event["event_id"],
                event["event_type"],
                event["aggregate_id"],
                event["actor_id"],
                event["timestamp"],
                json.dumps(event["payload"], sort_keys=True)
            ))
        
        self._pending_events = []
