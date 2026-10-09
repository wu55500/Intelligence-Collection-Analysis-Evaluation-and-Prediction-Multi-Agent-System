"""
承诺等级评估引擎
基于证据质量、样本量、反馈闭环等因素确定结论的承诺等级
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import uuid

from ..core.schemas import CommitmentLevel, Evidence, EvidenceQuality


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
    """承诺等级决策结果"""
    decision_id: str
    level: CommitmentLevel
    reason: str
    conditions: List[str]
    timestamp: datetime = datetime.now()


class CommitmentEngine:
    """
    承诺等级规则引擎
    
    评估输入条件，输出允许的最高承诺等级
    """
    
    def __init__(self):
        pass
    
    def evaluate(self, input_data: CommitmentInput) -> CommitmentDecision:
        """评估承诺等级"""
        # 检查是否触发BLOCKED
        blocked, reason = self._check_blocked(input_data)
        if blocked:
            return CommitmentDecision(
                decision_id=str(uuid.uuid4()),
                level=CommitmentLevel.BLOCKED,
                reason=reason,
                conditions=[]
            )
        
        # 检查降级条件
        downgrade = self._check_downgrade(input_data)
        if downgrade:
            return CommitmentDecision(
                decision_id=str(uuid.uuid4()),
                level=downgrade[0],
                reason=downgrade[1],
                conditions=[]
            )
        
        # 检查A级条件
        a_check = self._check_a_level(input_data)
        if a_check:
            return CommitmentDecision(
                decision_id=str(uuid.uuid4()),
                level=CommitmentLevel.A,
                reason=a_check[1],
                conditions=a_check[2]
            )
        
        # 检查B级条件
        b_check = self._check_b_level(input_data)
        if b_check:
            return CommitmentDecision(
                decision_id=str(uuid.uuid4()),
                level=CommitmentLevel.B,
                reason=b_check[1],
                conditions=b_check[2]
            )
        
        # 默认C级
        return CommitmentDecision(
            decision_id=str(uuid.uuid4()),
            level=CommitmentLevel.C,
            reason="方向性判断，缺乏充分证据支持更高等级",
            conditions=["建议补充证据或降低承诺等级"]
        )
    
    def _check_blocked(self, input_data: CommitmentInput) -> tuple[bool, str]:
        """检查是否触发BLOCKED"""
        if not input_data.evidence_list:
            return True, "无证据输入，流程阻断"
        
        if input_data.data_quality_level == EvidenceQuality.D:
            return True, "数据质量D级，流程阻断"
        
        return False, ""
    
    def _check_downgrade(self, input_data: CommitmentInput) -> Optional[tuple[CommitmentLevel, str]]:
        """检查降级条件"""
        if input_data.is_expired:
            return (CommitmentLevel.D, "证据过期，降级为D级")
        
        if input_data.single_source:
            return (CommitmentLevel.C, "单源证据，封顶C级")
        
        if input_data.is_contradicted:
            return (CommitmentLevel.B, "存在反证，封顶B级")
        
        return None
    
    def _check_a_level(self, input_data: CommitmentInput) -> Optional[tuple[bool, str, List[str]]]:
        """检查A级条件"""
        conditions = []
        
        if input_data.sample_size is None or input_data.sample_size < 30:
            return None
        
        conditions.append(f"样本量={input_data.sample_size}≥30")
        
        if not input_data.has_feedback_loop or input_data.feedback_count < 3:
            return None
        
        conditions.append(f"反馈闭环次数={input_data.feedback_count}≥3")
        
        if input_data.has_structural_break:
            return None
        
        if input_data.data_quality_level in [EvidenceQuality.C, EvidenceQuality.D]:
            return None
        
        conditions.append(f"数据质量={input_data.data_quality_level}")
        
        if not input_data.has_falsifiable_anchor:
            return None
        
        conditions.append("证伪锚点已声明")
        
        return (True, "满足A级所有条件", conditions)
    
    def _check_b_level(self, input_data: CommitmentInput) -> Optional[tuple[bool, str, List[str]]]:
        """检查B级条件"""
        conditions = []
        
        if not input_data.has_mechanism:
            return None
        
        conditions.append("机制与缩放假设已声明")
        
        if len(input_data.evidence_list) < 2:
            return None
        
        conditions.append(f"证据来源数={len(input_data.evidence_list)}≥2")
        
        if not input_data.has_falsifiable_anchor:
            return None
        
        conditions.append("证伪锚点已声明")
        
        return (True, "满足B级条件", conditions)


# 全局实例
_commitment_engine: Optional[CommitmentEngine] = None


def get_commitment_engine() -> CommitmentEngine:
    """获取承诺等级引擎实例"""
    global _commitment_engine
    if _commitment_engine is None:
        _commitment_engine = CommitmentEngine()
    return _commitment_engine
