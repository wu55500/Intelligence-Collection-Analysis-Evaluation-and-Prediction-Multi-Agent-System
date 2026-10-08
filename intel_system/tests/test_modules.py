"""
功能模块测试
"""

import pytest
from datetime import datetime
from src.modules.m1_collection.collector import MultiSourceCollector
from src.modules.m2_governance.governor import DataGovernor
from src.modules.m3_eda.analyzer import EDAAnalyzer
from src.modules.m5_causal.reviewer import CausalReviewer
from src.modules.m12_evidence.chain import EvidenceChain
from src.modules.m13_report.reporter import ReportGenerator
from src.core.schemas import Evidence, EvidenceQuality, Claim, CommitmentLevel


@pytest.mark.asyncio
async def test_multi_source_collector():
    """测试多源采集器"""
    collector = MultiSourceCollector()
    
    evidence_list = await collector.collect(
        query="测试查询",
        task_id="task-001",
        include_reverse=True,
        max_sources=5
    )
    
    # 应该返回证据列表
    assert isinstance(evidence_list, list)
    # 每条证据应该有必要的字段
    for ev in evidence_list:
        assert ev.evidence_id is not None
        assert ev.source_url is not None
        assert ev.source_quality in [EvidenceQuality.S, EvidenceQuality.A, EvidenceQuality.B, EvidenceQuality.C]
    
    await collector.close()


def test_data_governor():
    """测试数据治理器"""
    governor = DataGovernor()
    
    # 创建测试证据
    evidence_list = [
        Evidence(
            evidence_id="ev-1",
            source_url="https://gov.cn/article1",
            source_quality=EvidenceQuality.S,
            content_hash="hash1",
            raw_content="政府公告内容",
            extracted_at=datetime.now(),
            credibility_score=0.9,
            relevance_score=0.8,
            diagnostic_score=0.7,
            task_id="task-001"
        ),
        Evidence(
            evidence_id="ev-2",
            source_url="https://gov.cn/article2",  # 同源
            source_quality=EvidenceQuality.S,
            content_hash="hash1",  # 重复内容
            raw_content="政府公告内容",
            extracted_at=datetime.now(),
            credibility_score=0.9,
            relevance_score=0.8,
            diagnostic_score=0.7,
            task_id="task-001"
        )
    ]
    
    result = governor.govern(evidence_list)
    
    # 应该去重
    assert result.removed_count >= 1
    assert result.final_count < result.original_count


def test_eda_analyzer():
    """测试EDA分析器"""
    analyzer = EDAAnalyzer()
    
    # 测试数据
    data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    
    result = analyzer.analyze(data)
    
    assert result.statistical_summary.count == 10
    assert result.statistical_summary.mean == 5.5
    assert result.outlier_detection.outlier_ratio < 0.2  # 正常数据异常值比例低


def test_eda_correlation():
    """测试相关性分析"""
    analyzer = EDAAnalyzer()
    
    # 强相关数据
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [2.0, 4.0, 6.0, 8.0, 10.0]
    
    result = analyzer.analyze(x, second_data=y)
    
    assert result.correlation_result is not None
    assert abs(result.correlation_result.pearson_r) > 0.9  # 强相关


def test_causal_reviewer_granger():
    """测试因果审查器（格兰杰）"""
    reviewer = CausalReviewer()
    
    result = reviewer.review(
        claim="X导致Y",
        proposed_method="granger",
        data_characteristics={
            "is_time_series": True,
            "time_points": 100,
            "is_stationary": True
        }
    )
    
    # 格兰杰不能声称"导致"，只能声称"预测性关联"
    assert result.can_claim_causality is True
    assert result.allowed_statement == "预测性关联"
    assert any("格兰杰" in w for w in result.warnings)


def test_evidence_chain_triangular_verification():
    """测试三角验证"""
    chain = EvidenceChain()
    
    # 创建3个独立来源
    evidence_list = [
        Evidence(
            evidence_id=f"ev-{i}",
            source_url=f"https://site{i}.com",
            source_quality=EvidenceQuality.A,
            content_hash=f"hash{i}",
            raw_content=f"独立内容{i}",
            extracted_at=datetime.now(),
            credibility_score=0.8,
            relevance_score=0.7,
            diagnostic_score=0.6,
            task_id="task-001"
        )
        for i in range(3)
    ]
    
    result = chain.evaluate_chain(evidence_list, "测试结论")
    
    # 3个独立源应该是强验证
    assert result.triangulation.verification_level == "强验证"
    assert result.triangulation.independent_source_count == 3


def test_evidence_chain_single_source():
    """测试孤证情况"""
    chain = EvidenceChain()
    
    # 只有1个来源
    evidence_list = [
        Evidence(
            evidence_id="ev-1",
            source_url="https://site1.com",
            source_quality=EvidenceQuality.B,
            content_hash="hash1",
            raw_content="单一内容",
            extracted_at=datetime.now(),
            credibility_score=0.7,
            relevance_score=0.6,
            diagnostic_score=0.5,
            task_id="task-001"
        )
    ]
    
    result = chain.evaluate_chain(evidence_list, "测试结论")
    
    # 孤证应该是弱验证
    assert result.triangulation.verification_level == "孤证限用"
    assert result.overall_strength == "孤证"


def test_report_generator():
    """测试报告生成器"""
    generator = ReportGenerator()
    
    claims = [
        Claim(
            claim_id="claim-1",
            claim_type="inference",
            content="测试结论",
            commitment_level=CommitmentLevel.B,
            evidence_ids=["ev-1", "ev-2"],
            created_at=datetime.now(),
            falsifiable_anchor="如果X则证伪",
            verification_suggestion="检查Y",
            sample_size=50,
            task_id="task-001"
        )
    ]
    
    evidence_list = [
        Evidence(
            evidence_id="ev-1",
            source_url="https://example.com",
            source_quality=EvidenceQuality.A,
            content_hash="hash1",
            raw_content="证据内容",
            extracted_at=datetime.now(),
            credibility_score=0.8,
            relevance_score=0.7,
            diagnostic_score=0.6,
            task_id="task-001"
        )
    ]
    
    report = generator.generate(
        task_id="task-001",
        claims=claims,
        evidence_list=evidence_list,
        analysis_results={"method": "test", "result": "success"},
        commitment_level=CommitmentLevel.B
    )
    
    # 报告应该有多个段落
    assert len(report.sections) >= 5
    
    # 结论应该在前
    assert report.sections[0].section_type == "conclusion"
    
    # 声明应该在前面
    assert report.sections[1].section_type == "declaration"
    
    # 应该有逻辑谬误检查
    assert len(report.fallacy_checks) > 0
