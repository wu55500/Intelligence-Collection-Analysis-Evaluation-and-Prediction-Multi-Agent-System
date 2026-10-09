"""
M14 权限治理模块
支持权限检查、风险评估、权限升级/降级
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class PermissionLevel(str, Enum):
    L1 = "L1"  # 自主执行
    L2 = "L2"  # 确认后执行
    L3 = "L3"  # 人工主导


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PermissionRequest:
    """权限请求"""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_type: str = ""
    action_description: str = ""
    required_level: PermissionLevel = PermissionLevel.L1
    current_level: PermissionLevel = PermissionLevel.L1
    risk_level: RiskLevel = RiskLevel.LOW
    context: Dict[str, Any] = field(default_factory=dict)
    approved: bool = False
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class RiskAssessment:
    """风险评估"""
    risk_level: RiskLevel
    rpn_score: int  # Risk Priority Number
    severity: int  # 1-10
    occurrence: int  # 1-10
    detection: int  # 1-10
    has_dangerous_keyword: bool = False
    recommendation: str = ""


class PermissionGovernor:
    """
    权限治理器
    
    支持：
    - 权限级别管理
    - 风险评估（RPN）
    - 危险关键词检测
    - 权限升级/降级
    - 审批流程
    """
    
    DANGEROUS_KEYWORDS = ["删除", "转账", "购买", "发布", "隐私", "密码", "支付"]
    
    def __init__(self):
        self.current_level = PermissionLevel.L1
        self.requests: List[PermissionRequest] = []
        self._max_level_ever = PermissionLevel.L1  # 单向收紧
    
    def assess_risk(self, action_type: str, action_description: str,
                   context: Optional[Dict[str, Any]] = None) -> RiskAssessment:
        """
        评估操作风险
        
        RPN = 严重度 × 发生度 × 探测度
        """
        # 检测危险关键词
        has_dangerous = any(kw in action_description for kw in self.DANGEROUS_KEYWORDS)
        
        # 计算严重度
        severity = self._calculate_severity(action_type, action_description, has_dangerous)
        
        # 计算发生度
        occurrence = self._calculate_occurrence(action_type, context)
        
        # 计算探测度
        detection = self._calculate_detection(action_type, context)
        
        # RPN
        rpn = severity * occurrence * detection
        
        # 风险等级
        if rpn >= 100 or severity >= 8:
            risk_level = RiskLevel.CRITICAL
        elif rpn >= 50 or severity >= 6:
            risk_level = RiskLevel.HIGH
        elif rpn >= 20:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW
        
        # 推荐权限
        if risk_level == RiskLevel.CRITICAL:
            recommendation = "需要L3权限，必须人工审批"
        elif risk_level == RiskLevel.HIGH:
            recommendation = "建议L2权限，需要确认"
        else:
            recommendation = "L1权限可执行"
        
        return RiskAssessment(
            risk_level=risk_level,
            rpn_score=rpn,
            severity=severity,
            occurrence=occurrence,
            detection=detection,
            has_dangerous_keyword=has_dangerous,
            recommendation=recommendation
        )
    
    def request_permission(self, action_type: str, action_description: str,
                          context: Optional[Dict[str, Any]] = None) -> PermissionRequest:
        """请求权限"""
        risk = self.assess_risk(action_type, action_description, context)
        
        # 确定所需权限级别
        if risk.risk_level == RiskLevel.CRITICAL or risk.has_dangerous_keyword:
            required_level = PermissionLevel.L3
        elif risk.risk_level in [RiskLevel.HIGH, RiskLevel.MEDIUM]:
            required_level = PermissionLevel.L2
        else:
            required_level = PermissionLevel.L1
        
        request = PermissionRequest(
            action_type=action_type,
            action_description=action_description,
            required_level=required_level,
            current_level=self.current_level,
            risk_level=risk.risk_level,
            context=context or {}
        )
        
        # 自动审批（如果当前权限足够）
        if self._can_auto_approve(request):
            request.approved = True
            request.approved_by = "system"
            request.approved_at = datetime.now()
        
        self.requests.append(request)
        return request
    
    def _can_auto_approve(self, request: PermissionRequest) -> bool:
        """检查是否可以自动审批"""
        level_order = {PermissionLevel.L1: 1, PermissionLevel.L2: 2, PermissionLevel.L3: 3}
        return level_order[self.current_level] >= level_order[request.required_level]
    
    def approve_request(self, request_id: str, approved_by: str) -> bool:
        """审批请求"""
        for req in self.requests:
            if req.request_id == request_id and not req.approved:
                req.approved = True
                req.approved_by = approved_by
                req.approved_at = datetime.now()
                return True
        return False
    
    def tighten_permission(self, new_level: PermissionLevel) -> bool:
        """收紧权限（单向，只紧不松）"""
        level_order = {PermissionLevel.L1: 1, PermissionLevel.L2: 2, PermissionLevel.L3: 3}
        
        if level_order[new_level] > level_order[self.current_level]:
            self.current_level = new_level
            self._max_level_ever = new_level
            return True
        return False
    
    def get_pending_requests(self) -> List[PermissionRequest]:
        """获取待审批请求"""
        return [r for r in self.requests if not r.approved]
    
    def _calculate_severity(self, action_type: str, description: str, has_dangerous: bool) -> int:
        """计算严重度"""
        base = 3
        if has_dangerous:
            base = 8
        if "删除" in description or "支付" in description:
            base = 9
        return min(base, 10)
    
    def _calculate_occurrence(self, action_type: str, context: Optional[Dict]) -> int:
        """计算发生度"""
        # 简化实现
        if action_type in ["delete", "modify", "transfer"]:
            return 5
        return 3
    
    def _calculate_detection(self, action_type: str, context: Optional[Dict]) -> int:
        """计算探测度"""
        # 简化实现
        if context and context.get("has_audit_log"):
            return 3
        return 5
    
    def get_permission_stats(self) -> Dict[str, Any]:
        """权限统计"""
        total = len(self.requests)
        approved = sum(1 for r in self.requests if r.approved)
        pending = total - approved
        
        return {
            "current_level": self.current_level.value,
            "max_level_ever": self._max_level_ever.value,
            "total_requests": total,
            "approved": approved,
            "pending": pending,
            "approval_rate": approved / total if total > 0 else 0
        }
