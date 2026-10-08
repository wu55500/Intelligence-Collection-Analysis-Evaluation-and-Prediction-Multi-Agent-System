"""
M14 权限治理服务 - 确定性策略执行器

关键设计：
1. 不能让Agent自己决定是否绕过权限
2. 权限单向收紧：只紧不松
3. 危险关键词强制L3
4. RPN风险量化：严重度×发生度×探测度
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass
import uuid

from ..core.schemas import PermissionLevel, PermissionRequest, AuditLog
from ..core.config import get_settings
from ..core.database import get_database


@dataclass
class RiskAssessment:
    """风险评估结果"""
    severity: int  # 1-10 严重度
    occurrence: int  # 1-10 发生度
    detection: int  # 1-10 探测度
    rpn: int  # 风险优先级数 = S × O × D
    is_dangerous: bool  # 是否包含危险关键词
    required_level: PermissionLevel


class PermissionService:
    """
    M14 权限治理服务
    
    三级权限：
    - L1 自主执行：RPN < 27
    - L2 确认后执行：27 ≤ RPN < 100
    - L3 人工主导：RPN ≥ 100 或 严重度 ≥ 8
    
    关键规则：
    - 危险关键词（删除/转账/购买/发布/隐私）强制S≥9，必须L3
    - 权限单向收紧：只能自我收紧，禁止自我放宽
    """
    
    def __init__(self):
        self.settings = get_settings().permission
        self.db = get_database()
        
        # 当前权限级别（运行时状态，只能向下调整）
        self._current_max_level = PermissionLevel.L1
    
    def assess_risk(
        self,
        action_type: str,
        action_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> RiskAssessment:
        """
        评估操作风险
        
        Args:
            action_type: 操作类型
            action_description: 操作描述
            context: 上下文信息
        
        Returns:
            RiskAssessment: 风险评估结果
        """
        # 检测危险关键词
        is_dangerous = any(
            keyword in action_description
            for keyword in self.settings.dangerous_keywords
        )
        
        # 计算风险分数
        severity = self._calculate_severity(action_type, action_description, is_dangerous)
        occurrence = self._calculate_occurrence(action_type, context)
        detection = self._calculate_detection(action_type, context)
        
        rpn = severity * occurrence * detection
        
        # 确定所需权限级别
        if severity >= self.settings.l3_min_severity or is_dangerous or rpn >= self.settings.l2_max_rpn:
            required_level = PermissionLevel.L3
        elif rpn >= self.settings.l1_max_rpn:
            required_level = PermissionLevel.L2
        else:
            required_level = PermissionLevel.L1
        
        return RiskAssessment(
            severity=severity,
            occurrence=occurrence,
            detection=detection,
            rpn=rpn,
            is_dangerous=is_dangerous,
            required_level=required_level
        )
    
    def can_execute(
        self,
        action_type: str,
        action_description: str,
        current_level: PermissionLevel,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        检查是否可以执行操作
        
        Returns:
            {
                "allowed": bool,
                "required_level": PermissionLevel,
                "current_level": PermissionLevel,
                "risk_assessment": RiskAssessment,
                "reason": str
            }
        """
        risk = self.assess_risk(action_type, action_description, context)
        
        # 权限检查：当前级别必须 >= 所需级别
        level_order = {
            PermissionLevel.L1: 1,
            PermissionLevel.L2: 2,
            PermissionLevel.L3: 3
        }
        
        allowed = level_order[current_level] >= level_order[risk.required_level]
        
        if not allowed:
            reason = f"当前权限{current_level.value}不足，需要{risk.required_level.value}（RPN={risk.rpn}）"
            if risk.is_dangerous:
                reason += "，包含危险关键词"
        else:
            reason = "权限检查通过"
        
        result = {
            "allowed": allowed,
            "required_level": risk.required_level,
            "current_level": current_level,
            "risk_assessment": risk,
            "reason": reason
        }
        
        # 记录审计日志
        self._log_permission_check(action_type, risk, current_level, allowed)
        
        return result
    
    def request_approval(
        self,
        task_id: str,
        action_type: str,
        action_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> PermissionRequest:
        """
        创建权限请求（需要审批）
        
        Returns:
            PermissionRequest: 待审批的请求
        """
        risk = self.assess_risk(action_type, action_description, context)
        
        request = PermissionRequest(
            request_id=str(uuid.uuid4()),
            action_type=action_type,
            impact_level=self._map_rpn_to_impact(risk.rpn),
            requires_approval=risk.required_level in (PermissionLevel.L2, PermissionLevel.L3),
            task_id=task_id
        )
        
        # 记录请求
        self._log_permission_request(request, risk)
        
        return request
    
    def approve_request(
        self,
        request_id: str,
        approved_by: str,
        reason: Optional[str] = None
    ) -> bool:
        """审批权限请求"""
        # 这里应该从数据库查询请求并更新状态
        # 简化实现：直接记录审批
        
        audit = AuditLog(
            log_id=str(uuid.uuid4()),
            action="permission_approved",
            actor=approved_by,
            details={
                "request_id": request_id,
                "reason": reason or "审批通过"
            }
        )
        self.db.log_audit(audit)
        
        return True
    
    def tighten_permission(self, new_max_level: PermissionLevel) -> bool:
        """
        收紧权限（单向）
        
        只能向下调整，不能向上放宽
        """
        if not self.settings.monotonic:
            # 如果未启用单向收紧，允许任意调整
            self._current_max_level = new_max_level
            return True
        
        level_order = {
            PermissionLevel.L1: 1,
            PermissionLevel.L2: 2,
            PermissionLevel.L3: 3
        }
        
        # 只允许收紧（提高限制级别 = 数字变大）
        # L1=1 最宽松, L3=3 最严格
        # 收紧: 从1→3 OK, 放宽: 从3→1 拒绝
        if level_order[new_max_level] <= level_order[self._current_max_level]:
            return False  # 拒绝放宽（数字不变或变小）
        
        old_level = self._current_max_level
        self._current_max_level = new_max_level
        
        # 记录审计
        audit = AuditLog(
            log_id=str(uuid.uuid4()),
            action="permission_tightened",
            actor="system",
            details={
                "from": old_level.value,
                "to": new_max_level.value
            }
        )
        self.db.log_audit(audit)
        
        return True
    
    def get_current_max_level(self) -> PermissionLevel:
        """获取当前最高权限级别"""
        return self._current_max_level
    
    def _calculate_severity(
        self,
        action_type: str,
        description: str,
        is_dangerous: bool
    ) -> int:
        """计算严重度（1-10）"""
        base = 3
        
        if is_dangerous:
            base = max(base, 9)  # 危险关键词强制S≥9
        
        # 根据操作类型调整
        severity_map = {
            "delete": 9,
            "transfer": 9,
            "publish": 8,
            "modify": 5,
            "read": 2,
            "query": 1
        }
        
        return max(base, severity_map.get(action_type, 3))
    
    def _calculate_occurrence(
        self,
        action_type: str,
        context: Optional[Dict[str, Any]]
    ) -> int:
        """计算发生度（1-10）"""
        # 基于历史频率或上下文估计
        base = 5
        
        if context and "frequency" in context:
            freq = context["frequency"]
            if freq > 100:
                base = 8
            elif freq > 10:
                base = 5
            else:
                base = 3
        
        return base
    
    def _calculate_detection(
        self,
        action_type: str,
        context: Optional[Dict[str, Any]]
    ) -> int:
        """计算探测度（1-10，越高越难探测）"""
        # 基于操作的可观测性
        base = 5
        
        detectable_actions = {"read", "query", "log"}
        hard_to_detect = {"delete", "modify", "transfer"}
        
        if action_type in detectable_actions:
            base = 2  # 容易探测
        elif action_type in hard_to_detect:
            base = 8  # 难探测
        
        return base
    
    def _map_rpn_to_impact(self, rpn: int) -> str:
        """将RPN映射到影响等级"""
        if rpn >= 200:
            return "critical"
        elif rpn >= 100:
            return "high"
        elif rpn >= 27:
            return "medium"
        else:
            return "low"
    
    def _log_permission_check(
        self,
        action_type: str,
        risk: RiskAssessment,
        current_level: PermissionLevel,
        allowed: bool
    ):
        """记录权限检查日志"""
        audit = AuditLog(
            log_id=str(uuid.uuid4()),
            action="permission_check",
            actor="permission_service",
            details={
                "action_type": action_type,
                "rpn": risk.rpn,
                "severity": risk.severity,
                "required_level": risk.required_level.value,
                "current_level": current_level.value,
                "allowed": allowed
            }
        )
        self.db.log_audit(audit)
    
    def _log_permission_request(
        self,
        request: PermissionRequest,
        risk: RiskAssessment
    ):
        """记录权限请求日志"""
        audit = AuditLog(
            log_id=str(uuid.uuid4()),
            action="permission_request",
            actor="permission_service",
            details={
                "request_id": request.request_id,
                "action_type": request.action_type,
                "impact_level": request.impact_level,
                "rpn": risk.rpn,
                "requires_approval": request.requires_approval
            }
        )
        self.db.log_audit(audit)


# 全局实例
_permission_service: Optional[PermissionService] = None

def get_permission_service() -> PermissionService:
    global _permission_service
    if _permission_service is None:
        _permission_service = PermissionService()
    return _permission_service
