"""
Reflection 自我修正引擎
Agent 执行后自动评估，发现问题并修正
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
import uuid
from enum import Enum


class ReflectionType(str, Enum):
    """反思类型"""
    ERROR_CORRECTION = "error_correction"  # 错误修正
    QUALITY_IMPROVEMENT = "quality_improvement"  # 质量提升
    EFFICIENCY_OPTIMIZATION = "efficiency_optimization"  # 效率优化
    HALLUCINATION_CHECK = "hallucination_check"  # 幻觉检查


@dataclass
class ReflectionResult:
    """反思结果"""
    reflection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    reflection_type: ReflectionType = ReflectionType.QUALITY_IMPROVEMENT
    original_output: str = ""
    issues_found: List[str] = field(default_factory=list)
    corrections: List[str] = field(default_factory=list)
    corrected_output: str = ""
    confidence_before: float = 0.0
    confidence_after: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class ReflectionEngine:
    """
    反思引擎

    实现：
    1. 输出质量评估
    2. 幻觉检测
    3. 逻辑一致性检查
    4. 自动修正建议
    """

    def __init__(self):
        self.reflection_history: List[ReflectionResult] = []

    def reflect(
        self,
        task_type: str,
        original_output: str,
        context: Dict[str, Any],
        confidence: float = 0.5
    ) -> ReflectionResult:
        """
        执行反思

        Args:
            task_type: 任务类型（research, analysis, forecast）
            original_output: 原始输出
            context: 任务上下文
            confidence: 当前置信度

        Returns:
            ReflectionResult: 反思结果
        """
        reflection = ReflectionResult(
            original_output=original_output,
            confidence_before=confidence
        )

        # 1. 幻觉检查
        hallucination_issues = self._check_hallucinations(original_output, context)
        reflection.issues_found.extend(hallucination_issues)

        # 2. 逻辑一致性检查
        logic_issues = self._check_logic_consistency(original_output, context)
        reflection.issues_found.extend(logic_issues)

        # 3. 质量评估
        quality_issues = self._check_quality(original_output, task_type)
        reflection.issues_found.extend(quality_issues)

        # 4. 生成修正建议
        if reflection.issues_found:
            reflection.corrections = self._generate_corrections(
                reflection.issues_found, original_output, context
            )
            reflection.corrected_output = self._apply_corrections(
                original_output, reflection.corrections
            )
            reflection.confidence_after = min(1.0, confidence + 0.1 * len(reflection.corrections))
        else:
            reflection.corrected_output = original_output
            reflection.confidence_after = confidence

        # 记录历史
        self.reflection_history.append(reflection)

        return reflection

    def _check_hallucinations(self, output: str, context: Dict[str, Any]) -> List[str]:
        """检查幻觉（生成不存在的引用或数据）"""
        issues = []

        # 检查是否引用了不存在的证据
        evidence_ids = context.get("evidence_ids", [])
        if "ev-" in output and not evidence_ids:
            issues.append("输出引用了证据，但上下文无证据ID")

        # 检查是否生成了虚假数字
        if self._contains_suspicious_numbers(output):
            issues.append("输出包含可疑的精确数字，可能为幻觉")

        return issues

    def _check_logic_consistency(self, output: str, context: Dict[str, Any]) -> List[str]:
        """检查逻辑一致性"""
        issues = []

        # 检查矛盾陈述
        contradictions = self._find_contradictions(output)
        if contradictions:
            issues.extend(contradictions)

        # 检查与上下文的矛盾
        if context.get("constraint"):
            if not self._respects_constraint(output, context["constraint"]):
                issues.append(f"输出违反了约束: {context['constraint']}")

        return issues

    def _check_quality(self, output: str, task_type: str) -> List[str]:
        """检查输出质量"""
        issues = []

        # 长度检查
        if len(output) < 50:
            issues.append("输出过短，可能不完整")

        # 结构检查
        if task_type == "report" and not self._has_structure(output):
            issues.append("报告缺少结构化标题")

        # 承诺等级检查
        if "结论" in output and "承诺等级" not in output:
            issues.append("包含结论但未声明承诺等级")

        return issues

    def _generate_corrections(
        self,
        issues: List[str],
        original_output: str,
        context: Dict[str, Any]
    ) -> List[str]:
        """生成修正建议"""
        corrections = []

        for issue in issues:
            if "幻觉" in issue:
                corrections.append("删除或标注可疑的引用和数字")
            elif "矛盾" in issue:
                corrections.append("统一矛盾陈述，选择一致的表述")
            elif "约束" in issue:
                corrections.append(f"调整输出以满足约束: {context.get('constraint')}")
            elif "过短" in issue:
                corrections.append("补充必要的分析细节")
            elif "结构" in issue:
                corrections.append("添加结构化标题（背景、分析、结论）")
            elif "承诺等级" in issue:
                corrections.append("添加承诺等级声明")

        return corrections

    def _apply_corrections(self, original_output: str, corrections: List[str]) -> str:
        """应用修正（简化实现，实际应由LLM执行）"""
        # 这里是占位实现，实际需要LLM或规则引擎
        corrected = original_output

        # 添加免责声明
        if any("幻觉" in c for c in corrections):
            corrected += "\n\n[注意: 部分引用和数字可能不准确，需要人工验证]"

        if any("承诺等级" in c for c in corrections):
            corrected += "\n\n承诺等级: C（方向判断，待进一步验证）"

        return corrected

    def _contains_suspicious_numbers(self, text: str) -> bool:
        """检查是否包含可疑数字"""
        import re
        # 查找精确百分比（可能是幻觉）
        percentages = re.findall(r'\d{2,3}\.\d{2,}%', text)
        return len(percentages) > 3

    def _find_contradictions(self, text: str) -> List[str]:
        """查找矛盾陈述"""
        contradictions = []
        # 简化实现：检查明显的矛盾词
        if "增长" in text and "下降" in text:
            contradictions.append("发现矛盾: 同时提到增长和下降")
        return contradictions

    def _respects_constraint(self, output: str, constraint: str) -> bool:
        """检查是否尊重约束"""
        # 简化实现
        return True

    def _has_structure(self, text: str) -> bool:
        """检查是否有结构"""
        structure_markers = ["#", "背景", "分析", "结论", "方法"]
        return any(marker in text for marker in structure_markers)

    def get_reflection_stats(self) -> Dict[str, Any]:
        """获取反思统计"""
        if not self.reflection_history:
            return {"total": 0}

        avg_correction = sum(
            r.confidence_after - r.confidence_before
            for r in self.reflection_history
        ) / len(self.reflection_history)

        return {
            "total": len(self.reflection_history),
            "avg_confidence_improvement": avg_correction,
            "issues_per_reflection": sum(len(r.issues_found) for r in self.reflection_history) / len(self.reflection_history)
        }
