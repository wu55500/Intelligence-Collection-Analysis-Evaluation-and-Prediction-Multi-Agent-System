"""
核心数据模型定义
基于Pydantic实现严格的类型验证和Schema控制
"""

from typing import Optional, Literal, Dict, List, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class CommitmentLevel(str, Enum):
    """承诺等级 - M21确定性规则引擎"""
    A = "A"  # 闭环可操作定量
    B = "B"  # 条件性比率/比较静态
    C = "C"  # 方向/预测/情景判断
    D = "D"  # 伪精确/不可证伪承诺
    BLOCKED = "BLOCKED"  # 硬性阻断


class EvidenceQuality(str, Enum):
    """证据质量等级"""
    S = "S"  # 官方一手
    A = "A"  # 权威机构
    B = "B"  # 主流媒体
    C = "C"  # 自媒体待核实
    D = "D"  # 剔除


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    CIRCUIT_BREAK = "circuit_break"


class PermissionLevel(str, Enum):
    """权限等级 - M14"""
    L1 = "L1"  # 自主执行
    L2 = "L2"  # 确认后执行
    L3 = "L3"  # 人工主导


class TaskContract(BaseModel):
    """
    任务契约 - 所有任务的标准输入格式
    对应修正问题4：任务协议设计
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    task_id: str = Field(description="任务唯一标识")
    task_type: str = Field(description="任务类型：research/analysis/forecast")
    input_data: Dict[str, Any] = Field(description="输入数据")
    input_hash: str = Field(description="输入内容哈希，用于追溯")
    method_version: str = Field(description="方法版本")
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    evidence_refs: List[str] = Field(default_factory=list, description="产出的证据引用")
    error_code: Optional[str] = None
    retryable: bool = False
    output_hash: Optional[str] = None
    commitment_level: CommitmentLevel = CommitmentLevel.C
    permission_level: PermissionLevel = PermissionLevel.L1


class Evidence(BaseModel):
    """
    证据记录 - M12证据链治理
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    evidence_id: str
    source_url: str
    source_quality: EvidenceQuality
    content_hash: str
    raw_content: str
    extracted_at: datetime = Field(default_factory=datetime.now)
    credibility_score: float = Field(ge=0, le=1)
    relevance_score: float = Field(ge=0, le=1)
    diagnostic_score: float = Field(ge=0, le=1)
    is_contradictory: bool = False
    task_id: str
    claims: List[str] = Field(default_factory=list)


class Claim(BaseModel):
    """
    主张/结论记录
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    claim_id: str
    claim_type: Literal["fact", "interpretation", "inference", "forecast", "scenario"]
    content: str
    commitment_level: CommitmentLevel
    evidence_ids: List[str]
    created_at: datetime = Field(default_factory=datetime.now)
    falsifiable_anchor: Optional[str] = Field(description="证伪锚点")
    verification_suggestion: Optional[str] = Field(description="验证建议")
    sample_size: Optional[int] = None
    data_quality_level: Optional[EvidenceQuality] = None
    task_id: str


class ForecastRecord(BaseModel):
    """
    预测记录 - M8预测登记与结算
    关键：不可覆盖，只能追加和结算
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    forecast_id: str
    event_description: str
    probability: float = Field(ge=0, le=1)
    time_range_start: datetime
    time_range_end: datetime
    falsifiable_anchor: str
    premises: List[str] = Field(description="前提条件")
    registered_at: datetime = Field(default_factory=datetime.now)
    settled: bool = False
    settled_at: Optional[datetime] = None
    outcome: Optional[Literal["hit", "miss", "falsified", "unresolved"]] = None
    brier_score: Optional[float] = None
    evidence_snapshot: Dict[str, Any] = Field(description="登记时的证据快照")
    task_id: str


class AuditLog(BaseModel):
    """
    审计日志 - 所有关键操作的记录
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    log_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    action: str
    actor: str  # "system", "user", "agent", "service"
    details: Dict[str, Any]
    task_id: Optional[str] = None
    commitment_change: Optional[Dict[str, Any]] = None


class PermissionRequest(BaseModel):
    """
    权限请求 - M14权限治理
    """
    request_id: str
    action_type: str
    impact_level: Literal["low", "medium", "high", "critical"]
    requires_approval: bool
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    task_id: str


class CircuitBreakerState(BaseModel):
    """
    熔断器状态
    """
    module_name: str
    failure_count: int = 0
    last_failure: Optional[datetime] = None
    is_open: bool = False
    opened_at: Optional[datetime] = None
    failure_threshold: int = 5
    recovery_timeout: int = 60  # seconds


class ModelHealthMetrics(BaseModel):
    """
    模型健康指标 - M20
    """
    model_name: str
    model_version: str
    drift_score: Optional[float] = None
    accuracy_trend: Optional[float] = None
    last_check: datetime = Field(default_factory=datetime.now)
    is_healthy: bool = True
    alerts: List[str] = Field(default_factory=list)
