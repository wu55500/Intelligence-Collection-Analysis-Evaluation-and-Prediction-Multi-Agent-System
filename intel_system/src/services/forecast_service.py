"""
M8 预测登记与结算服务

关键设计：
1. 预测只追加，不可覆盖（防事后改写）
2. 结算按预先定义规则独立判定
3. 记录登记时的证据快照（防未来证据污染）
4. 100条已结算预测后开始系统性复盘Brier Score
5. 与简单基线比较
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass
import uuid
import json
import math

from ..core.schemas import (
    ForecastRecord, CommitmentLevel, AuditLog
)
from ..core.config import get_settings
from ..core.database import get_database


@dataclass
class BrierScoreResult:
    """Brier Score计算结果"""
    score: float  # 0-1，越小越好
    count: int  # 已结算预测数
    calibrated: bool  # 是否校准良好
    vs_baseline: Optional[float]  # 与基线比较的改善幅度
    calibration_curve: Optional[List[Dict[str, float]]]  # 校准曲线数据点


@dataclass
class SettlementResult:
    """结算结果"""
    forecast_id: str
    outcome: str  # "hit", "miss", "falsified", "unresolved"
    brier_score: Optional[float]
    settled_at: datetime
    reason: str


class ForecastService:
    """
    M8 预测登记与结算服务
    
    核心规则：
    1. 预测登记：保存预测+证据快照+证伪锚点+到期日
    2. 监测：收集新证据，不覆盖原始预测
    3. 结算：到期后按预先规则判定
    4. 回测：计算Brier Score，与基线比较
    5. 校准：评估概率预测的准确性
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.db = get_database()
        self.min_settlement_count = self.settings.forecast_min_settlement_count
    
    def register_forecast(
        self,
        task_id: str,
        event_description: str,
        probability: float,
        time_range_start: datetime,
        time_range_end: datetime,
        falsifiable_anchor: str,
        premises: List[str],
        evidence_snapshot: Dict[str, Any]
    ) -> ForecastRecord:
        """
        登记预测
        
        关键：
        - 只追加，不覆盖
        - 保存登记时的证据快照
        - 证伪锚点必须明确
        """
        # 验证概率范围
        if not 0 <= probability <= 1:
            raise ValueError(f"概率必须在0-1之间，当前值：{probability}")
        
        # 验证时间范围
        if time_range_end <= time_range_start:
            raise ValueError("时间范围结束必须晚于开始")
        
        # 验证证伪锚点非空
        if not falsifiable_anchor or not falsifiable_anchor.strip():
            raise ValueError("证伪锚点不能为空")
        
        # 生成预测记录
        forecast = ForecastRecord(
            forecast_id=str(uuid.uuid4()),
            event_description=event_description,
            probability=probability,
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            falsifiable_anchor=falsifiable_anchor,
            premises=premises,
            registered_at=datetime.now(),
            evidence_snapshot=evidence_snapshot,
            task_id=task_id
        )
        
        # 写入数据库（只追加）
        self.db.register_forecast(forecast)
        
        # 记录审计日志
        self._log_forecast_registration(forecast)
        
        return forecast
    
    def settle_forecast(
        self,
        forecast_id: str,
        actual_outcome: bool,
        evaluation_rules: Optional[Dict[str, Any]] = None
    ) -> SettlementResult:
        """
        结算预测
        
        Args:
            forecast_id: 预测ID
            actual_outcome: 实际结果（True/False）
            evaluation_rules: 评估规则（可选，默认使用预定义规则）
        
        Returns:
            SettlementResult: 结算结果
        """
        # 获取预测记录
        # 简化实现：从数据库查询
        forecasts = self.db.get_unsettled_forecasts()
        forecast = next((f for f in forecasts if f.forecast_id == forecast_id), None)
        
        if not forecast:
            raise ValueError(f"预测 {forecast_id} 不存在或已结算")
        
        # 判断结果
        predicted = forecast.probability >= 0.5  # 简化：概率≥0.5预测为True
        
        if predicted and actual_outcome:
            outcome = "hit"
            reason = "预测正确：预测为True，实际为True"
        elif not predicted and not actual_outcome:
            outcome = "hit"
            reason = "预测正确：预测为False，实际为False"
        elif predicted and not actual_outcome:
            outcome = "miss"
            reason = "预测错误：预测为True，实际为False"
        else:
            outcome = "miss"
            reason = "预测错误：预测为False，实际为True"
        
        # 检查证伪锚点
        if evaluation_rules and "falsified" in evaluation_rules:
            if evaluation_rules["falsified"]:
                outcome = "falsified"
                reason = "证伪锚点命中"
        
        # 计算Brier Score
        brier = self._calculate_single_brier(forecast.probability, actual_outcome)
        
        # 更新数据库
        self.db.settle_forecast(forecast_id, outcome, brier)
        
        # 记录审计
        self._log_forecast_settlement(forecast_id, outcome, brier, reason)
        
        return SettlementResult(
            forecast_id=forecast_id,
            outcome=outcome,
            brier_score=brier,
            settled_at=datetime.now(),
            reason=reason
        )
    
    def calculate_brier_score(
        self,
        forecasts: Optional[List[ForecastRecord]] = None
    ) -> BrierScoreResult:
        """
        计算累计Brier Score
        
        Brier Score = (1/N) * Σ(predicted_prob - actual_outcome)²
        
        越小越好，0表示完美预测
        """
        if forecasts is None:
            # 获取所有已结算的预测（从数据库查询）
            forecasts = self.db.get_settled_forecasts()
        else:
            # 传入的预测对象可能是内存中的旧引用，需要从DB刷新状态
            all_settled = self.db.get_settled_forecasts()
            settled_ids = {f.forecast_id for f in all_settled}
            refreshed = []
            for f in forecasts:
                if f.forecast_id in settled_ids:
                    # 用DB中的最新版本替换
                    latest = next(x for x in all_settled if x.forecast_id == f.forecast_id)
                    refreshed.append(latest)
                elif f.settled and f.outcome in ("hit", "miss"):
                    refreshed.append(f)
            forecasts = refreshed
        
        settled = [f for f in forecasts if f.settled and f.outcome in ("hit", "miss")]
        
        if len(settled) == 0:
            return BrierScoreResult(
                score=0.0,
                count=0,
                calibrated=False,
                vs_baseline=None,
                calibration_curve=None
            )
        
        # 计算Brier Score
        total_score = 0.0
        for f in settled:
            actual = 1.0 if f.outcome == "hit" else 0.0
            total_score += (f.probability - actual) ** 2
        
        avg_score = total_score / len(settled)
        
        # 与基线比较
        baseline_score = self._calculate_baseline_score(settled)
        vs_baseline = baseline_score - avg_score if baseline_score else None
        
        # 生成校准曲线数据点
        calibration_curve = self._generate_calibration_curve(settled)
        
        # 判断是否校准良好（偏差<5%）
        calibrated = self._check_calibration(calibration_curve)
        
        return BrierScoreResult(
            score=avg_score,
            count=len(settled),
            calibrated=calibrated,
            vs_baseline=vs_baseline,
            calibration_curve=calibration_curve
        )
    
    def get_unsettled_forecasts(self) -> List[ForecastRecord]:
        """获取未结算的预测"""
        return self.db.get_unsettled_forecasts()
    
    def check_due_forecasts(self) -> List[ForecastRecord]:
        """检查到期待结算的预测"""
        now = datetime.now()
        unsettled = self.db.get_unsettled_forecasts()
        
        due = [
            f for f in unsettled
            if f.time_range_end <= now
        ]
        
        return due
    
    def _calculate_single_brier(self, probability: float, actual: bool) -> float:
        """计算单个预测的Brier Score"""
        actual_value = 1.0 if actual else 0.0
        return (probability - actual_value) ** 2
    
    def _calculate_baseline_score(self, forecasts: List[ForecastRecord]) -> float:
        """
        计算基线Brier Score
        
        基线策略：始终预测基率（历史平均概率）
        """
        if not forecasts:
            return 0.0
        
        # 计算基率
        hit_count = sum(1 for f in forecasts if f.outcome == "hit")
        base_rate = hit_count / len(forecasts)
        
        # 基线策略的Brier Score
        total = 0.0
        for f in forecasts:
            actual = 1.0 if f.outcome == "hit" else 0.0
            total += (base_rate - actual) ** 2
        
        return total / len(forecasts)
    
    def _generate_calibration_curve(
        self,
        forecasts: List[ForecastRecord]
    ) -> List[Dict[str, float]]:
        """
        生成校准曲线数据点
        
        将预测按概率分桶，计算每桶的实际命中率
        """
        # 分桶：0-0.1, 0.1-0.2, ..., 0.9-1.0
        bins = [(i * 0.1, (i + 1) * 0.1) for i in range(10)]
        
        curve = []
        for low, high in bins:
            bin_forecasts = [f for f in forecasts if low <= f.probability < high]
            
            if not bin_forecasts:
                continue
            
            hit_count = sum(1 for f in bin_forecasts if f.outcome == "hit")
            hit_rate = hit_count / len(bin_forecasts)
            avg_predicted = sum(f.probability for f in bin_forecasts) / len(bin_forecasts)
            
            curve.append({
                "predicted": avg_predicted,
                "actual": hit_rate,
                "count": len(bin_forecasts)
            })
        
        return curve
    
    def _check_calibration(self, curve: List[Dict[str, float]]) -> bool:
        """检查校准是否良好（偏差<5%）"""
        if not curve:
            return False
        
        total_deviation = 0.0
        for point in curve:
            deviation = abs(point["predicted"] - point["actual"])
            total_deviation += deviation
        
        avg_deviation = total_deviation / len(curve)
        return avg_deviation < 0.05  # 5%阈值
    
    def _log_forecast_registration(self, forecast: ForecastRecord):
        """记录预测登记审计日志"""
        audit = AuditLog(
            log_id=str(uuid.uuid4()),
            action="forecast_registered",
            actor="forecast_service",
            details={
                "forecast_id": forecast.forecast_id,
                "event": forecast.event_description,
                "probability": forecast.probability,
                "time_range": f"{forecast.time_range_start} - {forecast.time_range_end}",
                "falsifiable_anchor": forecast.falsifiable_anchor,
                "premises_count": len(forecast.premises)
            },
            task_id=forecast.task_id
        )
        self.db.log_audit(audit)
    
    def _log_forecast_settlement(
        self,
        forecast_id: str,
        outcome: str,
        brier_score: float,
        reason: str
    ):
        """记录预测结算审计日志"""
        audit = AuditLog(
            log_id=str(uuid.uuid4()),
            action="forecast_settled",
            actor="forecast_service",
            details={
                "forecast_id": forecast_id,
                "outcome": outcome,
                "brier_score": brier_score,
                "reason": reason
            }
        )
        self.db.log_audit(audit)


# 全局实例
_forecast_service: Optional[ForecastService] = None

def get_forecast_service() -> ForecastService:
    global _forecast_service
    if _forecast_service is None:
        _forecast_service = ForecastService()
    return _forecast_service
