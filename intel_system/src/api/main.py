"""
FastAPI 主应用 - 整合全部四层架构

L1 · 交互与任务编排层 - API入口
L2 · 情报与分析能力层 - 各模块
L3 · 确定性治理层 - 验收闸门、红队、承诺等级
L4 · 数据与基础设施层 - DB、缓存、检索、检查点
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from ..core.schemas import (
    TaskContract, TaskStatus, Evidence, ForecastRecord,
    CommitmentLevel, PermissionLevel
)
from ..core.config import get_settings
from ..core.database import get_database
from ..core.validation_gate import ValidationGate, ModuleOutput
from ..services.commitment_engine import get_commitment_engine, CommitmentInput
from ..services.permission_service import get_permission_service
from ..services.forecast_service import get_forecast_service
from ..services.orchestrator import get_orchestrator
from ..services.red_team import IndependentVerifier
from ..services.checkpoint import CheckpointService
from ..agents.router import SmartRouter, TaskType
from ..agents.router.llm_client import UnifiedLLMClient
from ..infra.websocket import get_ws_manager, WebSocketMessage
from ..infra.vector import RAGRetriever
from ..infra.memory import MemoryManager
from ..modules.m15_metrics import SystemHealthMonitor, MetricsCollector


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    db = get_database()
    print(f"系统启动 | 架构: v2_四层 | 数据库: {settings.database.db_path}")
    yield
    print("系统关闭")


app = FastAPI(
    title="情报收集分析评估预测多Agent系统",
    description="四层架构 · 验收闸门 · 红队验证 · 智能路由 · 持久化检查点",
    version="0.2.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局服务
_ws_manager = get_ws_manager()
_smart_router = SmartRouter()
_llm_client = UnifiedLLMClient()
_rag_retriever = RAGRetriever()
_memory_mgr = MemoryManager()
_red_team = IndependentVerifier()
_checkpoint_svc = CheckpointService()
_health_monitor = SystemHealthMonitor()
_metrics = MetricsCollector()



# 挂载静态文件服务
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_dashboard():
    """提供仪表盘页面"""
    return FileResponse("static/dashboard.html")

# ========== 任务管理 ==========

@app.post("/api/v2/tasks")
async def create_task(task_input: dict, background_tasks: BackgroundTasks):
    """创建任务"""
    db = get_database()
    task = TaskContract(
        task_id=str(uuid.uuid4()),
        task_type=task_input.get("task_type", "research"),
        input_data=task_input.get("input_data", {}),
        input_hash=task_input.get("input_hash", ""),
        method_version="v2.0"
    )
    db.save_task(task)
    return {"task_id": task.task_id, "status": task.status.value}


@app.get("/api/v2/tasks/{task_id}")
async def get_task(task_id: str):
    db = get_database()
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@app.get("/api/v2/tasks/{task_id}/recovery")
async def get_task_recovery(task_id: str):
    """获取任务恢复信息（从检查点恢复）"""
    info = _checkpoint_svc.get_recovery_info(task_id)
    return info


@app.post("/api/v2/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    """恢复中断的任务"""
    try:
        orchestrator = get_orchestrator()
        state = await orchestrator.resume_task(task_id)
        return {"task_id": task_id, "resume_step": state.current_step.value}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v2/tasks/{task_id}/diffs")
async def get_task_diffs(task_id: str):
    """获取步骤重新运行的差异"""
    from ..services.orchestrator_v2 import WorkflowOrchestratorV2
    orch = WorkflowOrchestratorV2()
    return orch.get_step_diffs(task_id)


# ========== 智能路由 ==========

@app.post("/api/v2/routing/recommend")
async def recommend_model(task_input: dict):
    """根据任务类型推荐最佳模型"""
    try:
        task_type = TaskType(task_input.get("task_type", "general"))
        decision = _smart_router.route(
            task_type,
            max_cost=task_input.get("max_cost"),
            max_latency_ms=task_input.get("max_latency_ms"),
            prefer_fast=task_input.get("prefer_fast", False)
        )
        return {
            "task_type": task_type.value,
            "selected_model": {
                "id": decision.selected_model.model_id,
                "name": decision.selected_model.model_name,
                "provider": decision.selected_model.provider
            },
            "alternatives": [
                {"id": m.model_id, "name": m.model_name, "provider": m.provider}
                for m in decision.alternative_models
            ],
            "reason": decision.reason,
            "cost_per_1k": decision.cost_estimate,
            "latency_ms": decision.latency_estimate_ms
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v2/routing/models")
async def list_models(provider: Optional[str] = None):
    """列出所有可用模型"""
    from ..agents.router.model_registry import ModelRegistry
    registry = ModelRegistry()
    models = registry.list_models(provider)
    return [
        {
            "id": m.model_id,
            "name": m.model_name,
            "provider": m.provider,
            "capabilities": {k.value: v for k, v in m.capabilities.items()},
            "max_context": m.max_context_tokens,
            "cost_per_1k": m.cost_per_1k_tokens,
            "supports_tools": m.supports_tools,
            "supports_vision": m.supports_vision,
            "notes": m.notes
        }
        for m in models
    ]


# ========== 红队验证 ==========

@app.post("/api/v2/red-team/verify")
async def red_team_verify(verification_input: dict):
    """独立红队验证"""
    report = await _red_team.verify(
        task_id=verification_input.get("task_id", ""),
        claim=verification_input.get("claim", ""),
        commitment_level=verification_input.get("commitment_level", "C"),
        evidence_list=verification_input.get("evidence_list", []),
        methodology=verification_input.get("methodology", {}),
        forecast=verification_input.get("forecast")
    )
    return {
        "report_id": report.report_id,
        "overall_result": report.overall_result.value,
        "recommended_level": report.recommended_commitment_level,
        "should_block": report.should_block,
        "findings_count": len(report.findings)
    }


# ========== RAG 检索 ==========

@app.post("/api/v2/rag/search")
async def rag_search(search_input: dict):
    """RAG 语义搜索"""
    results = _rag_retriever.retrieve(
        query=search_input.get("query", ""),
        top_k=search_input.get("top_k", 5)
    )
    return {
        "query": search_input.get("query"),
        "results": [
            {"doc_id": r.doc_id, "text": r.text[:200], "score": r.score, "metadata": r.metadata}
            for r in results
        ]
    }


@app.post("/api/v2/rag/add")
async def rag_add_documents(doc_input: dict):
    """添加文档到向量库"""
    ids = _rag_retriever.add_documents(
        texts=doc_input.get("texts", []),
        metadatas=doc_input.get("metadatas")
    )
    return {"added": len(ids), "ids": ids}


# ========== 记忆系统 ==========

@app.post("/api/v2/memory/short-term")
async def add_short_term_memory(mem_input: dict):
    """添加短期记忆"""
    memory = _memory_mgr.add_short_term(
        content=mem_input["content"],
        session_id=mem_input["session_id"],
        importance=mem_input.get("importance", 0.5)
    )
    return {"memory_id": memory.memory_id}


@app.get("/api/v2/memory/short-term/{session_id}")
async def get_short_term_memories(session_id: str, limit: int = 10):
    """获取短期记忆"""
    memories = _memory_mgr.get_short_term(session_id, limit)
    return [
        {"id": m.memory_id, "content": m.content, "importance": m.importance}
        for m in memories
    ]


@app.get("/api/v2/memory/stats")
async def memory_stats():
    """记忆统计"""
    return _memory_mgr.get_memory_stats()



# ========== 预测管理（仪表盘用） ==========

@app.post("/api/v2/forecast/register")
async def register_forecast(forecast_input: dict):
    """登记预测"""
    from datetime import datetime, timedelta
    service = get_forecast_service()
    
    # Parse datetime strings
    start_time = datetime.fromisoformat(forecast_input.get("time_range_start", "").replace("Z", "+00:00"))
    end_time = datetime.fromisoformat(forecast_input.get("time_range_end", "").replace("Z", "+00:00"))
    
    forecast = service.register_forecast(
        task_id=forecast_input.get("task_id", ""),
        event_description=forecast_input.get("event_description", ""),
        probability=forecast_input.get("probability", 0.5),
        time_range_start=start_time,
        time_range_end=end_time,
        falsifiable_anchor=forecast_input.get("falsifiable_anchor", ""),
        premises=forecast_input.get("premises", []),
        evidence_snapshot=forecast_input.get("evidence_snapshot", {})
    )
    
    return {
        "forecast_id": forecast.forecast_id,
        "probability": forecast.probability,
        "falsifiable_anchor": forecast.falsifiable_anchor,
        "registered_at": forecast.registered_at.isoformat()
    }

@app.post("/api/v2/forecast/settle")
async def settle_forecast(settle_input: dict):
    """结算预测"""
    service = get_forecast_service()
    result = service.settle_forecast(
        forecast_id=settle_input.get("forecast_id", ""),
        actual_outcome=settle_input.get("actual_outcome", False)
    )
    return {
        "forecast_id": result.forecast_id,
        "outcome": result.outcome,
        "brier_score": result.brier_score,
        "reason": result.reason,
        "settled_at": result.settled_at.isoformat()
    }

@app.get("/api/v2/forecast/brier")
async def get_brier_score():
    """获取Brier Score"""
    service = get_forecast_service()
    result = service.calculate_brier_score()
    return {
        "score": result.score,
        "count": result.count,
        "calibrated": result.calibrated,
        "vs_baseline": result.vs_baseline
    }

@app.get("/api/v2/forecast/list")
async def list_forecasts():
    """列出所有预测"""
    db = get_database()
    # Get both settled and unsettled
    all_forecasts = db.get_all_forecasts() if hasattr(db, 'get_all_forecasts') else []
    return [
        {
            "forecast_id": f.forecast_id,
            "event_description": f.event_description,
            "probability": f.probability,
            "settled": f.settled,
            "outcome": f.outcome,
            "brier_score": f.brier_score,
            "falsifiable_anchor": f.falsifiable_anchor,
            "registered_at": f.registered_at.isoformat()
        }
        for f in all_forecasts
    ]

# ========== 验收闸门测试（仪表盘用） ==========

@app.post("/api/v2/gate/validate")
async def gate_validate(gate_input: dict):
    """测试验收闸门"""
    from ..core.validation_gate import ValidationGate, ModuleOutput, ModuleStatus
    
    gate = ValidationGate()
    output = ModuleOutput(
        module_name=gate_input.get("module_name", ""),
        status=ModuleStatus(gate_input.get("status", "success")),
        output_data=gate_input.get("output_data", {}),
        evidence_refs=gate_input.get("evidence_refs", []),
        errors=gate_input.get("errors", [])
    )
    
    result = gate.validate(output)
    should_block = gate.should_block(result)
    
    return {
        "passed": result.passed,
        "should_block": should_block,
        "critical_issues": result.critical_issues,
        "warnings": result.warnings
    }

# ========== 系统健康 ==========

@app.get("/api/v2/health")
async def health():
    return _health_monitor.get_health_summary()


@app.get("/api/v2/metrics")
async def metrics():
    return _metrics.get_all_metrics()


# ========== WebSocket ==========

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str, channels: str = "general"):
    await websocket.accept()
    channel_list = channels.split(",")
    await _ws_manager.connect(websocket, client_id, channel_list)
    try:
        while True:
            data = await websocket.receive_text()
            import json
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        await _ws_manager.disconnect(client_id)


# ========== 原有接口兼容 ==========

@app.post("/api/v1/commitment/evaluate")
async def evaluate_commitment(commitment_input: dict):
    engine = get_commitment_engine()
    input_data = CommitmentInput(
        evidence_list=[Evidence(**e) for e in commitment_input.get("evidence_list", [])],
        sample_size=commitment_input.get("sample_size"),
        has_feedback_loop=commitment_input.get("has_feedback_loop", False),
        feedback_count=commitment_input.get("feedback_count", 0),
        has_structural_break=commitment_input.get("has_structural_break", False),
        has_mechanism=commitment_input.get("has_mechanism", False),
        has_falsifiable_anchor=commitment_input.get("has_falsifiable_anchor", False),
        is_contradicted=commitment_input.get("is_contradicted", False),
        is_expired=commitment_input.get("is_expired", False),
        single_source=commitment_input.get("single_source", False),
        data_quality_level=commitment_input.get("data_quality_level"),
        method_name=commitment_input.get("method_name", "")
    )
    decision = engine.evaluate(input_data)
    return {
        "level": decision.level.value,
        "reason": decision.reason,
        "conditions": decision.conditions
    }


@app.get("/api/v1/status")
async def system_status():
    settings = get_settings()
    return {
        "version": "0.2.0",
        "architecture": "v2_four_layer",
        "features": {
            "validation_gate": True,
            "red_team": True,
            "checkpoint": True,
            "smart_routing": True,
            "rag": True,
            "memory": True,
            "websocket": True
        },
        "mobile_mode": settings.mobile_mode,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
