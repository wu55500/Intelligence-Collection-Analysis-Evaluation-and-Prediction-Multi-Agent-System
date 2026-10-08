"""
M13 报告与交付模块

P0需求：
- 13.1 结论先行模板+可证伪锚点+一句话验证建议
- 13.2 声明前置：层级+样本量是结论的一部分不是免责尾巴
- 13.3 逻辑谬误检查：幸存者偏差/确认偏误/后此谬误等
- 13.4 利益链检查：谁受益/谁受损/数据生产者立场
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid

from ...core.schemas import Claim, Evidence, CommitmentLevel, EvidenceQuality


@dataclass
class FallacyCheck:
    """逻辑谬误检查"""
    fallacy_type: str  # "survivorship_bias", "confirmation_bias", "post_hoc", etc.
    detected: bool
    description: str
    suggestion: str


@dataclass
class InterestChainCheck:
    """利益链检查"""
    beneficiaries: List[str]
    losers: List[str]
    data_producer_stance: str
    industry_material_is_sole_basis: bool
    warning: str = ""


@dataclass
class ReportSection:
    """报告段落"""
    section_type: str  # "conclusion", "declaration", "evidence", "methodology", "limitations", "falsification"
    title: str
    content: str
    priority: int  # 排序优先级


@dataclass
class GeneratedReport:
    """生成的报告"""
    report_id: str
    task_id: str
    sections: List[ReportSection]
    fallacy_checks: List[FallacyCheck]
    interest_chain_check: Optional[InterestChainCheck]
    commitment_level: CommitmentLevel
    generated_at: datetime = None
    full_text: str = ""
    
    def __post_init__(self):
        if self.generated_at is None:
            self.generated_at = datetime.now()
        if not self.full_text:
            self.full_text = self._assemble_text()
    
    def _assemble_text(self) -> str:
        lines = []
        for section in sorted(self.sections, key=lambda s: s.priority):
            lines.append(f"## {section.title}\n")
            lines.append(section.content)
            lines.append("")
        return "\n".join(lines)


class ReportGenerator:
    """
    报告生成器
    
    职责：
    1. 结论先行
    2. 声明前置（层级+样本量）
    3. 逻辑谬误检查
    4. 利益链检查
    5. 可证伪锚点
    """
    
    FALLACY_PATTERNS = {
        "survivorship_bias": {
            "name": "幸存者偏差",
            "indicators": ["成功案例", "幸存者", "存活率", "回报率"],
            "description": "只关注存活的样本，忽视被淘汰的样本",
            "suggestion": "补充失败/淘汰样本的统计数据"
        },
        "confirmation_bias": {
            "name": "确认偏误",
            "indicators": ["证实", "支持假设", "符合预期"],
            "description": "只搜索证实方向的信息，忽视反证",
            "suggestion": "执行反向检索，纳入反证证据"
        },
        "post_hoc": {
            "name": "后此谬误",
            "indicators": ["之后发生", "因此导致", "时间先后"],
            "description": "因为B在A之后发生，所以认为A导致B",
            "suggestion": "区分时间先后与因果关系，检查是否有混杂因素"
        },
        "availability_bias": {
            "name": "可得性偏差",
            "indicators": ["最近发生", "引人注目", "广泛报道"],
            "description": "因为容易想到就认为发生概率高",
            "suggestion": "参考基率数据，不要仅凭印象判断"
        },
        "base_rate_neglect": {
            "name": "基本比率忽视",
            "indicators": ["忽视基率", "个案推断"],
            "description": "忽视事件的基本比率，仅凭个案推断概率",
            "suggestion": "补充基率数据作为先验参考"
        },
        "circular_reasoning": {
            "name": "循环论证",
            "indicators": ["因为所以", "自证"],
            "description": "结论被用作前提来证明自己",
            "suggestion": "确保前提和结论来自独立的信息源"
        }
    }
    
    def generate(
        self,
        task_id: str,
        claims: List[Claim],
        evidence_list: List[Evidence],
        analysis_results: Dict[str, Any],
        commitment_level: CommitmentLevel
    ) -> GeneratedReport:
        """生成完整报告"""
        sections = []
        
        # 1. 结论先行（最高优先级）
        conclusion = self._build_conclusion_section(claims, commitment_level)
        sections.append(conclusion)
        
        # 2. 声明前置
        declaration = self._build_declaration_section(claims, evidence_list, commitment_level)
        sections.append(declaration)
        
        # 3. 证据摘要
        evidence_section = self._build_evidence_section(evidence_list)
        sections.append(evidence_section)
        
        # 4. 方法论
        methodology = self._build_methodology_section(analysis_results)
        sections.append(methodology)
        
        # 5. 证伪锚点
        falsification = self._build_falsification_section(claims)
        sections.append(falsification)
        
        # 6. 局限性
        limitations = self._build_limitations_section(claims, evidence_list, commitment_level)
        sections.append(limitations)
        
        # 7. 逻辑谬误检查
        fallacy_checks = self._check_fallacies(claims, evidence_list)
        
        # 8. 利益链检查
        interest_check = self._check_interest_chain(evidence_list)
        
        return GeneratedReport(
            report_id=str(uuid.uuid4()),
            task_id=task_id,
            sections=sections,
            fallacy_checks=fallacy_checks,
            interest_chain_check=interest_check,
            commitment_level=commitment_level
        )
    
    def _build_conclusion_section(
        self,
        claims: List[Claim],
        commitment_level: CommitmentLevel
    ) -> ReportSection:
        """结论先行"""
        lines = []
        for claim in claims:
            level_tag = f"[{commitment_level.value}级]"
            lines.append(f"{level_tag} {claim.content}")
            if claim.falsifiable_anchor:
                lines.append(f"  证伪锚点: {claim.falsifiable_anchor}")
            if claim.verification_suggestion:
                lines.append(f"  验证建议: {claim.verification_suggestion}")
        
        return ReportSection(
            section_type="conclusion",
            title="结论",
            content="\n".join(lines),
            priority=1
        )
    
    def _build_declaration_section(
        self,
        claims: List[Claim],
        evidence_list: List[Evidence],
        commitment_level: CommitmentLevel
    ) -> ReportSection:
        """
        声明前置：层级+样本量是结论的一部分不是免责尾巴
        """
        lines = []
        lines.append(f"承诺等级: {commitment_level.value}")
        
        # 样本量
        sample_sizes = [c.sample_size for c in claims if c.sample_size is not None]
        if sample_sizes:
            lines.append(f"样本量: {sample_sizes}")
        
        # 数据层级分布
        quality_counts = {}
        for e in evidence_list:
            q = e.source_quality.value
            quality_counts[q] = quality_counts.get(q, 0) + 1
        lines.append(f"数据层级分布: {quality_counts}")
        
        # 独立来源数
        domains = set()
        for e in evidence_list:
            try:
                from urllib.parse import urlparse
                domain = urlparse(e.source_url).netloc
                domains.add(domain)
            except Exception:
                pass
        lines.append(f"独立来源数: {len(domains)}")
        
        return ReportSection(
            section_type="declaration",
            title="声明（结论的一部分）",
            content="\n".join(lines),
            priority=2
        )
    
    def _build_evidence_section(self, evidence_list: List[Evidence]) -> ReportSection:
        """证据摘要"""
        lines = []
        for i, e in enumerate(evidence_list[:10], 1):
            quality_tag = f"[{e.source_quality.value}]"
            url_short = e.source_url[:60]
            lines.append(f"{i}. {quality_tag} {url_short}")
        
        if len(evidence_list) > 10:
            lines.append(f"... 共{len(evidence_list)}条证据")
        
        return ReportSection(
            section_type="evidence",
            title="证据摘要",
            content="\n".join(lines),
            priority=3
        )
    
    def _build_methodology_section(self, results: Dict[str, Any]) -> ReportSection:
        """方法论"""
        lines = []
        for key, value in results.items():
            if isinstance(value, dict):
                lines.append(f"**{key}**")
                for k, v in value.items():
                    lines.append(f"  {k}: {v}")
            else:
                lines.append(f"{key}: {value}")
        
        return ReportSection(
            section_type="methodology",
            title="方法论",
            content="\n".join(lines) if lines else "方法信息待补充",
            priority=4
        )
    
    def _build_falsification_section(self, claims: List[Claim]) -> ReportSection:
        """可证伪锚点"""
        lines = []
        for claim in claims:
            if claim.falsifiable_anchor:
                lines.append(f"- 主张: {claim.content[:80]}...")
                lines.append(f"  证伪锚点: {claim.falsifiable_anchor}")
                lines.append(f"  验证建议: {claim.verification_suggestion or '待补充'}")
            else:
                lines.append(f"- 主张: {claim.content[:80]}... [⚠ 缺少证伪锚点]")
        
        return ReportSection(
            section_type="falsification",
            title="证伪锚点与验证建议",
            content="\n".join(lines),
            priority=5
        )
    
    def _build_limitations_section(
        self,
        claims: List[Claim],
        evidence_list: List[Evidence],
        commitment_level: CommitmentLevel
    ) -> ReportSection:
        """局限性"""
        lines = []
        
        if commitment_level == CommitmentLevel.C:
            lines.append("- 当前承诺等级为C（方向判断），不适用于精确预测")
        
        # 孤证检查
        if len(evidence_list) == 1:
            lines.append("- 仅有1条证据，为孤证，结论置信度封顶50%")
        
        # C级来源占比
        c_count = sum(1 for e in evidence_list if e.source_quality == EvidenceQuality.C)
        if c_count > len(evidence_list) * 0.5 and evidence_list:
            lines.append(f"- C级来源占比过高（{c_count}/{len(evidence_list)}），建议补充权威来源")
        
        # 矛盾证据
        contradictory = sum(1 for e in evidence_list if e.is_contradictory)
        if contradictory > 0:
            lines.append(f"- 存在{contradictory}条反证证据，冲突未完全消解")
        
        if not lines:
            lines.append("- 未发现明显局限性")
        
        return ReportSection(
            section_type="limitations",
            title="局限性与适用条件",
            content="\n".join(lines),
            priority=6
        )
    
    def _check_fallacies(
        self,
        claims: List[Claim],
        evidence_list: List[Evidence]
    ) -> List[FallacyCheck]:
        """
        逻辑谬误检查
        
        清单：幸存者偏差/确认偏误/后此谬误/可得性偏差/基本比率忽视/循环论证
        """
        all_text = " ".join(c.content for c in claims)
        all_text += " " + " ".join(e.raw_content[:200] for e in evidence_list)
        
        checks = []
        for fallacy_key, pattern in self.FALLACY_PATTERNS.items():
            detected = any(ind in all_text for ind in pattern["indicators"])
            checks.append(FallacyCheck(
                fallacy_type=fallacy_key,
                detected=detected,
                description=pattern["description"],
                suggestion=pattern["suggestion"] if detected else "未检测到"
            ))
        
        return checks
    
    def _check_interest_chain(self, evidence_list: List[Evidence]) -> InterestChainCheck:
        """
        利益链检查
        
        规则：
        - 谁受益/谁受损
        - 数据生产者立场
        - 行业方材料不得作唯一定量依据
        """
        # 简化实现：检查来源类型
        industry_sources = [
            e for e in evidence_list
            if "industry" in e.raw_content.lower() or "行业" in e.raw_content
        ]
        
        is_sole_basis = len(industry_sources) == len(evidence_list) and len(evidence_list) > 0
        
        check = InterestChainCheck(
            beneficiaries=["待分析"],
            losers=["待分析"],
            data_producer_stance="待声明",
            industry_material_is_sole_basis=is_sole_basis,
            warning="行业方材料作为唯一定量依据，结论可能有偏" if is_sole_basis else ""
        )
        
        return check
