"""
独立验证器/红队 (L3 确定性治理层)

不由原分析 Agent 自己控制的复核路径：

主分析 Agent → 形成初步判断 → 独立验证器
    ├─ 来源独立性检查
    ├─ 反证检索
    ├─ 方法与统计检查
    ├─ 预测基线比较
    └─ 证伪锚点检查
→ 治理引擎裁决 → 交付 / 降级 / 阻断

注意：验证器的输出是可审计的验证结果，不自动拥有最终否决权。
真正的阻断条件由确定性规则或明确的人工审批策略定义。
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class VerificationResult(str, Enum):
    VERIFIED = "verified"          # 验证通过
    WEAKENED = "weakened"          # 结论被削弱
    CONTRADICTED = "contradicted"  # 结论被反驳
    INCONCLUSIVE = "inconclusive"  # 无法判定
    NEEDS_REVIEW = "needs_review"  # 需要人工复核


@dataclass
class RedTeamFinding:
    """红队发现"""
    finding_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    check_type: str = ""  # source_independence, counter_evidence, methodology, baseline, falsifiability
    result: VerificationResult = VerificationResult.INCONCLUSIVE
    description: str = ""
    confidence: float = 0.5
    evidence_refs: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RedTeamReport:
    """红队验证报告"""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    original_claim: str = ""
    original_commitment_level: str = ""
    findings: List[RedTeamFinding] = field(default_factory=list)
    overall_result: VerificationResult = VerificationResult.INCONCLUSIVE
    recommended_commitment_level: str = ""
    should_block: bool = False
    block_reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class IndependentVerifier:
    """
    独立验证器（红队）
    
    职责：
    1. 来源独立性检查 - 验证证据是否来自真正独立的来源
    2. 反证检索 - 主动搜索反面证据
    3. 方法与统计检查 - 验证分析方法是否适当
    4. 预测基线比较 - 与简单基线对比
    5. 证伪锚点检查 - 验证证伪条件是否明确
    """
    
    def __init__(self):
        self.verification_history: List[RedTeamReport] = []
    
    async def verify(
        self,
        task_id: str,
        claim: str,
        commitment_level: str,
        evidence_list: List[Dict[str, Any]],
        methodology: Dict[str, Any],
        forecast: Optional[Dict[str, Any]] = None
    ) -> RedTeamReport:
        """
        执行独立验证
        
        Args:
            task_id: 任务ID
            claim: 原始结论/主张
            commitment_level: 原承诺等级
            evidence_list: 证据列表
            methodology: 使用的方法
            forecast: 预测信息（如有）
        
        Returns:
            RedTeamReport: 验证报告
        """
        findings = []
        
        # 1. 来源独立性检查
        source_finding = self._check_source_independence(evidence_list)
        findings.append(source_finding)
        
        # 2. 反证充分性检查
        counter_finding = self._check_counter_evidence(evidence_list)
        findings.append(counter_finding)
        
        # 3. 方法适当性检查
        method_finding = self._check_methodology(methodology, claim)
        findings.append(method_finding)
        
        # 4. 基线比较
        if forecast:
            baseline_finding = self._check_baseline(forecast)
            findings.append(baseline_finding)
        
        # 5. 证伪锚点检查
        falsifiability_finding = self._check_falsifiability(claim, methodology)
        findings.append(falsifiability_finding)
        
        # 综合判断
        overall_result = self._aggregate_findings(findings)
        recommended_level = self._recommend_commitment_level(
            commitment_level, findings, overall_result
        )
        
        # 判断是否需要阻断
        should_block, block_reason = self._should_block(findings)
        
        report = RedTeamReport(
            task_id=task_id,
            original_claim=claim,
            original_commitment_level=commitment_level,
            findings=findings,
            overall_result=overall_result,
            recommended_commitment_level=recommended_level,
            should_block=should_block,
            block_reason=block_reason
        )
        
        self.verification_history.append(report)
        return report
    
    def _check_source_independence(self, evidence_list: List[Dict]) -> RedTeamFinding:
        """
        来源独立性检查
        
        检查：
        - 多源验证的"源"是否指不同信息生成者
        - 同源转载是否被错误计为多源
        - 是否存在信息回音室效应
        """
        if not evidence_list:
            return RedTeamFinding(
                check_type="source_independence",
                result=VerificationResult.CONTRADICTED,
                description="无证据输入",
                confidence=1.0
            )
        
        # 统计独立来源数
        domains = set()
        organizations = set()
        
        for ev in evidence_list:
            url = ev.get("source_url", "")
            if url:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc
                domains.add(domain)
            
            org = ev.get("organization", "")
            if org:
                organizations.add(org)
        
        total_sources = len(evidence_list)
        unique_domains = len(domains)
        
        # 判断独立性
        independence_ratio = unique_domains / max(total_sources, 1)
        
        if independence_ratio >= 0.7:
            result = VerificationResult.VERIFIED
            desc = f"来源独立性良好: {unique_domains}/{total_sources} 不同域名"
        elif independence_ratio >= 0.4:
            result = VerificationResult.WEAKENED
            desc = f"来源独立性一般: {unique_domains}/{total_sources} 不同域名，可能存在信息同源"
        else:
            result = VerificationResult.CONTRADICTED
            desc = f"来源独立性不足: 仅{unique_domains}个独立来源支撑{total_sources}条证据"
        
        return RedTeamFinding(
            check_type="source_independence",
            result=result,
            description=desc,
            confidence=0.8,
            recommendations=["补充不同立场的独立来源" if result != VerificationResult.VERIFIED else ""]
        )
    
    def _check_counter_evidence(self, evidence_list: List[Dict]) -> RedTeamFinding:
        """
        反证充分性检查
        
        检查：
        - 是否进行了反向检索
        - 反证与证实是否同权重
        - 矛盾证据是否被充分讨论
        """
        if not evidence_list:
            return RedTeamFinding(
                check_type="counter_evidence",
                result=VerificationResult.INCONCLUSIVE,
                description="无证据可检查"
            )
        
        contradictory = [e for e in evidence_list if e.get("is_contradictory", False)]
        ratio = len(contradictory) / len(evidence_list)
        
        if ratio >= 0.2:
            result = VerificationResult.VERIFIED
            desc = f"反证比例合理: {len(contradictory)}/{len(evidence_list)} ({ratio:.0%})"
        elif ratio >= 0.05:
            result = VerificationResult.WEAKENED
            desc = f"反证偏少: {len(contradictory)}/{len(evidence_list)} ({ratio:.0%})，可能确认偏误"
        else:
            result = VerificationResult.WEAKENED
            desc = f"几乎无反证: {len(contradictory)}/{len(evidence_list)}，高度怀疑确认偏误"
        
        return RedTeamFinding(
            check_type="counter_evidence",
            result=result,
            description=desc,
            confidence=0.7,
            recommendations=["增加反向检索轮次" if ratio < 0.2 else ""]
        )
    
    def _check_methodology(self, methodology: Dict, claim: str) -> RedTeamFinding:
        """
        方法适当性检查
        
        检查：
        - 方法是否匹配数据类型
        - 假设条件是否满足
        - 是否存在方法误用（如用相关声称因果）
        """
        method_name = methodology.get("method", "unknown")
        data_chars = methodology.get("data_characteristics", {})
        
        issues = []
        
        # 检查因果声称
        causal_keywords = ["导致", "因果", "引起", "造成", "causes"]
        claims_causality = any(kw in claim for kw in causal_keywords)
        
        if claims_causality and method_name in ["correlation", "granger"]:
            issues.append(f"使用{method_name}方法声称因果关系，方法不当")
        
        # 检查样本量
        sample_size = data_chars.get("sample_size", 0)
        if sample_size < 30 and method_name in ["regression", "time_series"]:
            issues.append(f"样本量{sample_size}过小，不适合{method_name}方法")
        
        if issues:
            result = VerificationResult.WEAKENED
            desc = "方法适当性问题: " + "; ".join(issues)
        else:
            result = VerificationResult.VERIFIED
            desc = f"方法{method_name}使用适当"
        
        return RedTeamFinding(
            check_type="methodology",
            result=result,
            description=desc,
            confidence=0.75
        )
    
    def _check_baseline(self, forecast: Dict) -> RedTeamFinding:
        """
        预测基线比较
        
        检查：
        - 是否比简单基线（历史平均/随机猜测）更好
        - 改进是否具有统计显著性
        """
        predicted_prob = forecast.get("probability", 0.5)
        baseline = forecast.get("baseline_probability", 0.5)
        
        improvement = abs(predicted_prob - baseline)
        
        if improvement > 0.2:
            result = VerificationResult.VERIFIED
            desc = f"预测显著优于基线: 预测{predicted_prob:.2f} vs 基线{baseline:.2f}"
        elif improvement > 0.05:
            result = VerificationResult.INCONCLUSIVE
            desc = f"预测略优于基线: 预测{predicted_prob:.2f} vs 基线{baseline:.2f}，改进有限"
        else:
            result = VerificationResult.WEAKENED
            desc = f"预测接近基线: 预测{predicted_prob:.2f} vs 基线{baseline:.2f}，价值有限"
        
        return RedTeamFinding(
            check_type="baseline",
            result=result,
            description=desc,
            confidence=0.7
        )
    
    def _check_falsifiability(self, claim: str, methodology: Dict) -> RedTeamFinding:
        """
        证伪锚点检查
        
        检查：
        - 结论是否有明确的证伪条件
        - 证伪条件是否可观测
        - 到期日是否合理
        """
        falsifiable_anchor = methodology.get("falsifiable_anchor", "")
        
        if not falsifiable_anchor:
            return RedTeamFinding(
                check_type="falsifiability",
                result=VerificationResult.WEAKENED,
                description="缺少明确的证伪锚点",
                confidence=0.9,
                recommendations=["必须声明：什么情况下结论会被证伪"]
            )
        
        # 检查证伪锚点是否具体
        vague_terms = ["可能", "大概", "某种程度上", "也许"]
        is_vague = any(term in falsifiable_anchor for term in vague_terms)
        
        if is_vague:
            result = VerificationResult.WEAKENED
            desc = f"证伪锚点含糊: '{falsifiable_anchor}'，需要更精确的条件"
        else:
            result = VerificationResult.VERIFIED
            desc = f"证伪锚点明确: '{falsifiable_anchor}'"
        
        return RedTeamFinding(
            check_type="falsifiability",
            result=result,
            description=desc,
            confidence=0.85
        )
    
    def _aggregate_findings(self, findings: List[RedTeamFinding]) -> VerificationResult:
        """综合所有发现"""
        if not findings:
            return VerificationResult.INCONCLUSIVE
        
        # 统计各结果数量
        results = [f.result for f in findings]
        
        if VerificationResult.CONTRADICTED in results:
            return VerificationResult.CONTRADICTED
        if results.count(VerificationResult.WEAKENED) >= 2:
            return VerificationResult.WEAKENED
        if all(r == VerificationResult.VERIFIED for r in results):
            return VerificationResult.VERIFIED
        if VerificationResult.WEAKENED in results:
            return VerificationResult.WEAKENED
        
        return VerificationResult.INCONCLUSIVE
    
    def _recommend_commitment_level(
        self,
        original_level: str,
        findings: List[RedTeamFinding],
        overall: VerificationResult
    ) -> str:
        """根据验证结果推荐承诺等级"""
        level_order = {"A": 4, "B": 3, "C": 2, "D": 1}
        current_rank = level_order.get(original_level, 2)
        
        if overall == VerificationResult.CONTRADICTED:
            return "D"
        elif overall == VerificationResult.WEAKENED:
            # 降一级
            new_rank = max(1, current_rank - 1)
            return {4: "A", 3: "B", 2: "C", 1: "D"}.get(new_rank, "C")
        elif overall == VerificationResult.VERIFIED:
            return original_level
        else:
            return original_level
    
    def _should_block(self, findings: List[RedTeamFinding]) -> tuple:
        """判断是否应该阻断"""
        for finding in findings:
            # 高置信度反驳 → 阻断
            if finding.result == VerificationResult.CONTRADICTED and finding.confidence >= 0.8:
                return True, f"红队发现高置信度反驳: {finding.description}"
        
        # 多个反驳 → 阻断
        contradicted_count = sum(1 for f in findings if f.result == VerificationResult.CONTRADICTED)
        if contradicted_count >= 2:
            return True, "多个检查项发现严重问题"
        
        # 高置信度削弱（如证伪锚点缺失、方法不适当）→ 也应阻断
        for finding in findings:
            if finding.result == VerificationResult.WEAKENED and finding.confidence >= 0.8:
                return True, f"红队发现高置信度削弱: {finding.description}"
        
        return False, ""
    
    def get_verification_stats(self) -> Dict[str, Any]:
        """验证统计"""
        total = len(self.verification_history)
        if not total:
            return {"total_verifications": 0}
        
        result_counts = {}
        for report in self.verification_history:
            r = report.overall_result.value
            result_counts[r] = result_counts.get(r, 0) + 1
        
        return {
            "total_verifications": total,
            "by_result": result_counts,
            "block_rate": sum(1 for r in self.verification_history if r.should_block) / total
        }
