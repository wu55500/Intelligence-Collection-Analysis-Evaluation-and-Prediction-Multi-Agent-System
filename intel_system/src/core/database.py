"""
数据库层 - SQLite实现
支持手机端轻量部署，WAL模式并发读取
实现任务持久化、断点恢复
"""

import sqlite3
import json
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

from .schemas import (
    TaskContract, Evidence, Claim, ForecastRecord,
    AuditLog, TaskStatus
)
from .config import get_settings


class Database:
    """SQLite数据库管理器"""
    
    def __init__(self, db_path: Optional[str] = None):
        settings = get_settings()
        self.db_path = db_path or settings.database.db_path
        
        # 确保目录存在
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self._init_tables()
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接（上下文管理器）"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        
        # WAL模式提升并发性能
        if get_settings().database.wal_mode:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(f"PRAGMA busy_timeout={get_settings().database.busy_timeout}")
        
        try:
            yield conn
            conn.commit()  # 关键：提交事务
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_tables(self):
        """初始化数据表"""
        with self.get_connection() as conn:
            # 任务表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    input_data TEXT NOT NULL,
                    input_hash TEXT NOT NULL,
                    method_version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    status TEXT NOT NULL,
                    evidence_refs TEXT,
                    error_code TEXT,
                    retryable INTEGER DEFAULT 0,
                    output_hash TEXT,
                    commitment_level TEXT DEFAULT 'C',
                    permission_level TEXT DEFAULT 'L1',
                    checkpoint TEXT
                )
            """)
            
            # 证据表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id TEXT PRIMARY KEY,
                    source_url TEXT NOT NULL,
                    source_quality TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    raw_content TEXT NOT NULL,
                    extracted_at TEXT NOT NULL,
                    credibility_score REAL NOT NULL,
                    relevance_score REAL NOT NULL,
                    diagnostic_score REAL NOT NULL,
                    is_contradictory INTEGER DEFAULT 0,
                    task_id TEXT NOT NULL,
                    claims TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)
            
            # 主张表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS claims (
                    claim_id TEXT PRIMARY KEY,
                    claim_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    commitment_level TEXT NOT NULL,
                    evidence_ids TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    falsifiable_anchor TEXT,
                    verification_suggestion TEXT,
                    sample_size INTEGER,
                    data_quality_level TEXT,
                    task_id TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)
            
            # 预测登记表 - 关键：只追加，不更新
            conn.execute("""
                CREATE TABLE IF NOT EXISTS forecasts (
                    forecast_id TEXT PRIMARY KEY,
                    event_description TEXT NOT NULL,
                    probability REAL NOT NULL,
                    time_range_start TEXT NOT NULL,
                    time_range_end TEXT NOT NULL,
                    falsifiable_anchor TEXT NOT NULL,
                    premises TEXT NOT NULL,
                    registered_at TEXT NOT NULL,
                    settled INTEGER DEFAULT 0,
                    settled_at TEXT,
                    outcome TEXT,
                    brier_score REAL,
                    evidence_snapshot TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)
            
            # 审计日志表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    log_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    details TEXT NOT NULL,
                    task_id TEXT,
                    commitment_change TEXT
                )
            """)
            
            # 索引优化
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_task ON evidence(task_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_claims_task ON claims(task_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_forecasts_task ON forecasts(task_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_forecasts_settled ON forecasts(settled)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_task ON audit_logs(task_id)")
    
    # ========== 任务操作 ==========
    
    def save_task(self, task: TaskContract) -> str:
        """保存或更新任务"""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO tasks (
                    task_id, task_type, input_data, input_hash, method_version,
                    created_at, started_at, completed_at, status, evidence_refs,
                    error_code, retryable, output_hash, commitment_level,
                    permission_level, checkpoint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.task_id,
                task.task_type,
                json.dumps(task.input_data, ensure_ascii=False),
                task.input_hash,
                task.method_version,
                task.created_at.isoformat(),
                task.started_at.isoformat() if task.started_at else None,
                task.completed_at.isoformat() if task.completed_at else None,
                task.status.value,
                json.dumps(task.evidence_refs),
                task.error_code,
                1 if task.retryable else 0,
                task.output_hash,
                task.commitment_level.value,
                task.permission_level.value,
                None  # checkpoint
            ))
            return task.task_id
    
    def get_task(self, task_id: str) -> Optional[TaskContract]:
        """获取任务"""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            
            if not row:
                return None
            
            return TaskContract(
                task_id=row["task_id"],
                task_type=row["task_type"],
                input_data=json.loads(row["input_data"]),
                input_hash=row["input_hash"],
                method_version=row["method_version"],
                created_at=datetime.fromisoformat(row["created_at"]),
                started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
                completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                status=TaskStatus(row["status"]),
                evidence_refs=json.loads(row["evidence_refs"] or "[]"),
                error_code=row["error_code"],
                retryable=bool(row["retryable"]),
                output_hash=row["output_hash"],
                commitment_level=row["commitment_level"],
                permission_level=row["permission_level"]
            )
    
    def update_task_status(self, task_id: str, status: TaskStatus, **kwargs):
        """更新任务状态"""
        with self.get_connection() as conn:
            updates = ["status = ?"]
            values = [status.value]
            
            if "completed_at" in kwargs:
                updates.append("completed_at = ?")
                values.append(kwargs["completed_at"].isoformat())
            
            if "error_code" in kwargs:
                updates.append("error_code = ?")
                values.append(kwargs["error_code"])
            
            if "output_hash" in kwargs:
                updates.append("output_hash = ?")
                values.append(kwargs["output_hash"])
            
            values.append(task_id)
            
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE task_id = ?",
                values
            )
    
    def get_pending_tasks(self, limit: int = 10) -> List[TaskContract]:
        """获取待处理任务"""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at LIMIT ?",
                (TaskStatus.PENDING.value, limit)
            ).fetchall()
            
            return [
                TaskContract(
                    task_id=row["task_id"],
                    task_type=row["task_type"],
                    input_data=json.loads(row["input_data"]),
                    input_hash=row["input_hash"],
                    method_version=row["method_version"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
                    completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                    status=TaskStatus(row["status"]),
                    evidence_refs=json.loads(row["evidence_refs"] or "[]"),
                    error_code=row["error_code"],
                    retryable=bool(row["retryable"]),
                    output_hash=row["output_hash"],
                    commitment_level=row["commitment_level"],
                    permission_level=row["permission_level"]
                )
                for row in rows
            ]
    
    # ========== 证据操作 ==========
    
    def save_evidence(self, evidence: Evidence) -> str:
        """保存证据"""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO evidence (
                    evidence_id, source_url, source_quality, content_hash,
                    raw_content, extracted_at, credibility_score, relevance_score,
                    diagnostic_score, is_contradictory, task_id, claims
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                evidence.evidence_id,
                evidence.source_url,
                evidence.source_quality.value,
                evidence.content_hash,
                evidence.raw_content,
                evidence.extracted_at.isoformat(),
                evidence.credibility_score,
                evidence.relevance_score,
                evidence.diagnostic_score,
                1 if evidence.is_contradictory else 0,
                evidence.task_id,
                json.dumps(evidence.claims)
            ))
            return evidence.evidence_id
    
    def get_evidence_by_task(self, task_id: str) -> List[Evidence]:
        """获取任务相关的所有证据"""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM evidence WHERE task_id = ?", (task_id,)
            ).fetchall()
            
            return [
                Evidence(
                    evidence_id=row["evidence_id"],
                    source_url=row["source_url"],
                    source_quality=row["source_quality"],
                    content_hash=row["content_hash"],
                    raw_content=row["raw_content"],
                    extracted_at=datetime.fromisoformat(row["extracted_at"]),
                    credibility_score=row["credibility_score"],
                    relevance_score=row["relevance_score"],
                    diagnostic_score=row["diagnostic_score"],
                    is_contradictory=bool(row["is_contradictory"]),
                    task_id=row["task_id"],
                    claims=json.loads(row["claims"] or "[]")
                )
                for row in rows
            ]
    
    # ========== 预测操作 ==========
    
    def register_forecast(self, forecast: ForecastRecord) -> str:
        """
        登记预测 - 只追加，不更新
        关键：保证预测不可被覆盖
        """
        with self.get_connection() as conn:
            # 检查是否已存在
            existing = conn.execute(
                "SELECT forecast_id FROM forecasts WHERE forecast_id = ?",
                (forecast.forecast_id,)
            ).fetchone()
            
            if existing:
                raise ValueError(f"预测 {forecast.forecast_id} 已存在，不可覆盖")
            
            conn.execute("""
                INSERT INTO forecasts (
                    forecast_id, event_description, probability, time_range_start,
                    time_range_end, falsifiable_anchor, premises, registered_at,
                    settled, settled_at, outcome, brier_score, evidence_snapshot, task_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                forecast.forecast_id,
                forecast.event_description,
                forecast.probability,
                forecast.time_range_start.isoformat(),
                forecast.time_range_end.isoformat(),
                forecast.falsifiable_anchor,
                json.dumps(forecast.premises, ensure_ascii=False),
                forecast.registered_at.isoformat(),
                1 if forecast.settled else 0,
                forecast.settled_at.isoformat() if forecast.settled_at else None,
                forecast.outcome,
                forecast.brier_score,
                json.dumps(forecast.evidence_snapshot, ensure_ascii=False),
                forecast.task_id
            ))
            return forecast.forecast_id
    
    def settle_forecast(
        self,
        forecast_id: str,
        outcome: str,
        brier_score: Optional[float] = None
    ):
        """结算预测"""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE forecasts 
                SET settled = 1, settled_at = ?, outcome = ?, brier_score = ?
                WHERE forecast_id = ?
            """, (
                datetime.now().isoformat(),
                outcome,
                brier_score,
                forecast_id
            ))
    
    def get_unsettled_forecasts(self) -> List[ForecastRecord]:
        """获取未结算的预测"""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM forecasts WHERE settled = 0"
            ).fetchall()
            
            return [
                ForecastRecord(
                    forecast_id=row["forecast_id"],
                    event_description=row["event_description"],
                    probability=row["probability"],
                    time_range_start=datetime.fromisoformat(row["time_range_start"]),
                    time_range_end=datetime.fromisoformat(row["time_range_end"]),
                    falsifiable_anchor=row["falsifiable_anchor"],
                    premises=json.loads(row["premises"]),
                    registered_at=datetime.fromisoformat(row["registered_at"]),
                    settled=bool(row["settled"]),
                    settled_at=datetime.fromisoformat(row["settled_at"]) if row["settled_at"] else None,
                    outcome=row["outcome"],
                    brier_score=row["brier_score"],
                    evidence_snapshot=json.loads(row["evidence_snapshot"]),
                    task_id=row["task_id"]
                )
                for row in rows
            ]
    
    # ========== 审计日志 ==========
    
    def log_audit(self, audit: AuditLog) -> str:
        """记录审计日志"""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO audit_logs (
                    log_id, timestamp, action, actor, details, task_id, commitment_change
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                audit.log_id,
                audit.timestamp.isoformat(),
                audit.action,
                audit.actor,
                json.dumps(audit.details, ensure_ascii=False),
                audit.task_id,
                json.dumps(audit.commitment_change, ensure_ascii=False) if audit.commitment_change else None
            ))
            return audit.log_id
    
    def get_audit_logs(self, task_id: Optional[str] = None, limit: int = 100) -> List[AuditLog]:
        """获取审计日志"""
        with self.get_connection() as conn:
            if task_id:
                rows = conn.execute(
                    "SELECT * FROM audit_logs WHERE task_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (task_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            
            return [
                AuditLog(
                    log_id=row["log_id"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    action=row["action"],
                    actor=row["actor"],
                    details=json.loads(row["details"]),
                    task_id=row["task_id"],
                    commitment_change=json.loads(row["commitment_change"]) if row["commitment_change"] else None
                )
                for row in rows
            ]


# 全局数据库实例
_db: Optional[Database] = None

def get_database(db_path: Optional[str] = None) -> Database:
    global _db
    if _db is None:
        _db = Database(db_path)
    return _db
