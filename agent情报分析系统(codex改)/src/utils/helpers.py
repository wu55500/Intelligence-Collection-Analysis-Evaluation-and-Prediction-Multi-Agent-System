"""
通用工具函数
"""

import hashlib
import json
from typing import Any, Dict
from datetime import datetime


def calculate_hash(content: Any) -> str:
    """计算内容的SHA256哈希"""
    if isinstance(content, str):
        data = content.encode('utf-8')
    elif isinstance(content, (dict, list)):
        data = json.dumps(content, ensure_ascii=False, sort_keys=True).encode('utf-8')
    else:
        data = str(content).encode('utf-8')
    
    return hashlib.sha256(data).hexdigest()


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """安全的JSON解析"""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def format_timestamp(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化时间戳"""
    return dt.strftime(fmt)


def truncate_text(text: str, max_length: int = 200) -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."
