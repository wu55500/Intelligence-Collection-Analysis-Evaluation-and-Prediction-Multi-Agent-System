"""
FastAPI主应用

四层架构的应用服务层：
- 任务API
- 工作流编排
- 身份与权限
- 任务状态持久化
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime
import uuid

from ..core.schemas import (
    TaskContract, TaskStatus, Evidence, ForecastRecord,
    CommitmentLevel, PermissionLevel
)
from ..core.config import get_settings
from ..core.database import get_database
from ..services.commitment_engine import get_commitment_engine, CommitmentInput
from ..services.permission_service import get_permission_service
from ..services.forecast_service import get_forecast_service
from ..services.orchestrator import get_orchestrator, WorkflowStep


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动时初始化
    settings = get_settings()
    db = get_database()
    print(f"系统启动，数据库路径: {settings.database.db_path}")
    yield
    # 关闭时清理
    print("系统关闭")


app = FastAPI(
    title="情报收集分析评估预测多Agent系统",
    description="基于确定性治理层和分层执行单元的情报分析预测系统",
    version="0.1.0",
    lifespan=lifespan
)

# CORS配置（允许移动端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== 任务管理 ==========

@app.post("/api/v1/tasks", response_model=TaskContract)
async def create_task(task_input: dict):
    """创建新任务"""
    db = get_database()
    
    task = TaskContract(
        task_id=str(uuid.uuid4()),
        task_type=task_input.get("task_type", "research"),
        input_data=task_input.get("input_data", {}),
        input_hash=task_input.get("input_hash", ""),
        method_version="v0.1.0",
        created_at=datetime.now(),
        status=TaskStatus.PENDING,
        commitment_level=CommitmentLevel.C,
        permission_level=PermissionLevel.L1
    )
    
    db.save_task(task)
    return task


@app.get("/api/v1/tasks/{task_id}", response_model=TaskContract)
async def get_task(task_id: str):
    """获取任务详情"""
    db = get_database()
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@app.get("/api/v1/tasks", response_model=List[TaskContract])
async def list_tasks(status: Optional[str] = None, limit: int = 20):
    """列出任务"""
    db = get_database()
    if status:
        # 按状态过滤
        tasks = db.get_pending_tasks(limit)
    else:
        tasks = db.get_pending_tasks(limit)
    return tasks


@app.post("/api/v1/tasks/{task_id}/start")
async def start_task(task_id: str, background_tasks: BackgroundTasks):
    """启动任务执行"""
    orchestrator = get_orchestrator()
    db = get_database()
    
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 启动工作流
    state = await orchestrator.start_task(task)
    
    # 后台执行工作流步骤
    async def execute_workflow():
        while state.current_step != WorkflowStep.COMPLETE:
            try:
                state = await orchestrator.execute_next_step(task_id)
            except Exception as e:
                print(f"工作流执行错误: {e}")
                break
    
    background_tasks.add_task(execute_workflow)
    
    return {"status": "started", "task_id": task_id, "current_step": state.current_step.value}


@app.post("/api/v1/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    """恢复中断的任务（断点续传）"""
    orchestrator = get_orchestrator()
    
    try:
        state = await orchestrator.resume_task(task_id)
        return {"status": "resumed", "task_id": task_id, "resume_step": state.current_step.value}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== 证据管理 ==========

@app.get("/api/v1/tasks/{task_id}/evidence", response_model=List[Evidence])
async def get_task_evidence(task_id: str):
    """获取任务的证据列表"""
    db = get_database()
    evidence = db.get_evidence_by_task(task_id)
    return evidence


# ========== 预测管理 ==========

@app.post("/api/v1/forecasts")
async def register_forecast(forecast_input: dict):
    """登记预测"""
    forecast_service = get_forecast_service()
    
    try:
        forecast = forecast_service.register_forecast(
            task_id=forecast_input["task_id"],
            event_description=forecast_input["event_description"],
            probability=forecast_input["probability"],
            time_range_start=datetime.fromisoformat(forecast_input["time_range_start"]),
            time_range_end=datetime.fromisoformat(forecast_input["time_range_end"]),
            falsifiable_anchor=forecast_input["falsifiable_anchor"],
            premises=forecast_input.get("premises", []),
            evidence_snapshot=forecast_input.get("evidence_snapshot", {})
        )
        return forecast
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/forecasts/unsettled", response_model=List[ForecastRecord])
async def get_unsettled_forecasts():
    """获取未结算的预测"""
    forecast_service = get_forecast_service()
    return forecast_service.get_unsettled_forecasts()


@app.post("/api/v1/forecasts/{forecast_id}/settle")
async def settle_forecast(forecast_id: str, settlement_input: dict):
    """结算预测"""
    forecast_service = get_forecast_service()
    
    try:
        result = forecast_service.settle_forecast(
            forecast_id=forecast_id,
            actual_outcome=settlement_input["actual_outcome"],
            evaluation_rules=settlement_input.get("evaluation_rules")
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/forecasts/brier-score")
async def get_brier_score():
    """获取Brier Score"""
    forecast_service = get_forecast_service()
    result = forecast_service.calculate_brier_score()
    return {
        "score": result.score,
        "count": result.count,
        "calibrated": result.calibrated,
        "vs_baseline": result.vs_baseline,
        "calibration_curve": result.calibration_curve
    }


# ========== 权限管理 ==========

@app.post("/api/v1/permissions/check")
async def check_permission(permission_input: dict):
    """检查权限"""
    permission_service = get_permission_service()
    
    result = permission_service.can_execute(
        action_type=permission_input["action_type"],
        action_description=permission_input["action_description"],
        current_level=PermissionLevel(permission_input.get("current_level", "L1")),
        context=permission_input.get("context")
    )
    
    return result


@app.post("/api/v1/permissions/tighten")
async def tighten_permission(new_level: str):
    """收紧权限（单向）"""
    permission_service = get_permission_service()
    
    try:
        success = permission_service.tighten_permission(PermissionLevel(new_level))
        if success:
            return {"status": "tightened", "new_level": new_level}
        else:
            raise HTTPException(
                status_code=400,
                detail="权限只能收紧，不能放宽（单向原则）"
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== 承诺等级 ==========

@app.post("/api/v1/commitment/evaluate")
async def evaluate_commitment(commitment_input: dict):
    """评估承诺等级"""
    commitment_engine = get_commitment_engine()
    
    # 构建输入
    evidence_list = [
        Evidence(**e) for e in commitment_input.get("evidence_list", [])
    ]
    
    input_data = CommitmentInput(
        evidence_list=evidence_list,
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
    
    decision = commitment_engine.evaluate(input_data)
    
    return {
        "level": decision.level.value,
        "reason": decision.reason,
        "conditions": decision.conditions,
        "timestamp": decision.timestamp.isoformat()
    }


# ========== 审计日志 ==========

@app.get("/api/v1/audit-logs")
async def get_audit_logs(task_id: Optional[str] = None, limit: int = 100):
    """获取审计日志"""
    db = get_database()
    logs = db.get_audit_logs(task_id, limit)
    return logs


# ========== 系统状态 ==========

@app.get("/api/v1/status")
async def get_system_status():
    """获取系统状态"""
    settings = get_settings()
    return {
        "version": "0.1.0",
        "mobile_mode": settings.mobile_mode,
        "cloud_fallback": settings.cloud_fallback,
        "database_path": settings.database.db_path,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
