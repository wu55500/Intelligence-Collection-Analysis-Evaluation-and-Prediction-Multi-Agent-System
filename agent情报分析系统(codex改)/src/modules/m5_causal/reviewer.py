"""
M5 因果推断审查模块

P0需求：
- 因果识别门：点名策略(格兰杰/DID/IV/RDD)+关键假设
- 只有格兰杰或纯相关→只能写「预测性关联」禁写「导致」
- 无干预对照：「X带来增长」必答有无对照组
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class CausalMethod:
    """因果推断方法"""
    method_name: str  # "granger", "did", "iv", "rdd"
    assumptions: List[str]
    requirements: List[str]
    is_applicable: bool
    reason: str


@dataclass
class CausalReviewResult:
    """因果审查结果"""
    review_id: str
    claim: str
    reviewed_methods: List[CausalMethod]
    can_claim_causality: bool
    allowed_statement: str  # "预测性关联", "条件性因果", "强因果"
    counterfactual_check: Dict[str, Any]
    warnings: List[str]
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class CausalReviewer:
    """
    因果推断审查器
    
    职责：
    1. 检查因果声明是否合理
    2. 验证使用的因果推断方法的假设是否满足
    3. 强制区分"相关"和"因果"
    4. 要求对照组检查
    """
    
    METHOD_DATABASE = {
        "granger": {
            "name": "格兰杰因果",
            "assumptions": [
                "时间序列平稳",
                "无遗漏变量",
                "线性关系"
            ],
            "requirements": [
                "时间序列数据",
                "足够的时间点（建议≥50）"
            ],
            "max_claim": "预测性关联",  # 格兰杰不等于真因果
            "description": "时间上的预测关系，不等于结构因果"
        },
        "did": {
            "name": "双重差分(DID)",
            "assumptions": [
                "平行趋势假设",
                "无溢出效应",
                "处理组和对照组可比"
            ],
            "requirements": [
                "处理组和对照组",
                "政策/干预前后的数据"
            ],
            "max_claim": "条件性因果",
            "description": "需要平行趋势假设成立"
        },
        "iv": {
            "name": "工具变量(IV)",
            "assumptions": [
                "工具变量外生性",
                "工具变量与内生变量相关",
                "排他性约束"
            ],
            "requirements": [
                "有效的工具变量",
                "两阶段最小二乘法"
            ],
            "max_claim": "条件性因果",
            "description": "依赖工具变量的有效性"
        },
        "rdd": {
            "name": "断点回归(RDD)",
            "assumptions": [
                "断点处无精确操纵",
                "处理分配在断点处随机"
            ],
            "requirements": [
                "明确的断点/阈值",
                "断点两侧足够样本"
            ],
            "max_claim": "局部因果",
            "description": "仅适用于断点附近的局部因果效应"
        }
    }
    
    def review(
        self,
        claim: str,
        proposed_method: str,
        data_characteristics: Dict[str, Any]
    ) -> CausalReviewResult:
        """
        审查因果声明
        
        Args:
            claim: 因果声明（如"X导致Y"）
            proposed_method: 提议使用的因果推断方法
            data_characteristics: 数据特征
        """
        import uuid
        
        # 1. 检查方法适用性
        method_info = self.METHOD_DATABASE.get(proposed_method)
        if not method_info:
            return CausalReviewResult(
                review_id=str(uuid.uuid4()),
                claim=claim,
                reviewed_methods=[],
                can_claim_causality=False,
                allowed_statement="无法评估：未知方法",
                counterfactual_check={},
                warnings=["未识别的因果推断方法"]
            )
        
        # 2. 验证假设
        assumptions_met, unmet_assumptions = self._check_assumptions(
            method_info["assumptions"],
            data_characteristics
        )
        
        # 3. 验证要求
        requirements_met, unmet_requirements = self._check_requirements(
            method_info["requirements"],
            data_characteristics
        )
        
        # 4. 确定允许的因果声明级别
        can_claim = assumptions_met and requirements_met
        allowed_statement = method_info["max_claim"] if can_claim else "预测性关联"
        
        # 5. 对照组检查
        counterfactual_check = self._check_counterfactual(claim, data_characteristics)
        
        # 6. 生成警告
        warnings = []
        if not assumptions_met:
            warnings.append(f"假设未满足: {', '.join(unmet_assumptions)}")
        if not requirements_met:
            warnings.append(f"要求未满足: {', '.join(unmet_requirements)}")
        if not counterfactual_check.get("has_counterfactual"):
            warnings.append("缺少对照组/反事实分析")
        
        # 格兰杰方法的特殊警告
        if proposed_method == "granger" and "导致" in claim:
            warnings.append("格兰杰因果不等于真因果，应使用'预测性关联'表述")
        
        # 7. 构建方法记录
        reviewed_method = CausalMethod(
            method_name=proposed_method,
            assumptions=method_info["assumptions"],
            requirements=method_info["requirements"],
            is_applicable=can_claim,
            reason=method_info["description"]
        )
        
        return CausalReviewResult(
            review_id=str(uuid.uuid4()),
            claim=claim,
            reviewed_methods=[reviewed_method],
            can_claim_causality=can_claim,
            allowed_statement=allowed_statement,
            counterfactual_check=counterfactual_check,
            warnings=warnings
        )
    
    def _check_assumptions(
        self,
        assumptions: List[str],
        data_chars: Dict[str, Any]
    ) -> tuple[bool, List[str]]:
        """检查假设是否满足"""
        unmet = []
        
        for assumption in assumptions:
            # 简化的假设检查逻辑
            # 实际应该根据具体假设和数据特征进行详细验证
            if "平稳" in assumption and not data_chars.get("is_stationary", False):
                unmet.append(assumption)
            elif "平行趋势" in assumption and not data_chars.get("has_parallel_trend", False):
                unmet.append(assumption)
            elif "外生性" in assumption and not data_chars.get("has_exogenous_iv", False):
                unmet.append(assumption)
        
        return len(unmet) == 0, unmet
    
    def _check_requirements(
        self,
        requirements: List[str],
        data_chars: Dict[str, Any]
    ) -> tuple[bool, List[str]]:
        """检查要求是否满足"""
        unmet = []
        
        for req in requirements:
            if "时间序列" in req and not data_chars.get("is_time_series", False):
                unmet.append(req)
            elif "足够的时间点" in req:
                time_points = data_chars.get("time_points", 0)
                if time_points < 50:
                    unmet.append(f"{req}（当前{time_points}个）")
            elif "对照组" in req and not data_chars.get("has_control_group", False):
                unmet.append(req)
        
        return len(unmet) == 0, unmet
    
    def _check_counterfactual(
        self,
        claim: str,
        data_chars: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        检查反事实/对照组
        
        规则：「X带来增长」必答有无对照组
        """
        has_counterfactual = data_chars.get("has_control_group", False) or \
                            data_chars.get("has_counterfactual", False)
        
        return {
            "has_counterfactual": has_counterfactual,
            "control_group_type": data_chars.get("control_group_type"),
            "counterfactual_method": data_chars.get("counterfactual_method"),
            "recommendation": "建议增加对照组或反事实分析" if not has_counterfactual else "对照组检查通过"
        }
    
    def get_allowed_language(self, review_result: CausalReviewResult) -> Dict[str, Any]:
        """
        获取允许使用的语言
        
        返回：
        - allowed_terms: 允许使用的术语
        - forbidden_terms: 禁止使用的术语
        - suggested_rewording: 建议的重新表述
        """
        if review_result.can_claim_causality:
            if review_result.allowed_statement == "强因果":
                return {
                    "allowed_terms": ["导致", "因果效应", "因果"],
                    "forbidden_terms": [],
                    "suggested_rewording": review_result.claim
                }
            elif review_result.allowed_statement == "条件性因果":
                return {
                    "allowed_terms": ["在...条件下导致", "条件性因果效应"],
                    "forbidden_terms": ["必然导致", "绝对因果"],
                    "suggested_rewording": f"在满足{review_result.reviewed_methods[0].assumptions}的条件下，{review_result.claim}"
                }
            elif review_result.allowed_statement == "局部因果":
                return {
                    "allowed_terms": ["在断点附近导致", "局部因果效应"],
                    "forbidden_terms": ["全局因果", "普遍因果"],
                    "suggested_rewording": f"在断点附近，{review_result.claim}"
                }
        
        # 默认：只能声称预测性关联
        return {
            "allowed_terms": ["预测", "预测性关联", "时间上先于", "与...相关"],
            "forbidden_terms": ["导致", "因果", "引起", "造成"],
            "suggested_rewording": review_result.claim.replace("导致", "预测").replace("因果", "预测性关联")
        }
