"""
M12 证据链治理模块

P0需求：
- 3.1 信息源分级：S/A/B/C/D域名白名单驱动
- 3.2 三维快判：质量(CRAAP)×相关(贴题)×诊断(区分竞争假设能力)
- 3.3 三角验证：核心结论≥3独立源；2源=弱验证；1源=孤证限用
- 3.4 矛盾点管理：冲突显式编号标注，不可消解则降置信度
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import uuid

from ...core.schemas import Evidence, EvidenceQuality


@dataclass
class EvidenceEvaluation:
    """单条证据的三维评估"""
    evidence_id: str
    craap_score: float  # 质量分 (CRAAP: Currency/Relevance/Authority/Accuracy/Purpose)
    relevance_score: float  # 相关度
    diagnostic_score: float  # 诊断度（区分竞争假设的能力）
    combined_score: float  # 三轴独立打分，禁止一个0.8混切
    quality_grade: EvidenceQuality
    is_independent_source: bool
    notes: str = ""


@dataclass
class TriangulationResult:
    """三角验证结果"""
    conclusion: str
    independent_source_count: int
    verification_level: str  # "强验证", "弱验证", "孤证限用"
    supporting_evidence: List[str]
    contradicting_evidence: List[str]
    max_confidence: float
    notes: str = ""


@dataclass
class ConflictRecord:
    """矛盾点记录"""
    conflict_id: str
    description: str
    supporting_side: List[str]
    contradicting_side: List[str]
    is_resolvable: bool
    resolution_note: str = ""
    confidence_impact: str = ""


@dataclass
class EvidenceChainResult:
    """证据链完整结果"""
    evaluations: List[EvidenceEvaluation]
    triangulation: TriangulationResult
    conflicts: List[ConflictRecord]
    overall_strength: str  # "强", "中", "弱", "孤证"
    max_commitment_level: str
    recommendations: List[str]
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class EvidenceChain:
    """
    证据链治理器
    
    职责：
    1. 三维快判（质量×相关×诊断）
    2. 三角验证
    3. 矛盾点管理
    """
    
    def evaluate_chain(
        self,
        evidence_list: List[Evidence],
        conclusion: str
    ) -> EvidenceChainResult:
        """评估完整证据链"""
        
        # 1. 三维快判
        evaluations = [self._evaluate_single(e) for e in evidence_list]
        
        # 2. 三角验证
        triangulation = self._triangulate(evaluations, conclusion)
        
        # 3. 矛盾点管理
        conflicts = self._identify_conflicts(evaluations, evidence_list)
        
        # 4. 综合判断
        overall_strength = self._assess_overall_strength(triangulation, conflicts)
        max_commitment = self._determine_max_commitment(overall_strength, conflicts)
        
        # 5. 建议
        recommendations = self._generate_recommendations(triangulation, conflicts, evaluations)
        
        return EvidenceChainResult(
            evaluations=evaluations,
            triangulation=triangulation,
            conflicts=conflicts,
            overall_strength=overall_strength,
            max_commitment_level=max_commitment,
            recommendations=recommendations
        )
    
    def _evaluate_single(self, evidence: Evidence) -> EvidenceEvaluation:
        """单条证据的三维评估"""
        # CRAAP质量评分
        craap = self._calculate_craap(evidence)
        
        # 相关度
        relevance = evidence.relevance_score
        
        # 诊断度
        diagnostic = evidence.diagnostic_score
        
        # 综合分 = 三轴独立打分（禁止一个0.8混切）
        combined = (craap + relevance + diagnostic) / 3.0
        
        return EvidenceEvaluation(
            evidence_id=evidence.evidence_id,
            craap_score=craap,
            relevance_score=relevance,
            diagnostic_score=diagnostic,
            combined_score=combined,
            quality_grade=evidence.source_quality,
            is_independent_source=True  # 后续通过域名聚类判断
        )
    
    def _calculate_craap(self, evidence: Evidence) -> float:
        """
        CRAAP评分：Currency/Relevance/Authority/Accuracy/Purpose
        
        简化实现，实际应该由LLM详细评估
        """
        quality_scores = {
            EvidenceQuality.S: 0.95,
            EvidenceQuality.A: 0.80,
            EvidenceQuality.B: 0.65,
            EvidenceQuality.C: 0.40,
            EvidenceQuality.D: 0.0
        }
        return quality_scores.get(evidence.source_quality, 0.5)
    
    def _triangulate(
        self,
        evaluations: List[EvidenceEvaluation],
        conclusion: str
    ) -> TriangulationResult:
        """
        三角验证
        
        规则：
        - ≥3独立源 = 强验证
        - 2源 = 弱验证
        - 1源 = 孤证限用
        """
        independent_count = sum(1 for e in evaluations if e.is_independent_source)
        
        supporting = [
            e.evidence_id for e in evaluations
            if e.combined_score > 0.5 and e.is_independent_source
        ]
        
        contradicting = [
            e.evidence_id for e in evaluations
            if e.combined_score < 0.3
        ]
        
        if independent_count >= 3:
            level = "强验证"
            max_confidence = 0.9
        elif independent_count == 2:
            level = "弱验证"
            max_confidence = 0.65
        elif independent_count == 1:
            level = "孤证限用"
            max_confidence = 0.5
        else:
            level = "无证据"
            max_confidence = 0.0
        
        return TriangulationResult(
            conclusion=conclusion,
            independent_source_count=independent_count,
            verification_level=level,
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            max_confidence=max_confidence
        )
    
    def _identify_conflicts(
        self,
        evaluations: List[EvidenceEvaluation],
        evidence_list: List[Evidence]
    ) -> List[ConflictRecord]:
        """
        识别矛盾点
        
        规则：冲突显式编号标注，不可消解则降置信度
        """
        conflicts = []
        
        # 检查是否有互相矛盾的证据
        contradictory = [e for e in evidence_list if e.is_contradictory]
        supporting = [e for e in evidence_list if not e.is_contradictory]
        
        if contradictory and supporting:
            conflicts.append(ConflictRecord(
                conflict_id=str(uuid.uuid4()),
                description="存在反证证据与正证证据冲突",
                supporting_side=[e.evidence_id for e in supporting],
                contradicting_side=[e.evidence_id for e in contradictory],
                is_resolvable=False,
                confidence_impact="置信度需降低至少一档"
            ))
        
        # 检查质量等级冲突
        high_quality = [e for e in evaluations if e.quality_grade in (EvidenceQuality.S, EvidenceQuality.A)]
        low_quality = [e for e in evaluations if e.quality_grade in (EvidenceQuality.C, EvidenceQuality.D)]
        
        if high_quality and low_quality:
            # 不同质量等级的证据指向不同方向
            conflicts.append(ConflictRecord(
                conflict_id=str(uuid.uuid4()),
                description="高质量来源与低质量来源结论不一致",
                supporting_side=[e.evidence_id for e in high_quality],
                contradicting_side=[e.evidence_id for e in low_quality],
                is_resolvable=False,
                confidence_impact="应以高质量来源为准，但需记录冲突"
            ))
        
        return conflicts
    
    def _assess_overall_strength(
        self,
        triangulation: TriangulationResult,
        conflicts: List[ConflictRecord]
    ) -> str:
        """综合评估证据链强度"""
        if triangulation.verification_level == "强验证" and not conflicts:
            return "强"
        elif triangulation.verification_level in ("强验证", "弱验证") and len(conflicts) <= 1:
            return "中"
        elif triangulation.verification_level == "孤证限用":
            return "孤证"
        else:
            return "弱"
    
    def _determine_max_commitment(
        self,
        strength: str,
        conflicts: List[ConflictRecord]
    ) -> str:
        """确定最高承诺等级"""
        if strength == "强" and not conflicts:
            return "A"
        elif strength in ("强", "中"):
            return "B"
        elif strength == "弱":
            return "C"
        else:  # 孤证
            return "C"  # 孤证封顶
    
    def _generate_recommendations(
        self,
        triangulation: TriangulationResult,
        conflicts: List[ConflictRecord],
        evaluations: List[EvidenceEvaluation]
    ) -> List[str]:
        """生成建议"""
        recommendations = []
        
        if triangulation.independent_source_count < 3:
            recommendations.append(
                f"独立来源数({triangulation.independent_source_count})不足3个，建议补充更多独立来源"
            )
        
        if conflicts:
            for conflict in conflicts:
                if not conflict.is_resolvable:
                    recommendations.append(f"冲突[{conflict.conflict_id[:8]}]: {conflict.confidence_impact}")
        
        low_score = [e for e in evaluations if e.combined_score < 0.4]
        if low_score:
            recommendations.append(
                f"{len(low_score)}条证据综合评分低于0.4，建议复核或降级使用"
            )
        
        return recommendations
