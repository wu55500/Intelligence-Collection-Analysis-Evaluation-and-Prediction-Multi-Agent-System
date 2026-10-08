"""
M21 承诺等级规则引擎 - 确定性实现

关键设计：
1. 不是提示词，是普通代码执行规则
2. 等级、阈值来自可配置规则，非硬编码
3. 提供依据 → 规则引擎执行 → 主控Agent交付
4. 关键规则由普通程序执行，LLM负责提供分析依据
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from dataclasses import dataclass

from ..core.schemas import (
    CommitmentLevel, EvidenceQuality, Evidence, AuditLog
)
from ..core.config import get_settings
from ..core.database import get_database

import uuid


@dataclass
class CommitmentInput:
    """承诺等级评估输入"""
    evidence_list: List[Evidence]
    sample_size: Optional[int] = None
    has_feedback_loop: bool = False
    feedback_count: int = 0
    has_structural_break: bool = False
    has_mechanism: bool = False
    has_falsifiable_anchor: bool = False
    is_contradicted: bool = False
    is_expired: bool = False
    single_source: bool = False
    data_quality_level: Optional[EvidenceQuality] = None
    method_name: str = ""


@dataclass
class CommitmentDecision:
    """承诺等级裁决结果"""
    level: CommitmentLevel
    reason: str
    conditions: List[str]
    previous_level: Optional[CommitmentLevel] = None
    change_type: Optional[str] = None  # "upgrade", "downgrade", "block"
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class CommitmentEngine:
    """
    M21 承诺等级规则引擎
    
    三层架构：
    - 第一层：子模块提供依据（数据质量、模型表现、证据冲突等）
    - 第二层：本引擎（确定性规则）计算允许的最高承诺等级
    - 第三层：主控Agent根据裁决结果组织报告，不得擅自提高等级
    """
    
    def __init__(self):
        self.settings = get_settings().commitment
        self.db = get_database()
    
    def evaluate(self, input_data: CommitmentInput) -> CommitmentDecision:
        """
        评估承诺等级
        
        规则优先级：
        1. BLOCKED条件 → 硬性阻断
        2. 降级条件 → 检查是否触发降级
        3. A级条件 → 最严格检查
        4. B级条件 → 中等检查
        5. 默认C级
        """
        reasons = []
        conditions = []
        
        # ========== 第一步：检查BLOCKED条件 ==========
        blocked, block_reason = self._check_blocked(input_data)
        if blocked:
            return CommitmentDecision(
                level=CommitmentLevel.BLOCKED,
                reason=block_reason,
                conditions=["BLOCKED条件触发，流程不可继续"]
            )
        
        # ========== 第二步：检查降级条件 ==========
        downgrade_level = self._check_downgrade(input_data)
        if downgrade_level:
            reasons.append(f"触发降级条件: {downgrade_level[1]}")
        
        # ========== 第三步：检查A级条件 ==========
        a_check = self._check_a_level(input_data)
        if a_check.passed:
            return CommitmentDecision(
                level=CommitmentLevel.A,
                reason=a_check.reason,
                conditions=a_check.conditions
            )
        
        # ========== 第四步：检查B级条件 ==========
        b_check = self._check_b_level(input_data)
        if b_check.passed:
            return CommitmentDecision(
                level=CommitmentLevel.B,
                reason=b_check.reason,
                conditions=b_check.conditions
            )
        
        # ========== 第五步：检查降级结果 ==========
        if downgrade_level:
            return CommitmentDecision(
                level=downgrade_level[0],
                reason=downgrade_level[1],
                conditions=reasons
            )
        
        # ========== 默认C级 ==========
        return CommitmentDecision(
            level=CommitmentLevel.C,
            reason="方向/预测/情景判断，证据与方法可说明",
            conditions=["基率、期限、证伪锚点和结算规则需明确"]
        )
    
    def _check_blocked(self, input_data: CommitmentInput) -> Tuple[bool, str]:
        """检查是否触发BLOCKED"""
        # 来源完全缺失
        if not input_data.evidence_list:
            return True, "无证据输入，流程阻断"
        
        # 所有证据质量D级
        if all(e.source_quality == EvidenceQuality.D for e in input_data.evidence_list):
            return True, "所有证据质量D级（剔除），流程阻断"
        
        # 未来数据泄漏
        future_leak = any(
            "future_leak" in str(e.claims)
            for e in input_data.evidence_list
        )
        if future_leak:
            return True, "检测到未来信息泄漏，流程阻断"
        
        # 结构性突变且无法监测
        if input_data.has_structural_break and not input_data.has_feedback_loop:
            return True, "结构性突变且无反馈机制，无法监测失效"
        
        return False, ""
    
    def _check_downgrade(self, input_data: CommitmentInput) -> Optional[Tuple[CommitmentLevel, str]]:
        """检查降级条件"""
        # 单一来源 → 最高C
        if input_data.single_source:
            max_level = CommitmentLevel(self.settings.single_source_max_level)
            return max_level, "单一来源，承诺等级封顶"
        
        # 存在矛盾证据 → 最高B
        if input_data.is_contradicted:
            max_level = CommitmentLevel(self.settings.contradicted_max_level)
            return max_level, "证据冲突未消解，承诺等级封顶"
        
        # 过期数据 → 最高D
        if input_data.is_expired:
            max_level = CommitmentLevel(self.settings.expired_max_level)
            return max_level, "证据过期，承诺等级封顶"
        
        return None
    
    def _check_a_level(self, input_data: CommitmentInput) -> "_CheckResult":
        """
        检查A级条件
        A级代表：局部可复算、误差定义明确、可监控并有反馈修正
        """
        conditions = []
        
        # 样本量检查
        if input_data.sample_size is None or input_data.sample_size < self.settings.a_min_sample_size:
            return _CheckResult(False, f"样本量不足（需要≥{self.settings.a_min_sample_size}）")
        
        conditions.append(f"样本量={input_data.sample_size}≥{self.settings.a_min_sample_size}")
        
        # 反馈闭环检查
        if not input_data.has_feedback_loop:
            return _CheckResult(False, "缺少反馈闭环机制")
        
        if input_data.feedback_count < self.settings.a_required_feedback_loops:
            return _CheckResult(
                False,
                f"反馈闭环次数不足（需要≥{self.settings.a_required_feedback_loops}，实际{input_data.feedback_count}）"
            )
        
        conditions.append(f"反馈闭环次数={input_data.feedback_count}≥{self.settings.a_required_feedback_loops}")
        
        # 数据质量检查
        if input_data.data_quality_level and input_data.data_quality_level.value in ("C", "D"):
            return _CheckResult(False, "数据质量C/D级，不满足A级要求")
        
        # 多独立来源
        independent_sources = self._count_independent_sources(input_data.evidence_list)
        if independent_sources < 3:
            return _CheckResult(False, f"独立来源数={independent_sources}，A级要求≥3")
        
        conditions.append(f"独立来源数={independent_sources}≥3")
        
        return _CheckResult(
            True,
            "满足A级所有条件：输入可追溯、误差定义明确、反馈频率足够",
            conditions
        )
    
    def _check_b_level(self, input_data: CommitmentInput) -> "_CheckResult":
        """
        检查B级条件
        B级代表：在明确假设下给出相对变化、比例或倍数
        """
        conditions = []
        
        # 机制检查
        if self.settings.b_requires_mechanism and not input_data.has_mechanism:
            return _CheckResult(False, "B级要求机制与缩放假设清楚")
        
        conditions.append("机制与缩放假设已声明")
        
        # 多来源检查
        if len(input_data.evidence_list) < self.settings.b_min_evidence_sources:
            return _CheckResult(
                False,
                f"证据来源数={len(input_data.evidence_list)}，B级要求≥{self.settings.b_min_evidence_sources}"
            )
        
        conditions.append(f"证据来源数={len(input_data.evidence_list)}≥{self.settings.b_min_evidence_sources}")
        
        # 证伪锚点
        if not input_data.has_falsifiable_anchor:
            return _CheckResult(False, "B级要求证伪锚点明确")
        
        conditions.append("证伪锚点已声明")
        
        return _CheckResult(
            True,
            "满足B级条件：在明确假设下给出相对变化",
            conditions
        )
    
    def _count_independent_sources(self, evidence_list: List[Evidence]) -> int:
        """计算独立来源数（不同信息生成者）"""
        # 转载不算独立源：按域名聚类
        domains = set()
        for e in evidence_list:
            domain = self._extract_domain(e.source_url)
            if domain:
                domains.add(domain)
        return len(domains)
    
    def _extract_domain(self, url: str) -> Optional[str]:
        """从URL提取域名"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return None
    
    def record_decision(
        self,
        task_id: str,
        decision: CommitmentDecision,
        previous_level: Optional[CommitmentLevel] = None
    ) -> str:
        """记录裁决到审计日志"""
        decision.previous_level = previous_level
        if previous_level and previous_level != decision.level:
            if decision.level == CommitmentLevel.BLOCKED:
                decision.change_type = "block"
            elif self._level_order(decision.level) > self._level_order(previous_level):
                decision.change_type = "upgrade"
            else:
                decision.change_type = "downgrade"
        
        # 写审计日志
        audit = AuditLog(
            log_id=str(uuid.uuid4()),
            action="commitment_decision",
            actor="commitment_engine",
            details={
                "level": decision.level.value,
                "reason": decision.reason,
                "conditions": decision.conditions,
                "previous_level": previous_level.value if previous_level else None,
                "change_type": decision.change_type
            },
            task_id=task_id,
            commitment_change={
                "from": previous_level.value if previous_level else None,
                "to": decision.level.value,
                "type": decision.change_type
            }
        )
        self.db.log_audit(audit)
        
        return audit.log_id
    
    @staticmethod
    def _level_order(level: CommitmentLevel) -> int:
        """等级数值映射（用于比较升降级）"""
        order = {
            CommitmentLevel.A: 5,
            CommitmentLevel.B: 4,
            CommitmentLevel.C: 3,
            CommitmentLevel.D: 2,
            CommitmentLevel.BLOCKED: 0
        }
        return order.get(level, 1)


@dataclass
class _CheckResult:
    """内部检查结果"""
    passed: bool
    reason: str
    conditions: List[str] = None

    def __post_init__(self):
        if self.conditions is None:
            self.conditions = []
