"""
M2 数据治理模块

P0需求：
- 2.1 清洗去重：剔广告/重复/公关稿；同源转载=单源；口径不一致保留差异
- 2.2 异常值净化：IQR法，剔除前列表留痕
- 2.3 口径检查：限上≠大企业、期货≠现货、名义≠实际、初值≠终值
- 2.5 分层标注：每条数据标S/B/C层级，决定结论声明模板
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import uuid

from ...core.schemas import Evidence, EvidenceQuality


@dataclass
class CleanAction:
    """清洗动作记录（必须留痕）"""
    action_id: str
    action_type: str  # "remove_duplicate", "remove_ad", "remove_pr", "outlier_iqr"
    source_evidence_id: Optional[str]
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ScaleCheck:
    """口径检查结果"""
    field_name: str
    detected_scale: str  # "名义", "实际", "初值", "终值", "期货", "现货"等
    warning: str
    resolved: bool = False


@dataclass
class GovernanceResult:
    """数据治理结果"""
    original_count: int
    final_count: int
    removed_count: int
    clean_actions: List[CleanAction]
    scale_checks: List[ScaleCheck]
    quality_distribution: Dict[str, int]  # {"S": 5, "A": 10, "B": 3, "C": 2}
    data_quality_report: Dict[str, Any]
    governed_evidence: List[Evidence]


class DataGovernor:
    """
    数据治理器
    
    职责：
    1. 清洗去重
    2. 异常值净化（IQR法）
    3. 口径检查
    4. 分层标注
    """
    
    def __init__(self):
        self.clean_actions: List[CleanAction] = []
    
    def govern(self, evidence_list: List[Evidence]) -> GovernanceResult:
        """执行完整的数据治理流程"""
        original_count = len(evidence_list)
        
        # 第1步：清洗去重
        cleaned, step1_actions = self._clean_deduplicate(evidence_list)
        self.clean_actions.extend(step1_actions)
        
        # 第2步：剔除广告/公关稿
        filtered, step2_actions = self._filter_noise(cleaned)
        self.clean_actions.extend(step2_actions)
        
        # 第3步：口径检查
        scale_checks = self._check_scales(filtered)
        
        # 第4步：分层标注统计
        quality_dist = self._calculate_quality_distribution(filtered)
        
        # 生成数据质量报告
        data_quality_report = self._generate_quality_report(
            filtered, scale_checks, quality_dist
        )
        
        return GovernanceResult(
            original_count=original_count,
            final_count=len(filtered),
            removed_count=original_count - len(filtered),
            clean_actions=self.clean_actions,
            scale_checks=scale_checks,
            quality_distribution=quality_dist,
            data_quality_report=data_quality_report,
            governed_evidence=filtered
        )
    
    def _clean_deduplicate(
        self,
        evidence_list: List[Evidence]
    ) -> Tuple[List[Evidence], List[CleanAction]]:
        """
        清洗去重
        
        规则：
        - 同源转载=单源（按域名聚类）
        - 口径不一致保留差异
        - 内容哈希完全相同视为重复
        """
        actions = []
        seen_hashes = set()
        seen_domains = {}
        result = []
        
        for evidence in evidence_list:
            # 完全相同内容去重
            if evidence.content_hash in seen_hashes:
                actions.append(CleanAction(
                    action_id=str(uuid.uuid4()),
                    action_type="remove_duplicate",
                    source_evidence_id=evidence.evidence_id,
                    reason=f"内容哈希重复: {evidence.content_hash[:12]}..."
                ))
                continue
            
            # 同源转载检查（同域名只保留质量最高的）
            domain = self._extract_domain(evidence.source_url)
            if domain in seen_domains:
                existing = seen_domains[domain]
                if self._quality_rank(evidence.source_quality) <= self._quality_rank(existing.source_quality):
                    actions.append(CleanAction(
                        action_id=str(uuid.uuid4()),
                        action_type="remove_duplicate",
                        source_evidence_id=evidence.evidence_id,
                        reason=f"同源转载，已有更高质量来源: {domain}"
                    ))
                    continue
            
            seen_hashes.add(evidence.content_hash)
            seen_domains[domain] = evidence
            result.append(evidence)
        
        return result, actions
    
    def _filter_noise(
        self,
        evidence_list: List[Evidence]
    ) -> Tuple[List[Evidence], List[CleanAction]]:
        """
        过滤噪声：广告、公关稿、重复内容
        """
        actions = []
        result = []
        
        noise_keywords = ["广告", "推广", "赞助内容", "PR", "press release"]
        
        for evidence in evidence_list:
            content_lower = evidence.raw_content.lower()
            is_noise = any(kw in content_lower for kw in noise_keywords)
            
            if is_noise:
                actions.append(CleanAction(
                    action_id=str(uuid.uuid4()),
                    action_type="remove_ad",
                    source_evidence_id=evidence.evidence_id,
                    reason="检测到广告/公关稿内容"
                ))
            else:
                result.append(evidence)
        
        return result, actions
    
    def _check_scales(self, evidence_list: List[Evidence]) -> List[ScaleCheck]:
        """
        口径检查
        
        规则：限上≠大企业、期货≠现货、名义≠实际、初值≠终值
        """
        checks = []
        scale_indicators = {
            "名义": ["名义", "nominal", "未扣除价格因素"],
            "实际": ["实际", "real", "扣除价格因素", "可比价"],
            "初值": ["初值", "preliminary", "初步核算"],
            "终值": ["终值", "final", "最终核实"],
            "期货": ["期货", "futures", "远期"],
            "现货": ["现货", "spot", "即期"],
            "限上": ["限上", "规模以上", "above-scale"],
        }
        
        for evidence in evidence_list:
            content = evidence.raw_content
            detected_scales = []
            
            for scale_name, indicators in scale_indicators.items():
                if any(ind in content for ind in indicators):
                    detected_scales.append(scale_name)
            
            # 检查冲突
            if "名义" in detected_scales and "实际" in detected_scales:
                checks.append(ScaleCheck(
                    field_name=f"evidence:{evidence.evidence_id[:8]}",
                    detected_scale="名义+实际冲突",
                    warning="同一条证据同时出现名义和实际口径，需要区分"
                ))
            
            if "初值" in detected_scales and "终值" in detected_scales:
                checks.append(ScaleCheck(
                    field_name=f"evidence:{evidence.evidence_id[:8]}",
                    detected_scale="初值+终值冲突",
                    warning="同一条证据同时出现初值和终值口径，需要区分"
                ))
            
            if "期货" in detected_scales and "现货" in detected_scales:
                checks.append(ScaleCheck(
                    field_name=f"evidence:{evidence.evidence_id[:8]}",
                    detected_scale="期货+现货冲突",
                    warning="同一条证据同时出现期货和现货口径，需要区分"
                ))
        
        return checks
    
    def _calculate_quality_distribution(
        self,
        evidence_list: List[Evidence]
    ) -> Dict[str, int]:
        """统计各质量等级分布"""
        dist = {"S": 0, "A": 0, "B": 0, "C": 0, "D": 0}
        for e in evidence_list:
            dist[e.source_quality.value] += 1
        return dist
    
    def _generate_quality_report(
        self,
        evidence_list: List[Evidence],
        scale_checks: List[ScaleCheck],
        quality_dist: Dict[str, int]
    ) -> Dict[str, Any]:
        """生成数据质量报告"""
        total = len(evidence_list)
        
        return {
            "total_evidence": total,
            "quality_distribution": quality_dist,
            "quality_score": self._calculate_overall_quality(quality_dist, total),
            "scale_conflicts": len(scale_checks),
            "has_s_level": quality_dist.get("S", 0) > 0,
            "dominant_quality": max(quality_dist, key=quality_dist.get) if total > 0 else "N/A",
            "recommendation": self._generate_recommendation(quality_dist, scale_checks)
        }
    
    def _calculate_overall_quality(
        self,
        quality_dist: Dict[str, int],
        total: int
    ) -> float:
        """计算整体质量分数"""
        if total == 0:
            return 0.0
        
        weights = {"S": 1.0, "A": 0.8, "B": 0.6, "C": 0.4, "D": 0.0}
        score = sum(
            quality_dist.get(level, 0) * weight
            for level, weight in weights.items()
        )
        return score / total
    
    def _generate_recommendation(
        self,
        quality_dist: Dict[str, int],
        scale_checks: List[ScaleCheck]
    ) -> str:
        """生成数据治理建议"""
        total = sum(quality_dist.values())
        if total == 0:
            return "无数据"
        
        s_ratio = quality_dist.get("S", 0) / total
        c_ratio = quality_dist.get("C", 0) / total
        
        if s_ratio >= 0.3:
            base = "数据质量良好，S级来源占比充足"
        elif c_ratio > 0.5:
            base = "数据质量偏低，C级来源占比过高，建议补充一手源"
        else:
            base = "数据质量中等"
        
        if scale_checks:
            base += f"；发现{len(scale_checks)}个口径冲突，需人工确认"
        
        return base
    
    @staticmethod
    def _extract_domain(url: str) -> str:
        """提取域名"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except Exception:
            return url
    
    @staticmethod
    def _quality_rank(quality: EvidenceQuality) -> int:
        """质量等级排名（越小越好）"""
        ranks = {
            EvidenceQuality.S: 1,
            EvidenceQuality.A: 2,
            EvidenceQuality.B: 3,
            EvidenceQuality.C: 4,
            EvidenceQuality.D: 5
        }
        return ranks.get(quality, 5)
