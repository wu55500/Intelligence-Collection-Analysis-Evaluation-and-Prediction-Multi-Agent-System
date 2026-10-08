"""
系统配置管理
支持环境变量覆盖，适配手机端和云端部署
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class LLMConfig(BaseModel):
    """LLM模型配置"""
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 120
    fallback_model: Optional[str] = None


class DatabaseConfig(BaseModel):
    """数据库配置"""
    db_path: str = "data/intel_system.db"
    wal_mode: bool = True
    journal_mode: str = "wal"
    busy_timeout: int = 5000


class CommitmentRules(BaseModel):
    """M21承诺等级规则 - 可配置，非硬编码"""
    # A级要求：输入可追溯、误差定义明确、反馈频率足够
    a_min_sample_size: int = 30
    a_required_feedback_loops: int = 3
    a_max_structural_break_days: int = 90
    
    # B级要求：明确假设、缩放机制清楚
    b_min_evidence_sources: int = 2
    b_requires_mechanism: bool = True
    
    # C级：方向判断，允许不确定性
    c_min_evidence_sources: int = 1
    c_max_falsifiable_days: int = 365
    
    # 降级规则
    single_source_max_level: str = "C"
    contradicted_max_level: str = "B"
    expired_max_level: str = "D"
    
    # 熔断条件
    circuit_break_keywords: list = [
        "source_unavailable", "schema_error", "tool_failure",
        "budget_exceeded", "permission_anomaly", "future_leak",
        "evidence_conflict_spike", "error_drift", "model_unhealthy"
    ]


class PermissionRules(BaseModel):
    """M14权限规则"""
    # 危险关键词 → 强制S>=9, L3
    dangerous_keywords: list = ["删除", "转账", "购买", "发布", "隐私"]
    
    # RPN阈值
    l1_max_rpn: int = 27
    l2_max_rpn: int = 100
    l3_min_severity: int = 8
    
    # 权限单向收紧：只紧不松
    monotonic: bool = True


class CollectionConfig(BaseModel):
    """M1采集配置"""
    max_sources_per_query: int = 20
    reverse_search_ratio: float = 0.5
    timeout_per_source: int = 10
    max_retries: int = 3
    freshness_hours: int = 24
    domain_whitelist_path: Optional[str] = None


class Settings(BaseSettings):
    """全局配置"""
    
    # 基础路径
    project_root: str = str(Path(__file__).parent.parent.parent)
    data_dir: str = "data"
    
    # 各子系统配置
    llm: LLMConfig = LLMConfig()
    database: DatabaseConfig = DatabaseConfig()
    commitment: CommitmentRules = CommitmentRules()
    permission: PermissionRules = PermissionRules()
    collection: CollectionConfig = CollectionConfig()
    
    # 运行模式
    debug: bool = False
    log_level: str = "INFO"
    
    # 手机端适配
    mobile_mode: bool = False
    cloud_fallback: bool = True
    checkpoint_interval: int = 60
    
    # 预测评估
    forecast_min_settlement_count: int = 100
    
    model_config = {"env_prefix": "INTEL_", "env_nested_delimiter": "__"}


_settings: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

def reload_settings(**overrides) -> Settings:
    global _settings
    _settings = Settings(**overrides)
    return _settings
