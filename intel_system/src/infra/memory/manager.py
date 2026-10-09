"""
Agent 记忆系统
支持三种记忆：短期记忆、长期记忆、工作记忆
用于 Agent 学习和上下文管理
"""

import sqlite3
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import uuid


@dataclass
class Memory:
    """记忆基类"""
    memory_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    importance: float = 0.5  # 0-1
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)


@dataclass
class ShortTermMemory(Memory):
    """
    短期记忆
    - 容量有限（最近N条）
    - 自动遗忘
    - 用于当前对话上下文
    """
    ttl_minutes: int = 30
    session_id: str = ""


@dataclass
class LongTermMemory(Memory):
    """
    长期记忆
    - 持久化存储
    - 基于重要性保留
    - 用于知识积累
    """
    category: str = "general"  # fact, skill, experience, preference
    tags: List[str] = field(default_factory=list)


@dataclass
class WorkingMemory(Memory):
    """
    工作记忆
    - 当前任务的临时存储
    - 任务完成后归档或删除
    - 用于多步骤推理
    """
    task_id: str = ""
    step: str = ""


class MemoryManager:
    """
    记忆管理器

    实现三种记忆的存储、检索、遗忘机制
    """

    def __init__(self, db_path: str = "data/memory.db"):
        self.db_path = db_path
        self._init_db()
        self._short_term_buffer: List[ShortTermMemory] = []
        self._working_memory_cache: Dict[str, WorkingMemory] = {}

    def _init_db(self):
        """初始化记忆数据库"""
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS long_term_memory (
                memory_id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                category TEXT NOT NULL,
                tags TEXT,
                importance REAL DEFAULT 0.5,
                access_count INTEGER DEFAULT 0,
                metadata TEXT,
                created_at TEXT NOT NULL,
                last_accessed TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_category
            ON long_term_memory(category)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_importance
            ON long_term_memory(importance DESC)
        """)
        conn.commit()
        conn.close()

    # ===== 短期记忆 =====

    def add_short_term(self, content: str, session_id: str, 
                      importance: float = 0.5, ttl_minutes: int = 30) -> ShortTermMemory:
        """添加短期记忆"""
        memory = ShortTermMemory(
            content=content,
            session_id=session_id,
            importance=importance,
            ttl_minutes=ttl_minutes
        )
        self._short_term_buffer.append(memory)
        self._cleanup_short_term()
        return memory

    def get_short_term(self, session_id: str, limit: int = 10) -> List[ShortTermMemory]:
        """获取短期记忆"""
        self._cleanup_short_term()
        memories = [m for m in self._short_term_buffer if m.session_id == session_id]
        memories.sort(key=lambda x: x.created_at, reverse=True)
        return memories[:limit]

    def _cleanup_short_term(self):
        """清理过期的短期记忆"""
        now = datetime.now()
        self._short_term_buffer = [
            m for m in self._short_term_buffer
            if (now - m.created_at).total_seconds() < m.ttl_minutes * 60
        ]

    # ===== 长期记忆 =====

    def add_long_term(self, content: str, category: str, 
                     tags: List[str] = None, importance: float = 0.5) -> LongTermMemory:
        """添加长期记忆"""
        memory = LongTermMemory(
            content=content,
            category=category,
            tags=tags or [],
            importance=importance
        )

        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO long_term_memory
            (memory_id, content, category, tags, importance, access_count, metadata, created_at, last_accessed)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
        """, (
            memory.memory_id,
            memory.content,
            memory.category,
            json.dumps(memory.tags),
            memory.importance,
            json.dumps(memory.metadata, ensure_ascii=False),
            memory.created_at.isoformat(),
            memory.last_accessed.isoformat()
        ))
        conn.commit()
        conn.close()
        return memory

    def search_long_term(self, category: Optional[str] = None, 
                        tags: Optional[List[str]] = None,
                        limit: int = 10) -> List[LongTermMemory]:
        """检索长期记忆"""
        conn = sqlite3.connect(self.db_path)

        query = "SELECT * FROM long_term_memory"
        conditions = []
        params = []

        if category:
            conditions.append("category = ?")
            params.append(category)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY importance DESC, last_accessed DESC LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        memories = []

        for row in cursor:
            memory = LongTermMemory(
                memory_id=row[0],
                content=row[1],
                category=row[2],
                tags=json.loads(row[3]) if row[3] else [],
                importance=row[4],
                access_count=row[5],
                metadata=json.loads(row[6]) if row[6] else {},
                created_at=datetime.fromisoformat(row[7]),
                last_accessed=datetime.fromisoformat(row[8])
            )

            # 过滤tags
            if tags:
                if not any(tag in memory.tags for tag in tags):
                    continue

            memories.append(memory)

        conn.close()

        # 更新访问次数
        self._update_access_count([m.memory_id for m in memories])

        return memories

    def _update_access_count(self, memory_ids: List[str]):
        """更新访问次数和时间"""
        if not memory_ids:
            return

        conn = sqlite3.connect(self.db_path)
        now = datetime.now().isoformat()
        placeholders = ','.join('?' * len(memory_ids))
        conn.execute(f"""
            UPDATE long_term_memory
            SET access_count = access_count + 1, last_accessed = ?
            WHERE memory_id IN ({placeholders})
        """, [now] + memory_ids)
        conn.commit()
        conn.close()

    # ===== 工作记忆 =====

    def set_working(self, task_id: str, step: str, content: str) -> WorkingMemory:
        """设置工作记忆"""
        if task_id not in self._working_memory_cache:
            self._working_memory_cache[task_id] = WorkingMemory(task_id=task_id)

        memory = self._working_memory_cache[task_id]
        memory.step = step
        memory.content = content
        return memory

    def get_working(self, task_id: str) -> Optional[WorkingMemory]:
        """获取工作记忆"""
        return self._working_memory_cache.get(task_id)

    def clear_working(self, task_id: str):
        """清除工作记忆（任务完成后调用）"""
        self._working_memory_cache.pop(task_id, None)

    # ===== 记忆整合 =====

    def consolidate_memories(self, session_id: str) -> int:
        """
        整合记忆：将重要的短期记忆转为长期记忆
        返回归档的数量
        """
        short_memories = self.get_short_term(session_id, limit=100)
        archived_count = 0

        for memory in short_memories:
            if memory.importance >= 0.7:  # 高重要性归档
                self.add_long_term(
                    content=memory.content,
                    category="experience",
                    importance=memory.importance,
                    tags=["auto-archived", session_id]
                )
                archived_count += 1

        return archived_count

    def forget_old_memories(self, keep_count: int = 1000):
        """遗忘低重要性的旧记忆（保留最重要的N条）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT memory_id FROM long_term_memory
            ORDER BY importance DESC, last_accessed DESC
            LIMIT ?
        """, (keep_count,))
        keep_ids = [row[0] for row in cursor]

        if keep_ids:
            placeholders = ','.join('?' * len(keep_ids))
            conn.execute(f"""
                DELETE FROM long_term_memory
                WHERE memory_id NOT IN ({placeholders})
            """, keep_ids)
            conn.commit()

        conn.close()

    def get_memory_stats(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT category, COUNT(*), AVG(importance)
            FROM long_term_memory
            GROUP BY category
        """)
        stats = {row[0]: {"count": row[1], "avg_importance": row[2]} for row in cursor}
        conn.close()

        return {
            "long_term": stats,
            "short_term": len(self._short_term_buffer),
            "working": len(self._working_memory_cache)
        }
