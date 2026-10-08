"""
M1 数据采集模块 - 多源检索实现

P0需求：
- 1.1 多源检索：搜索+垂直站+开放API三通道
- 1.2 反向检索：每轮必带反向词，反证与证实同权重
- 1.3 一手源直读：政府/央行/财报/论文原文页
"""

import asyncio
import hashlib
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urlparse
import uuid

import httpx

from ...core.schemas import Evidence, EvidenceQuality
from ...core.config import get_settings


class MultiSourceCollector:
    """
    多源数据采集器
    
    三通道：
    1. 通用搜索引擎
    2. 垂直网站（政府、央行、财报等）
    3. 开放API（Twitter、Reddit等）
    
    核心规则：
    - 每轮必带反向词（反证与证实同权重）
    - 一手源直读，二手转述降级
    - 摘要不得直接当结论
    """
    
    def __init__(self):
        self.settings = get_settings().collection
        self.domain_whitelist = self._load_domain_whitelist()
        self.http_client = httpx.AsyncClient(timeout=self.settings.timeout_per_source)
    
    async def collect(
        self,
        query: str,
        task_id: str,
        include_reverse: bool = True,
        max_sources: Optional[int] = None
    ) -> List[Evidence]:
        """
        执行多源采集
        
        Args:
            query: 检索词
            task_id: 任务ID
            include_reverse: 是否包含反向检索
            max_sources: 最大来源数
        
        Returns:
            List[Evidence]: 采集到的证据列表
        """
        max_sources = max_sources or self.settings.max_sources_per_query
        
        # 生成反向检索词
        reverse_query = self._generate_reverse_query(query) if include_reverse else None
        
        # 并行执行三通道采集
        tasks = [
            self._collect_from_search(query, task_id),
            self._collect_from_vertical(query, task_id),
            self._collect_from_api(query, task_id)
        ]
        
        if reverse_query:
            tasks.extend([
                self._collect_from_search(reverse_query, task_id, is_reverse=True),
                self._collect_from_vertical(reverse_query, task_id, is_reverse=True),
                self._collect_from_api(reverse_query, task_id, is_reverse=True)
            ])
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 合并结果，过滤异常
        all_evidence = []
        for result in results:
            if isinstance(result, list):
                all_evidence.extend(result)
        
        # 去重（同源转载=单源）
        deduplicated = self._deduplicate_sources(all_evidence)
        
        # 限制数量
        return deduplicated[:max_sources]
    
    async def _collect_from_search(
        self,
        query: str,
        task_id: str,
        is_reverse: bool = False
    ) -> List[Evidence]:
        """从搜索引擎采集"""
        # 简化实现：模拟搜索结果
        # 实际应该调用真实搜索引擎API
        mock_results = [
            {
                "url": "https://example.com/article1",
                "title": "相关报道1",
                "snippet": "这是模拟的搜索结果摘要...",
                "timestamp": datetime.now().isoformat()
            }
        ]
        
        evidence_list = []
        for result in mock_results:
            evidence = await self._process_search_result(result, task_id, is_reverse)
            if evidence:
                evidence_list.append(evidence)
        
        return evidence_list
    
    async def _collect_from_vertical(
        self,
        query: str,
        task_id: str,
        is_reverse: bool = False
    ) -> List[Evidence]:
        """从垂直网站采集（政府、央行、财报等）"""
        # 优先读取一手源
        vertical_sites = [
            "gov.cn",
            "pbc.gov.cn",
            "sec.gov",
            "arxiv.org"
        ]
        
        evidence_list = []
        for site in vertical_sites:
            # 模拟从垂直站采集
            evidence = self._create_mock_vertical_evidence(site, query, task_id, is_reverse)
            evidence_list.append(evidence)
        
        return evidence_list
    
    async def _collect_from_api(
        self,
        query: str,
        task_id: str,
        is_reverse: bool = False
    ) -> List[Evidence]:
        """从开放API采集（Twitter、Reddit等）"""
        # 模拟API采集
        return []
    
    async def _process_search_result(
        self,
        result: Dict[str, Any],
        task_id: str,
        is_reverse: bool
    ) -> Optional[Evidence]:
        """处理搜索结果，生成Evidence"""
        url = result.get("url")
        if not url:
            return None
        
        # 读取原始页面（非摘要）
        try:
            content = await self._fetch_raw_content(url)
        except Exception:
            return None
        
        # 判断证据质量等级
        quality = self._assess_evidence_quality(url)
        
        # 计算内容哈希
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        # 生成Evidence
        evidence = Evidence(
            evidence_id=str(uuid.uuid4()),
            source_url=url,
            source_quality=quality,
            content_hash=content_hash,
            raw_content=content,
            extracted_at=datetime.now(),
            credibility_score=self._calculate_credibility(quality),
            relevance_score=self._calculate_relevance(content),
            diagnostic_score=self._calculate_diagnostic(content),
            is_contradictory=is_reverse,
            task_id=task_id,
            claims=[]
        )
        
        return evidence
    
    async def _fetch_raw_content(self, url: str) -> str:
        """
        读取原始页面内容
        
        关键：二手转述丢弃或降级，必须读取一手源
        """
        try:
            response = await self.http_client.get(url, follow_redirects=True)
            response.raise_for_status()
            return response.text[:10000]  # 限制大小
        except Exception as e:
            raise Exception(f"无法读取原始页面: {url}, 错误: {e}")
    
    def _assess_evidence_quality(self, url: str) -> EvidenceQuality:
        """
        评估证据质量等级
        
        S: 官方一手（政府、央行、上市公司公告）
        A: 权威机构（国际组织、知名智库）
        B: 主流媒体（NYT、Reuters等）
        C: 自媒体待核实
        D: 剔除（广告、重复、公关稿）
        """
        domain = urlparse(url).netloc
        
        # 检查白名单
        if domain in self.domain_whitelist.get("S", []):
            return EvidenceQuality.S
        elif domain in self.domain_whitelist.get("A", []):
            return EvidenceQuality.A
        elif domain in self.domain_whitelist.get("B", []):
            return EvidenceQuality.B
        else:
            # 未知来源，降级为C
            return EvidenceQuality.C
    
    def _calculate_credibility(self, quality: EvidenceQuality) -> float:
        """计算可信度分数"""
        scores = {
            EvidenceQuality.S: 0.95,
            EvidenceQuality.A: 0.85,
            EvidenceQuality.B: 0.70,
            EvidenceQuality.C: 0.50,
            EvidenceQuality.D: 0.0
        }
        return scores.get(quality, 0.5)
    
    def _calculate_relevance(self, content: str) -> float:
        """计算相关度（简化实现）"""
        # 实际应该用更复杂的算法
        return 0.7
    
    def _calculate_diagnostic(self, content: str) -> float:
        """计算诊断度（区分竞争假设的能力）"""
        # 简化实现
        return 0.6
    
    def _generate_reverse_query(self, query: str) -> str:
        """
        生成反向检索词
        
        规则：每轮必带反向词，反证与证实同权重
        """
        reverse_keywords = [
            "反驳", "质疑", "反对", "不支持", "矛盾",
            "dispute", "contradict", "refute", "against"
        ]
        
        # 选择反向关键词
        reverse_term = reverse_keywords[hash(query) % len(reverse_keywords)]
        return f"{query} {reverse_term}"
    
    def _deduplicate_sources(self, evidence_list: List[Evidence]) -> List[Evidence]:
        """
        去重：同源转载=单源
        
        规则：转载不算独立源，多源验证的"源"指不同信息生成者
        """
        seen_domains: Set[str] = set()
        deduplicated = []
        
        for evidence in evidence_list:
            domain = urlparse(evidence.source_url).netloc
            
            if domain not in seen_domains:
                seen_domains.add(domain)
                deduplicated.append(evidence)
            # 否则跳过（同源转载）
        
        return deduplicated
    
    def _load_domain_whitelist(self) -> Dict[str, List[str]]:
        """加载域名白名单"""
        # 简化实现：硬编码白名单
        return {
            "S": [
                "gov.cn",
                "pbc.gov.cn",
                "ndrc.gov.cn",
                "sec.gov",
                "fed.gov"
            ],
            "A": [
                "imf.org",
                "worldbank.org",
                "oecd.org",
                "bis.org"
            ],
            "B": [
                "reuters.com",
                "bloomberg.com",
                "ft.com",
                "nytimes.com"
            ]
        }
    
    def _create_mock_vertical_evidence(
        self,
        site: str,
        query: str,
        task_id: str,
        is_reverse: bool
    ) -> Evidence:
        """创建模拟的垂直站证据"""
        return Evidence(
            evidence_id=str(uuid.uuid4()),
            source_url=f"https://{site}/mock-article",
            source_quality=EvidenceQuality.S if "gov" in site else EvidenceQuality.A,
            content_hash=hashlib.sha256(f"mock-{site}-{query}".encode()).hexdigest(),
            raw_content=f"这是来自{site}的模拟内容...",
            extracted_at=datetime.now(),
            credibility_score=0.9 if "gov" in site else 0.8,
            relevance_score=0.75,
            diagnostic_score=0.65,
            is_contradictory=is_reverse,
            task_id=task_id,
            claims=[]
        )
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.http_client.aclose()
