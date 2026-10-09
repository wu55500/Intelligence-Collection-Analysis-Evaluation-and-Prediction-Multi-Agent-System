"""
M10 告警引擎模块
支持实时监控、阈值告警、前提失灵报警
"""

import asyncio
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import uuid


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    FATAL = "fatal"


class AlertType(str, Enum):
    THRESHOLD = "threshold"  # 阈值告警
    PREMISE_FAILURE = "premise_failure"  # 前提失灵
    MODEL_DRIFT = "model_drift"  # 模型漂移
    EVIDENCE_CONFLICT = "evidence_conflict"  # 证据冲突
    TIMEOUT = "timeout"  # 超时


@dataclass
class Alert:
    """告警记录"""
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    alert_type: AlertType = AlertType.THRESHOLD
    severity: AlertSeverity = AlertSeverity.WARNING
    title: str = ""
    description: str = ""
    task_id: str = ""
    metric_name: str = ""
    metric_value: float = 0.0
    threshold_value: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    is_acknowledged: bool = False
    resolved_at: Optional[datetime] = None


@dataclass
class AlertRule:
    """告警规则"""
    rule_id: str
    metric_name: str
    condition: str  # ">", "<", ">=", "<=", "==", "!="
    threshold: float
    severity: AlertSeverity
    cooldown_seconds: int = 300
    description: str = ""


class AlertEngine:
    """
    告警引擎
    
    支持：
    - 阈值告警（指标超出范围）
    - 前提失灵报警（预测前提不满足）
    - 模型漂移检测
    - 证据冲突告警
    - 冷却期防止告警风暴
    """
    
    def __init__(self):
        self.rules: List[AlertRule] = []
        self.alerts: List[Alert] = []
        self._last_triggered: Dict[str, datetime] = {}
        self._callbacks: List[Callable] = []
    
    def add_rule(self, rule: AlertRule):
        """添加告警规则"""
        self.rules.append(rule)
    
    def add_callback(self, callback: Callable):
        """添加告警回调"""
        self._callbacks.append(callback)
    
    async def check_metric(self, metric_name: str, value: float, 
                          task_id: str = "") -> List[Alert]:
        """检查指标是否触发告警"""
        triggered = []
        
        for rule in self.rules:
            if rule.metric_name != metric_name:
                continue
            
            # 冷却期检查
            if self._in_cooldown(rule.rule_id):
                continue
            
            # 条件检查
            if self._evaluate_condition(rule.condition, value, rule.threshold):
                alert = Alert(
                    alert_type=AlertType.THRESHOLD,
                    severity=rule.severity,
                    title=f"告警: {metric_name} {rule.condition} {rule.threshold}",
                    description=rule.description or f"{metric_name}当前值{value}触发告警",
                    task_id=task_id,
                    metric_name=metric_name,
                    metric_value=value,
                    threshold_value=rule.threshold
                )
                
                self.alerts.append(alert)
                self._last_triggered[rule.rule_id] = datetime.now()
                triggered.append(alert)
                
                # 触发回调
                for callback in self._callbacks:
                    try:
                        await callback(alert) if asyncio.iscoroutinefunction(callback) else callback(alert)
                    except Exception:
                        pass
        
        return triggered
    
    async def check_premises(self, task_id: str, premises: List[Dict[str, Any]]) -> List[Alert]:
        """检查预测前提是否失灵"""
        alerts = []
        
        for premise in premises:
            premise_id = premise.get("premise_id", "")
            condition = premise.get("condition", "")
            current_status = premise.get("status", "unknown")
            
            if current_status == "failed" or not self._evaluate_status(condition, premise.get("value")):
                alert = Alert(
                    alert_type=AlertType.PREMISE_FAILURE,
                    severity=AlertSeverity.CRITICAL,
                    title=f"前提失灵: {premise_id}",
                    description=f"预测前提 '{condition}' 不再满足",
                    task_id=task_id
                )
                
                self.alerts.append(alert)
                alerts.append(alert)
        
        return alerts
    
    def check_evidence_conflict(self, evidence_list: List[Dict]) -> List[Alert]:
        """检查证据冲突"""
        alerts = []
        
        contradictory = [e for e in evidence_list if e.get("is_contradictory", False)]
        if len(contradictory) > len(evidence_list) * 0.3:  # 超过30%为反证
            alert = Alert(
                alert_type=AlertType.EVIDENCE_CONFLICT,
                severity=AlertSeverity.WARNING,
                title="证据冲突过高",
                description=f"反证比例={len(contradictory)}/{len(evidence_list)}",
                metric_value=len(contradictory) / max(len(evidence_list), 1),
                threshold_value=0.3
            )
            self.alerts.append(alert)
            alerts.append(alert)
        
        return alerts
    
    def get_active_alerts(self, severity: Optional[AlertSeverity] = None) -> List[Alert]:
        """获取活跃告警"""
        active = [a for a in self.alerts if a.resolved_at is None]
        if severity:
            active = [a for a in active if a.severity == severity]
        return active
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警"""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.is_acknowledged = True
                return True
        return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """解除告警"""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.resolved_at = datetime.now()
                return True
        return False
    
    def _evaluate_condition(self, condition: str, value: float, threshold: float) -> bool:
        """评估条件"""
        if condition == ">": return value > threshold
        elif condition == "<": return value < threshold
        elif condition == ">=": return value >= threshold
        elif condition == "<=": return value <= threshold
        elif condition == "==": return value == threshold
        elif condition == "!=": return value != threshold
        return False
    
    def _evaluate_status(self, condition: str, value: Any) -> bool:
        """评估状态"""
        if value is None:
            return False
        return True
    
    def _in_cooldown(self, rule_id: str) -> bool:
        """检查冷却期"""
        last = self._last_triggered.get(rule_id)
        if last is None:
            return False
        rule = next((r for r in self.rules if r.rule_id == rule_id), None)
        if rule is None:
            return False
        return (datetime.now() - last).total_seconds() < rule.cooldown_seconds
    
    def get_alert_stats(self) -> Dict[str, Any]:
        """告警统计"""
        active = self.get_active_alerts()
        return {
            "total_alerts": len(self.alerts),
            "active_alerts": len(active),
            "by_severity": {
                s.value: len([a for a in active if a.severity == s])
                for s in AlertSeverity
            },
            "by_type": {
                t.value: len([a for a in active if a.alert_type == t])
                for t in AlertType
            }
        }
