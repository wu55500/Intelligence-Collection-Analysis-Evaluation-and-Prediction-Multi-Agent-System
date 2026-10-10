"""
M21 承诺等级模块
支持承诺等级评估、规则引擎、审计记录
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class CommitmentLevel(str, Enum):
    A = "A"  # 闭环可操作定量
    B = "B"  # 条件性比率/比较静态
    C = "C"  # 方向/预测/情景判断
    D = "D"  # 伪精确/不可证伪承诺
    BLOCKED = "BLOCKED"  # 硬性阻断


@dataclass
class CommitmentInput:
    """承诺等级评估输入"""
    evidence_count: int = 0
    sample_size: Optional[int] = None
    has_feedback_loop: bool = False
    feedback_count: int = 0
    has_structural_break: bool = False
    has_mechanism: bool = False
    has_falsifiable_anchor: bool = False
    is_contradicted: bool = False
    is_expired: bool = False
    single_source: bool = False
    data_quality_level: str = "C"  # S, A, B, C, D
    method_name: str = ""


@dataclass
class CommitmentDecision:
    """承诺等级决策"""
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    level: CommitmentLevel = CommitmentLevel.C
    reason: str = ""
    conditions: List[str] = field(default_factory=list)
    previous_level: Optional[CommitmentLevel] = None
    change_type: Optional[str] = None  # upgrade, downgrade, block
    timestamp: datetime = field(default_factory=datetime.now)
    task_id: str = ""


class CommitmentEngine:
    """
    承诺等级规则引擎
    
    三层架构：
    1. 子模块提供依据（数据质量、证据冲突等）
    2. 本引擎（确定性规则）计算允许的最高承诺等级
    3. 主控Agent根据裁决结果组织报告，不得擅自提高等级
    """
    
    # A级要求
    A_MIN_SAMPLE_SIZE = 30
    A_REQUIRED_FEEDBACK_LOOPS = 3
    A_MAX_STRUCTURAL_BREAK_DAYS = 90
    
    # B级要求
    B_MIN_EVIDENCE_SOURCES = 2
    B_REQUIRES_MECHANISM = True
    
    # C级要求
    C_MIN_EVIDENCE_SOURCES = 1
    
    # 降级规则
    SINGLE_SOURCE_MAX_LEVEL = "C"
    CONTRADICTED_MAX_LEVEL = "B"
    EXPIRED_MAX_LEVEL = "D"
    
    def evaluate(self, input_data: CommitmentInput) -> CommitmentDecision:
        """评估承诺等级"""
        decision = CommitmentDecision()
        
        # 1. 检查BLOCKED条件
        blocked, block_reason = self._check_blocked(input_data)
        if blocked:
            decision.level = CommitmentLevel.BLOCKED
            decision.reason = block_reason
            decision.conditions = ["BLOCKED条件触发，流程不可继续"]
            return decision
        
        # 2. 检查降级条件
        downgrade_level = self._check_downgrade(input_data)
        if downgrade_level:
            decision.level = downgrade_level[0]
            decision.reason = downgrade_level[1]
            return decision
        
        # 3. 检查A级条件
        a_check = self._check_a_level(input_data)
        if a_check[0]:
            decision.level = CommitmentLevel.A
            decision.reason = a_check[1]
            decision.conditions = a_check[2]
            return decision
        
        # 4. 检查B级条件
        b_check = self._check_b_level(input_data)
        if b_check[0]:
            decision.level = CommitmentLevel.B
            decision.reason = b_check[1]
            decision.conditions = b_check[2]
            return decision
        
        # 5. 默认C级
        decision.level = CommitmentLevel.C
        decision.reason = "方向/预测/情景判断，证据与方法可说明"
        decision.conditions = ["基率、期限、证伪锚点和结算规则需明确"]
        
        return decision
    
    def _check_blocked(self, input_data: CommitmentInput) -> Tuple[bool, str]:
        """检查是否触发BLOCKED"""
        if input_data.evidence_count == 0:
            return True, "无证据输入，流程阻断"
        
        if input_data.data_quality_level == "D":
            return True, "数据质量D级，流程阻断"
        
        if input_data.is_expired and input_data.evidence_count < 3:
            return True, "证据过期且不足3条，流程阻断"
        
        return False, ""
    
    def _check_downgrade(self, input_data: CommitmentInput) -> Optional[Tuple[CommitmentLevel, str]]:
        """检查降级条件"""
        if input_data.is_expired:
            return (CommitmentLevel.D, "证据过期，降级为D级")
        
        if input_data.single_source:
            return (CommitmentLevel.C, "单源证据，封顶C级")
        
        if input_data.is_contradicted:
            return (CommitmentLevel.B, "存在反证，封顶B级")
        
        return None
    
    def _check_a_level(self, input_data: CommitmentInput) -> Tuple[bool, str, List[str]]:
        """检查A级条件"""
        conditions = []
        
        # 样本量检查
        if input_data.sample_size is None or input_data.sample_size < self.A_MIN_SAMPLE_SIZE:
            return False, f"样本量不足（需要≥{self.A_MIN_SAMPLE_SIZE}）", []
        
        conditions.append(f"样本量={input_data.sample_size}≥{self.A_MIN_SAMPLE_SIZE}")
        
        # 反馈闭环检查
        if not input_data.has_feedback_loop or input_data.feedback_count < self.A_REQUIRED_FEEDBACK_LOOPS:
            return False, f"反馈闭环不足（需要≥{self.A_REQUIRED_FEEDBACK_LOOPS}次）", []
        
        conditions.append(f"反馈闭环次数={input_data.feedback_count}≥{self.A_REQUIRED_FEEDBACK_LOOPS}")
        
        # 结构断点检查
        if input_data.has_structural_break:
            return False, "存在结构断点", []
        
        # 数据质量检查
        if input_data.data_quality_level in ["C", "D"]:
            return False, f"数据质量{input_data.data_quality_level}级，不满足A级要求", []
        
        conditions.append(f"数据质量={input_data.data_quality_level}")
        
        # 证伪锚点检查
        if not input_data.has_falsifiable_anchor:
            return False, "缺少证伪锚点", []
        
        conditions.append("证伪锚点已声明")
        
        return True, "满足A级所有条件：输入可追溯、误差定义明确、反馈频率足够", conditions
    
    def _check_b_level(self, input_data: CommitmentInput) -> Tuple[bool, str, List[str]]:
        """检查B级条件"""
        conditions = []
        
        # 机制检查
        if self.B_REQUIRES_MECHANISM and not input_data.has_mechanism:
            return False, "B级要求机制与缩放假设清楚", []
        
        conditions.append("机制与缩放假设已声明")
        
        # 多来源检查
        if input_data.evidence_count < self.B_MIN_EVIDENCE_SOURCES:
            return False, f"证据来源数={input_data.evidence_count}，B级要求≥{self.B_MIN_EVIDENCE_SOURCES}", []
        
        conditions.append(f"证据来源数={input_data.evidence_count}≥{self.B_MIN_EVIDENCE_SOURCES}")
        
        # 证伪锚点
        if not input_data.has_falsifiable_anchor:
            return False, "B级要求证伪锚点明确", []
        
        conditions.append("证伪锚点已声明")
        
        return True, "满足B级条件：在明确假设下给出相对变化", conditions
    
    def get_evaluation_stats(self) -> Dict[str, Any]:
        """获取评估统计"""
        return {
            "engine_version": "1.0",
            "rules": {
                "a_min_sample_size": self.A_MIN_SAMPLE_SIZE,
                "a_required_feedback_loops": self.A_REQUIRED_FEEDBACK_LOOPS,
                "b_min_evidence_sources": self.B_MIN_EVIDENCE_SOURCES
            }
        }
