"""
V2 集成测试
测试四层架构 + 验收闸门 + 红队 + 检查点 + 智能路由
"""

import pytest
import asyncio
from datetime import datetime

from src.core.validation_gate import ValidationGate, ModuleOutput, ModuleStatus
from src.services.red_team import IndependentVerifier, VerificationResult
from src.services.checkpoint import CheckpointService, Checkpoint
from src.agents.router import SmartRouter, TaskType, ModelRegistry
from src.agents.router.llm_client import UnifiedLLMClient
from src.infra.cache import RedisClient, QueryCache
from src.infra.vector import EmbeddingService, VectorStore, RAGRetriever
from src.infra.memory import MemoryManager
from src.infra.reflection import ReflectionEngine
from src.modules.m10_alert import AlertEngine, AlertRule, AlertSeverity
from src.modules.m14_permission import PermissionGovernor, PermissionLevel
from src.modules.m15_metrics import MetricsCollector, SystemHealthMonitor
from src.modules.m20_model_health import ModelHealthMonitor
from src.modules.m21_commitment import CommitmentEngine, CommitmentInput, CommitmentLevel


# ========== 验收闸门 ==========

class TestValidationGate:
    def test_success_passes(self):
        gate = ValidationGate()
        output = ModuleOutput(
            module_name="m1_collection", status=ModuleStatus.SUCCESS,
            output_data={"count": 10}, evidence_refs=["ev1", "ev2"]
        )
        result = gate.validate(output)
        assert result.passed
        assert not gate.should_block(result)

    def test_critical_failure_blocks(self):
        gate = ValidationGate()
        output = ModuleOutput(
            module_name="m1_collection", status=ModuleStatus.FAILED,
            errors=["timeout"]
        )
        result = gate.validate(output)
        assert not result.passed
        assert gate.should_block(result)

    def test_non_critical_failure_no_block(self):
        gate = ValidationGate()
        output = ModuleOutput(
            module_name="m3_eda", status=ModuleStatus.FAILED,
            errors=["insufficient data"]
        )
        result = gate.validate(output)
        assert not result.passed
        assert not gate.should_block(result)

    def test_collection_no_evidence_blocks(self):
        gate = ValidationGate()
        output = ModuleOutput(
            module_name="m1_collection", status=ModuleStatus.SUCCESS,
            output_data={"count": 0}
        )
        result = gate.validate(output)
        assert not result.passed  # 采集模块无证据引用 → 不通过


# ========== 红队 ==========

class TestRedTeam:
    @pytest.mark.asyncio
    async def test_verified_with_good_evidence(self):
        verifier = IndependentVerifier()
        evidence = [
            {"source_url": f"https://domain{i}.com/a", "is_contradictory": (i == 3)}
            for i in range(5)
        ]
        report = await verifier.verify(
            task_id="t1", claim="测试结论", commitment_level="C",
            evidence_list=evidence,
            methodology={"method": "correlation", "falsifiable_anchor": "如果X不发生"}
        )
        assert not report.should_block
        assert len(report.findings) >= 3

    @pytest.mark.asyncio
    async def test_no_falsifiable_anchor_weakened(self):
        verifier = IndependentVerifier()
        report = await verifier.verify(
            task_id="t2", claim="无锚点结论", commitment_level="A",
            evidence_list=[{"source_url": "https://a.com", "is_contradictory": False}],
            methodology={"method": "correlation"}
        )
        assert report.overall_result.value == "weakened"


# ========== 检查点 ==========

class TestCheckpoint:
    def test_save_and_retrieve(self):
        svc = CheckpointService(db_path="data/test_v2.db")
        cp = Checkpoint(task_id="t1", step_name="collect")
        cp_id = svc.save_checkpoint(cp)
        assert svc.get_checkpoint(cp_id) is not None

    def test_mark_completed(self):
        svc = CheckpointService(db_path="data/test_v2.db")
        cp = Checkpoint(task_id="t2", step_name="govern")
        cp_id = svc.save_checkpoint(cp)
        svc.mark_completed(cp_id, {"cleaned": 5})
        assert svc.get_checkpoint(cp_id).status.value == "completed"

    def test_recovery_info(self):
        svc = CheckpointService(db_path="data/test_v2.db")
        cp = Checkpoint(task_id="t3", step_name="eda")
        svc.save_checkpoint(cp)
        info = svc.get_recovery_info("t3")
        assert info["can_resume"]


