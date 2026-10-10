"""
Redis 缓存层
支持查询缓存、会话状态、速率限制
兼容 Redis 不可用时的内存回退
"""

import json
import hashlib
import time
from typing import Optional, Any, Dict, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import OrderedDict


@dataclass
class CacheEntry:
    key: str
    value: Any
    ttl: float
    created_at: float = field(default_factory=time.time)

    @property
    def expired(self) -> bool:
        return time.time() - self.created_at > self.ttl


class MemoryCacheBackend:
    """内存缓存回退（Redis不可用时使用）"""

    def __init__(self, max_size: int = 1000):
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.expired:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return entry.value

    def set(self, key: str, value: Any, ttl: float = 300) -> None:
        if key in self._store:
            del self._store[key]
        elif len(self._store) >= self._max_size:
            self._store.popitem(last=False)
        self._store[key] = CacheEntry(key=key, value=value, ttl=ttl)

    def delete(self, key: str) -> bool:
        return self._store.pop(key, None) is not None

    def flush(self) -> None:
        self._store.clear()

    def keys(self, pattern: str = "*") -> List[str]:
        return list(self._store.keys())


class RedisClient:
    """
    Redis 客户端（带内存回退）

    优先级：redis-py → 内存缓存
    所有方法接口一致，调用方无感知
    """

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0,
                 password: Optional[str] = None, fallback_to_memory: bool = True):
        self._redis = None
        self._memory = MemoryCacheBackend()
        self._using_memory = False

        try:
            import redis
            self._redis = redis.Redis(
                host=host, port=port, db=db, password=password,
                decode_responses=True, socket_timeout=3,
                socket_connect_timeout=2, retry_on_timeout=False
            )
            self._redis.ping()
        except Exception:
            if fallback_to_memory:
                self._using_memory = True
                self._redis = None
            else:
                raise

    @property
    def backend(self) -> str:
        return "memory" if self._using_memory else "redis"

    def get_json(self, key: str) -> Optional[Any]:
        raw = None
        if self._using_memory:
            return self._memory.get(key)
        try:
            raw = self._redis.get(key)
        except Exception:
            self._using_memory = True
            return self._memory.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def set_json(self, key: str, value: Any, ttl: int = 300) -> None:
        if self._using_memory:
            self._memory.set(key, value, ttl)
            return
        try:
            self._redis.setex(key, ttl, json.dumps(value, ensure_ascii=False, default=str))
        except Exception:
            self._using_memory = True
            self._memory.set(key, value, ttl)

    def delete(self, key: str) -> bool:
        if self._using_memory:
            return self._memory.delete(key)
        try:
            return bool(self._redis.delete(key))
        except Exception:
            return False

    def incr(self, key: str, ttl: int = 60) -> int:
        if self._using_memory:
            val = self._memory.get(key) or 0
            val = int(val) + 1
            self._memory.set(key, val, ttl)
            return val
        try:
            pipe = self._redis.pipeline()
            pipe.incr(key, 1)
            pipe.expire(key, ttl)
            results = pipe.execute()
            return int(results[0])
        except Exception:
            val = (self._memory.get(key) or 0) + 1
            self._memory.set(key, val, ttl)
            return val

    def exists(self, key: str) -> bool:
        if self._using_memory:
            return self._memory.get(key) is not None
        try:
            return bool(self._redis.exists(key))
        except Exception:
            return False


class QueryCache:
    """
    查询结果缓存
    按 (module, input_hash) → result 缓存
    """

    def __init__(self, client: Optional[RedisClient] = None, default_ttl: int = 300):
        self.client = client or RedisClient()
        self.default_ttl = default_ttl

    def _make_key(self, module: str, input_hash: str) -> str:
        return f"query:{module}:{input_hash}"

    def get(self, module: str, input_hash: str) -> Optional[Dict]:
        return self.client.get_json(self._make_key(module, input_hash))

    def set(self, module: str, input_hash: str, result: Dict, ttl: Optional[int] = None) -> None:
        self.client.set_json(
            self._make_key(module, input_hash),
            result,
            ttl=ttl or self.default_ttl
        )

    def invalidate(self, module: str, input_hash: str) -> None:
        self.client.delete(self._make_key(module, input_hash))
