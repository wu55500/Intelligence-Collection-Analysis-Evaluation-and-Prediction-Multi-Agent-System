"""
M8 预测登记与结算 - Agent侧

职责：
1. 将分析结论转化为结构化预测（五件套）
2. 调用ForecastService登记（不可覆盖）
3. 到期后触发结算
4. 计算Brier Score并与基线比较
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import uuid

from ...core.schemas import ForecastRecord, CommitmentLevel
from ...services.forecast_service import ForecastService, BrierScoreResult


@dataclass
class ForecastProposal:
    """预测提案（Agent生成，确定性服务审核）"""
    event_description: str
    probability: float
    time_range_start: datetime
    time_range_end: datetime
    falsifiable_anchor: str
    premises: List[str]
    evidence_snapshot: Dict[str, Any]
    task_id: str
    proposed_by: str  # "research_agent" / "analysis_agent"


@dataclass
class ForecastLifecycle:
    """预测生命周期状态"""
    forecast_id: str
    stage: str  # "proposed", "registered", "monitoring", "due", "settled"
    registered_at: datetime
    due_at: datetime
    days_remaining: int
    outcome: Optional[str] = None
    brier_score: Optional[float] = None


class ForecasterAgent:
    """
    预测Agent（Agent层）
    
    注意：实际登记/结算由确定性ForecastService执行
    本Agent负责：生成预测提案、触发结算流程、汇总评估结果
    """
    
    def __init__(self):
        self.forecast_service = ForecastService()
    
    def propose(
        self,
        event_description: str,
        probability: float,
        days_ahead: int,
        falsifiable_anchor: str,
        premises: List[str],
        evidence_snapshot: Dict[str, Any],
        task_id: str,
        proposed_by: str = "analysis_agent"
    ) -> ForecastProposal:
        """
        生成预测提案
        
        五件套：结论+置信度区间+证伪锚点+到期日+登记时间
        """
        now = datetime.now()
        
        # 概率范围校验
        if not 0.0 <= probability <= 1.0:
            raise ValueError(f"概率必须在0-1之间: {probability}")
        
        # 证伪锚点不能为空
        if not falsifiable_anchor.strip():
            raise ValueError("证伪锚点不能为空（九条铁律第2条）")
        
        return ForecastProposal(
            event_description=event_description,
            probability=probability,
            time_range_start=now,
            time_range_end=now + timedelta(days=days_ahead),
            falsifiable_anchor=falsifiable_anchor,
            premises=premises,
            evidence_snapshot=evidence_snapshot,
            task_id=task_id,
            proposed_by=proposed_by
        )
    
    def register(self, proposal: ForecastProposal) -> ForecastRecord:
        """
        登记预测（调用确定性服务）
        
        登记后不可覆盖——只能追加
        """
        record = self.forecast_service.register_forecast(
            task_id=proposal.task_id,
            event_description=proposal.event_description,
            probability=proposal.probability,
            time_range_start=proposal.time_range_start,
            time_range_end=proposal.time_range_end,
            falsifiable_anchor=proposal.falsifiable_anchor,
            premises=proposal.premises,
            evidence_snapshot=proposal.evidence_snapshot
        )
        return record
    
    def check_due(self) -> List[ForecastRecord]:
        """检查到期待结算的预测"""
        return self.forecast_service.check_due_forecasts()
    
    def settle_batch(self) -> Dict[str, Any]:
        """批量结算到期的预测（需要外部提供实际结果）"""
        due = self.check_due()
        return {
            "due_count": len(due),
            "forecasts": [
                {
                    "forecast_id": f.forecast_id,
                    "event": f.event_description,
                    "probability": f.probability,
                    "anchor": f.falsifiable_anchor,
                    "due_at": f.time_range_end.isoformat(),
                    "needs_manual_settlement": True
                }
                for f in due
            ]
        }
    
    def get_lifecycle(self, forecast_id: str) -> Optional[ForecastLifecycle]:
        """获取预测生命周期状态"""
        unsettled = self.forecast_service.get_unsettled_forecasts()
        for f in unsettled:
            if f.forecast_id == forecast_id:
                remaining = (f.time_range_end - datetime.now()).days
                stage = "due" if remaining <= 0 else "monitoring"
                return ForecastLifecycle(
                    forecast_id=f.forecast_id,
                    stage=stage,
                    registered_at=f.registered_at,
                    due_at=f.time_range_end,
                    days_remaining=remaining
                )
        return None
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取预测表现汇总"""
        brier = self.forecast_service.calculate_brier_score()
        return {
            "total_settled": brier.count,
            "brier_score": brier.score,
            "calibrated": brier.calibrated,
            "vs_baseline": brier.vs_baseline,
            "min_for_systematic_review": self.forecast_service.min_settlement_count,
            "ready_for_review": brier.count >= self.forecast_service.min_settlement_count
        }