# ========== 智能路由 ==========

class TestSmartRouter:
    def test_different_tasks_different_models(self):
        router = SmartRouter()
        decisions = {}
        for task_type in [TaskType.RESEARCH, TaskType.ANALYSIS, TaskType.REPORT, TaskType.SUMMARIZATION]:
            d = router.route(task_type)
            decisions[task_type] = d.selected_model.model_id

        # 至少2个不同模型
        assert len(set(decisions.values())) >= 2

    def test_cost_constraint(self):
        router = SmartRouter()
        d = router.route(TaskType.GENERAL, max_cost=0.001)
        # 应该选便宜的
        assert d.selected_model.cost_per_1k_tokens <= 0.001

    def test_speed_preference(self):
        router = SmartRouter()
        d = router.route(TaskType.GENERAL, prefer_fast=True)
        assert d.selected_model.avg_latency_ms < 3000


# ========== 缓存 ==========

class TestCache:
    def test_memory_fallback(self):
        client = RedisClient()
        assert client.backend == "memory"
        client.set_json("k1", {"v": 1}, ttl=60)
        assert client.get_json("k1") == {"v": 1}
        client.delete("k1")
        assert client.get_json("k1") is None

    def test_rate_limiting(self):
        client = RedisClient()
        for i in range(5):
            val = client.incr("rate:test", ttl=60)
        assert val == 5


# ========== 向量检索 ==========

class TestVector:
    def test_embed_and_search(self):
        emb = EmbeddingService()
        vec = emb.embed_text("测试文本")
        assert len(vec) == 1536

    def test_store_and_retrieve(self):
        store = VectorStore(db_path="data/test_vec.db")
        emb = EmbeddingService()
        texts = ["经济数据分析", "股市预测", "政策变化"]
        embeddings = emb.embed_texts(texts)

        from src.infra.vector import VectorDocument
        for i, (text, vec) in enumerate(zip(texts, embeddings)):
            store.insert(VectorDocument(doc_id=f"doc{i}", text=text, embedding=vec))

        results = store.search(emb.embed_text("经济"), top_k=2)
        assert len(results) >= 1


# ========== 记忆系统 ==========

class TestMemory:
    def test_short_term(self):
        mm = MemoryManager(db_path="data/test_mem_v2.db")
        mm.add_short_term("test", "s1")
        mems = mm.get_short_term("s1")
        assert len(mems) == 1

    def test_long_term(self):
        mm = MemoryManager(db_path="data/test_mem_v2.db")
        mm.add_long_term("长期知识", "fact", tags=["test"])
        found = mm.search_long_term(category="fact")
        assert len(found) >= 1


# ========== 模块 ==========

class TestModules:
    def test_alert_engine(self):
        engine = AlertEngine()
        engine.add_rule(AlertRule(
            rule_id="r1", metric_name="error_rate",
            condition=">", threshold=0.5, severity=AlertSeverity.WARNING
        ))
        asyncio.run(engine.check_metric("error_rate", 0.8))
        active = engine.get_active_alerts()
        assert len(active) == 1

    def test_permission_governor(self):
        gov = PermissionGovernor()
        risk = gov.assess_risk("delete", "删除所有数据")
        assert risk.has_dangerous_keyword
        assert risk.risk_level.value == "critical"

    def test_commitment_engine(self):
        engine = CommitmentEngine()
        decision = engine.evaluate(CommitmentInput(evidence_count=0))
        assert decision.level == CommitmentLevel.BLOCKED

    def test_model_health(self):
        import numpy as np
        monitor = ModelHealthMonitor()
        monitor.set_reference("f1", np.random.randn(100))
        drift = monitor.detect_drift("f1", np.random.randn(100) + 2)
        assert drift.drift_score > 0

    def test_metrics(self):
        m = MetricsCollector()
        m.increment("requests")
        m.increment("requests")
        assert m.get_counter("requests") == 2
        m.set_gauge("cpu", 0.75)
        assert m.get_gauge("cpu") == 0.75

    def test_reflection(self):
        engine = ReflectionEngine()
        result = engine.reflect("analysis", "这是一个足够长的测试文本用于检测反思引擎的工作效果和质量检查", {})
        assert result.confidence_after >= result.confidence_before
