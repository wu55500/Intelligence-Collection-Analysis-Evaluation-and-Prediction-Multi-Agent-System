"""
持久化检查点服务 (L4 数据与基础设施层)

支持任务恢复、断点续传、状态持久化
任何环节中断可恢复，重要信源无遗漏
"""

import json
import sqlite3
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid
import os


class CheckpointStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RECOVERED = "recovered"


@dataclass
class Checkpoint:
    """检查点"""
    checkpoint_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    step_name: str = ""
    status: CheckpointStatus = CheckpointStatus.PENDING
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    module_version: str = "1.0"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    error_message: str = ""
    retry_count: int = 0
    max_retries: int = 3


class CheckpointService:
    """
    检查点服务
    
    支持：
    - 任务状态持久化
    - 断点恢复
    - 重试管理
    - 历史追溯
    """
    
    def __init__(self, db_path: str = "data/checkpoints.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                step_name TEXT NOT NULL,
                status TEXT NOT NULL,
                input_data TEXT,
                output_data TEXT,
                module_version TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                UNIQUE(task_id, step_name)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_task ON checkpoints(task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_task_step ON checkpoints(task_id, step_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON checkpoints(status)")
        conn.commit()
        conn.close()
    
    def save_checkpoint(self, checkpoint: Checkpoint) -> str:
        """保存检查点（幂等：同一task_id+step_name会覆盖）"""
        checkpoint.updated_at = datetime.now()
        
        conn = sqlite3.connect(self.db_path)
        
        # 查找是否已存在同task_id+step_name的检查点
        existing = conn.execute(
            "SELECT checkpoint_id FROM checkpoints WHERE task_id = ? AND step_name = ?",
            (checkpoint.task_id, checkpoint.step_name)
        ).fetchone()
        
        if existing:
            # 复用已有的checkpoint_id，实现幂等覆盖
            checkpoint.checkpoint_id = existing[0]
        
        conn.execute("""
            INSERT OR REPLACE INTO checkpoints
            (checkpoint_id, task_id, step_name, status, input_data, output_data,
             module_version, created_at, updated_at, error_message, retry_count, max_retries)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            checkpoint.checkpoint_id,
            checkpoint.task_id,
            checkpoint.step_name,
            checkpoint.status.value,
            json.dumps(checkpoint.input_data, ensure_ascii=False, default=str),
            json.dumps(checkpoint.output_data, ensure_ascii=False, default=str),
            checkpoint.module_version,
            checkpoint.created_at.isoformat(),
            checkpoint.updated_at.isoformat(),
            checkpoint.error_message,
            checkpoint.retry_count,
            checkpoint.max_retries
        ))
        conn.commit()
        conn.close()
        return checkpoint.checkpoint_id
    
    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """获取检查点"""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT * FROM checkpoints WHERE checkpoint_id = ?",
            (checkpoint_id,)
        ).fetchone()
        conn.close()
        
        if row:
            return self._row_to_checkpoint(row)
        return None
    
    def get_task_checkpoints(self, task_id: str) -> List[Checkpoint]:
        """获取任务的所有检查点"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT * FROM checkpoints WHERE task_id = ? ORDER BY created_at",
            (task_id,)
        ).fetchall()
        conn.close()
        
        return [self._row_to_checkpoint(row) for row in rows]
    
    def get_last_completed_step(self, task_id: str) -> Optional[Checkpoint]:
        """获取任务最后完成的步骤"""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("""
            SELECT * FROM checkpoints
            WHERE task_id = ? AND status = 'completed'
            ORDER BY updated_at DESC LIMIT 1
        """, (task_id,)).fetchone()
        conn.close()
        
        if row:
            return self._row_to_checkpoint(row)
        return None
    
    def get_failed_steps(self, task_id: str) -> List[Checkpoint]:
        """获取失败的步骤"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT * FROM checkpoints WHERE task_id = ? AND status = 'failed'",
            (task_id,)
        ).fetchall()
        conn.close()
        
        return [self._row_to_checkpoint(row) for row in rows]
    
    def mark_completed(self, checkpoint_id: str, output_data: Dict[str, Any]) -> bool:
        """标记完成"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            UPDATE checkpoints
            SET status = 'completed', output_data = ?, updated_at = ?
            WHERE checkpoint_id = ?
        """, (
            json.dumps(output_data, ensure_ascii=False, default=str),
            datetime.now().isoformat(),
            checkpoint_id
        ))
        conn.commit()
        changed = conn.total_changes > 0
        conn.close()
        return changed
    
    def mark_failed(self, checkpoint_id: str, error: str) -> bool:
        """标记失败"""
        cp = self.get_checkpoint(checkpoint_id)
        if not cp:
            return False
        
        cp.retry_count += 1
        
        if cp.retry_count >= cp.max_retries:
            status = "failed"
        else:
            status = "in_progress"
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            UPDATE checkpoints
            SET status = ?, error_message = ?, retry_count = ?, updated_at = ?
            WHERE checkpoint_id = ?
        """, (status, error, cp.retry_count, datetime.now().isoformat(), checkpoint_id))
        conn.commit()
        conn.close()
        return True
    
    def can_retry(self, checkpoint_id: str) -> bool:
        """检查是否可以重试"""
        cp = self.get_checkpoint(checkpoint_id)
        if not cp:
            return False
        return cp.retry_count < cp.max_retries
    
    def _row_to_checkpoint(self, row) -> Checkpoint:
        """数据库行转Checkpoint对象"""
        return Checkpoint(
            checkpoint_id=row[0],
            task_id=row[1],
            step_name=row[2],
            status=CheckpointStatus(row[3]),
            input_data=json.loads(row[4]) if row[4] else {},
            output_data=json.loads(row[5]) if row[5] else {},
            module_version=row[6] or "1.0",
            created_at=datetime.fromisoformat(row[7]),
            updated_at=datetime.fromisoformat(row[8]),
            error_message=row[9] or "",
            retry_count=row[10],
            max_retries=row[11]
        )
    
    def get_recovery_info(self, task_id: str) -> Dict[str, Any]:
        """获取恢复信息"""
        checkpoints = self.get_task_checkpoints(task_id)
        completed = [c for c in checkpoints if c.status == CheckpointStatus.COMPLETED]
        failed = [c for c in checkpoints if c.status == CheckpointStatus.FAILED]
        pending = [c for c in checkpoints if c.status == CheckpointStatus.PENDING]
        
        return {
            "task_id": task_id,
            "total_steps": len(checkpoints),
            "completed": len(completed),
            "failed": len(failed),
            "pending": len(pending),
            "last_completed": completed[-1].step_name if completed else None,
            "can_resume": len(failed) == 0 or any(self.can_retry(f.checkpoint_id) for f in failed),
            "failed_steps": [f.step_name for f in failed]
        }
