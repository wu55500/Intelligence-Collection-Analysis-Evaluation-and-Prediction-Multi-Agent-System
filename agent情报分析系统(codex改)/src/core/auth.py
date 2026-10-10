"""
认证与授权模块

提供：
1. API Key 认证
2. 基于角色的访问控制 (RBAC)
3. 对象级授权检查
4. 请求限流
"""

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from enum import Enum


class Permission(str, Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    DANGER = "danger"  # 危险操作（删除、结算、重跑）


class ResourceType(str, Enum):
    TASK = "task"
    FORECAST = "forecast"
    REPORT = "report"
    CONFIG = "config"
    SYSTEM = "system"


@dataclass
class APIKey:
    """API 密钥"""
    key_id: str
    key_hash: str  # SHA256 哈希存储，不存明文
    name: str
    permissions: Set[Permission]
    owner_id: str
    created_at: datetime
    expires_at: Optional[datetime]
    last_used: Optional[datetime]
    rate_limit: int = 1000  # 每小时请求数
    is_active: bool = True


@dataclass
class RateLimitEntry:
    """限流记录"""
    client_id: str
    request_count: int
    window_start: datetime


class AuthManager:
    """
    认证与授权管理器
    
    职责：
    1. API Key 管理
    2. 权限验证
    3. 对象级授权
    4. 请求限流
    """
    
    def __init__(self):
        self.api_keys: Dict[str, APIKey] = {}  # key_hash -> APIKey
        self.rate_limits: Dict[str, RateLimitEntry] = {}
        self.dangerous_actions: Set[str] = {
            "forecast_settle",
            "task_delete",
            "config_update",
            "permission_change"
        }
    
    def generate_api_key(self, name: str, owner_id: str, 
                        permissions: Set[Permission],
                        expires_hours: Optional[int] = None) -> str:
        """
        生成新的 API Key
        
        返回：明文密钥（仅显示一次）
        """
        raw_key = f"ik_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_id = secrets.token_hex(8)
        
        now = datetime.now()
        expires_at = now + timedelta(hours=expires_hours) if expires_hours else None
        
        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            name=name,
            permissions=permissions,
            owner_id=owner_id,
            created_at=now,
            expires_at=expires_at,
            last_used=None
        )
        
        self.api_keys[key_hash] = api_key
        return raw_key
    
    def authenticate(self, api_key: str) -> Optional[APIKey]:
        """
        认证 API Key
        
        返回：APIKey 对象或 None
        """
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        api_key_obj = self.api_keys.get(key_hash)
        if not api_key_obj:
            return None
        
        if not api_key_obj.is_active:
            return None
        
        if api_key_obj.expires_at and datetime.now() > api_key_obj.expires_at:
            return None
        
        # 更新最后使用时间
        api_key_obj.last_used = datetime.now()
        return api_key_obj
    
    def check_permission(self, api_key_obj: APIKey, 
                        permission: Permission) -> bool:
        """
        检查权限
        
        权限层级：admin > write > read
        """
        if Permission.ADMIN in api_key_obj.permissions:
            return True
        if permission == Permission.READ and Permission.WRITE in api_key_obj.permissions:
            return True
        return permission in api_key_obj.permissions
    
    def check_dangerous_action(self, api_key_obj: APIKey, 
                              action: str) -> bool:
        """
        检查危险操作权限
        
        危险操作需要 DANGER 或 ADMIN 权限
        """
        if action in self.dangerous_actions:
            return Permission.DANGER in api_key_obj.permissions or \
                   Permission.ADMIN in api_key_obj.permissions
        return True
    
    def check_object_access(self, api_key_obj: APIKey,
                           resource_type: ResourceType,
                           resource_id: str,
                           owner_id: str) -> bool:
        """
        对象级授权检查
        
        用户只能访问自己拥有的资源（除非有 ADMIN 权限）
        """
        if Permission.ADMIN in api_key_obj.permissions:
            return True
        return api_key_obj.owner_id == owner_id
    
    def check_rate_limit(self, client_id: str) -> tuple:
        """
        检查请求限流
        
        返回：(allowed: bool, remaining: int, reset_at: datetime)
        """
        now = datetime.now()
        entry = self.rate_limits.get(client_id)
        
        if not entry or (now - entry.window_start).seconds >= 3600:
            # 新窗口
            self.rate_limits[client_id] = RateLimitEntry(
                client_id=client_id,
                request_count=1,
                window_start=now
            )
            return True, 999, now + timedelta(hours=1)
        
        if entry.request_count >= 1000:
            return False, 0, entry.window_start + timedelta(hours=1)
        
        entry.request_count += 1
        return True, 1000 - entry.request_count, entry.window_start + timedelta(hours=1)
    
    def validate_request(self, api_key: str, action: str,
                        resource_type: Optional[ResourceType] = None,
                        resource_id: Optional[str] = None,
                        resource_owner: Optional[str] = None) -> dict:
        """
        完整请求验证
        
        返回：
        {
            "allowed": bool,
            "api_key": APIKey,
            "reason": str
        }
        """
        # 1. 认证
        api_key_obj = self.authenticate(api_key)
        if not api_key_obj:
            return {
                "allowed": False,
                "api_key": None,
                "reason": "无效的 API Key 或已过期"
            }
        
        # 2. 限流检查
        allowed, remaining, reset_at = self.check_rate_limit(api_key_obj.owner_id)
        if not allowed:
            return {
                "allowed": False,
                "api_key": api_key_obj,
                "reason": f"请求过于频繁，请等待至 {reset_at.isoformat()}"
            }
        
        # 3. 危险操作检查
        if not self.check_dangerous_action(api_key_obj, action):
            return {
                "allowed": False,
                "api_key": api_key_obj,
                "reason": f"操作 '{action}' 需要更高权限"
            }
        
        # 4. 对象级授权
        if resource_type and resource_id and resource_owner:
            if not self.check_object_access(api_key_obj, resource_type, 
                                          resource_id, resource_owner):
                return {
                    "allowed": False,
                    "api_key": api_key_obj,
                    "reason": "无权访问此资源"
                }
        
        return {
            "allowed": True,
            "api_key": api_key_obj,
            "reason": "验证通过",
            "remaining": remaining
        }
    
    def create_default_admin_key(self) -> str:
        """创建默认管理员密钥（仅用于开发环境）"""
        return self.generate_api_key(
            name="default_admin",
            owner_id="system",
            permissions={Permission.ADMIN},
            expires_hours=None
        )


# 全局实例
_auth_manager: Optional[AuthManager] = None

def get_auth_manager() -> AuthManager:
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager
