"""
M19 工作流编排器 - 确定性状态机

关键设计（修正问题3）：
- 不是LLM Agent，是工作流编排器 + 持久化状态机
- 管理重试、超时、依赖、失败和恢复
- 支持断点续传、熔断、状态升级/降级
"""

from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import uuid
import json

from ..core.schemas import (
    TaskContract, TaskStatus, CommitmentLevel,
    AuditLog, CircuitBreakerState
)
from ..core.config import get_settings
from ..core.database import get_database


class WorkflowStep(str, Enum):
    """工作流步骤"""
    COLLECT = "collect"           # M1 采集
    GOVERN = "govern"             # M2 治理
    EDA = "eda"                   # M3 EDA
    CAUSAL_REVIEW = "causal"      # M5 因果审查
    EVIDENCE_EVAL = "eval"        # M12 证据评估
    COMMITMENT = "commitment"     # M21 承诺等级
    FORECAST = "forecast"         # M8 预测登记
    REPORT = "report"             # M13 报告
    COMPLETE = "complete"         # 完成


@dataclass
class WorkflowState:
    """工作流状态"""
    task_id: str
    current_step: WorkflowStep
    step_results: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    started_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    is_circuit_broken: bool = False
    circuit_break_reason: Optional[str] = None


class WorkflowOrchestrator:
    """
    工作流编排器
    
    职责：
    1. 管理任务从创建到完成的完整生命周期
    2. 处理步骤间的依赖和状态转换
    3. 支持重试、超时、熔断和断点恢复
    4. 记录完整审计日志
    """
    
    STEP_ORDER = [
        WorkflowStep.COLLECT,
        WorkflowStep.GOVERN,
        WorkflowStep.EDA,
        WorkflowStep.CAUSAL_REVIEW,
        WorkflowStep.EVIDENCE_EVAL,
        WorkflowStep.COMMITMENT,
        WorkflowStep.FORECAST,
        WorkflowStep.REPORT,
        WorkflowStep.COMPLETE
    ]
    
    def __init__(self):
        self.settings = get_settings()
        self.db = get_database()
        self._active_states: Dict[str, WorkflowState] = {}
        self._step_handlers: Dict[WorkflowStep, Callable] = {}
        self._circuit_breakers: Dict[str, CircuitBreakerState] = {}
    
    def register_handler(self, step: WorkflowStep, handler: Callable):
        """注册步骤处理函数"""
        self._step_handlers[step] = handler
    
    async def start_task(self, task: TaskContract) -> WorkflowState:
        """启动任务"""
        state = WorkflowState(
            task_id=task.task_id,
            current_step=WorkflowStep.COLLECT
        )
        
        self._active_states[task.task_id] = state
        
        # 更新任务状态
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        self.db.save_task(task)
        
        # 审计日志
        self._log_action("task_started", task.task_id, {
            "task_type": task.task_type,
            "input_hash": task.input_hash
        })
        
        return state
    
    async def execute_next_step(self, task_id: str) -> WorkflowState:
        """执行下一步"""
        state = self._active_states.get(task_id)
        if not state:
            raise ValueError(f"任务 {task_id} 状态不存在")
        
        if state.is_circuit_broken:
            raise RuntimeError(f"任务已熔断: {state.circuit_break_reason}")
        
        current_step = state.current_step
        
        # 检查处理函数
        handler = self._step_handlers.get(current_step)
        if not handler:
            # 无处理函数，直接跳过到下一步
            state.step_results[current_step.value] = {"status": "skipped"}
            return self._advance_step(state)
        
        # 执行步骤
        try:
            result = await handler(task_id, state.step_results)
            state.step_results[current_step.value] = result
            state.last_updated = datetime.now()
            state.retry_count = 0  # 成功后重置重试计数
            
            self._log_action("step_completed", task_id, {
                "step": current_step.value,
                "result_keys": list(result.keys()) if isinstance(result, dict) else []
            })
            
            return self._advance_step(state)
            
        except Exception as e:
            return await self._handle_step_error(state, current_step, e)
    
    def _advance_step(self, state: WorkflowState) -> WorkflowState:
        """推进到下一步"""
        current_idx = self.STEP_ORDER.index(state.current_step)
        
        if current_idx + 1 >= len(self.STEP_ORDER):
            # 所有步骤完成
            state.current_step = WorkflowStep.COMPLETE
            self._complete_task(state)
        else:
            state.current_step = self.STEP_ORDER[current_idx + 1]
        
        return state
    
    async def _handle_step_error(
        self,
        state: WorkflowState,
        step: WorkflowStep,
        error: Exception
    ) -> WorkflowState:
        """处理步骤错误"""
        state.retry_count += 1
        state.errors.append({
            "step": step.value,
            "error": str(error),
            "retry_count": state.retry_count,
            "timestamp": datetime.now().isoformat()
        })
        
        self._log_action("step_error", state.task_id, {
            "step": step.value,
            "error": str(error),
            "retry_count": state.retry_count
        })
        
        # 检查是否需要熔断
        if self._should_circuit_break(state, step):
            state.is_circuit_broken = True
            state.circuit_break_reason = f"步骤{step.value}连续失败触发熔断"
            self._fail_task(state)
            return state
        
        # 检查重试上限
        if state.retry_count >= state.max_retries:
            self._fail_task(state)
            return state
        
        # 否则保持当前步骤，等待重试
        return state
    
    def _should_circuit_break(
        self,
        state: WorkflowState,
        step: WorkflowStep
    ) -> bool:
        """判断是否应该熔断"""
        # 统计该步骤的连续失败次数
        recent_errors = [
            e for e in state.errors
            if e["step"] == step.value
        ]
        
        # 连续失败超过阈值 → 熔断
        if len(recent_errors) >= 5:
            return True
        
        # 检查熔断关键词
        error_str = str(state.errors[-1]["error"]).lower() if state.errors else ""
        break_keywords = self.settings.commitment.circuit_break_keywords
        if any(kw in error_str for kw in break_keywords):
            return True
        
        return False
    
    def _complete_task(self, state: WorkflowState):
        """完成任务"""
        self.db.update_task_status(
            state.task_id,
            TaskStatus.SUCCESS,
            completed_at=datetime.now()
        )
        
        self._log_action("task_completed", state.task_id, {
            "total_steps": len(state.step_results),
            "duration_seconds": (datetime.now() - state.started_at).total_seconds()
        })
    
    def _fail_task(self, state: WorkflowState):
        """任务失败"""
        status = TaskStatus.FAILED
        if state.is_circuit_broken:
            status = TaskStatus.CIRCUIT_BREAK
        
        self.db.update_task_status(
            state.task_id,
            status,
            completed_at=datetime.now(),
            error_code=state.errors[-1]["error"] if state.errors else "unknown"
        )
        
        self._log_action("task_failed", state.task_id, {
            "status": status.value,
            "error_count": len(state.errors),
            "circuit_broken": state.is_circuit_broken
        })
    
    async def resume_task(self, task_id: str) -> WorkflowState:
        """
        恢复中断的任务（断点续传）
        
        关键：任何环节中断可恢复，重要信源无遗漏
        """
        task = self.db.get_task(task_id)
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")
        
        if task.status not in (TaskStatus.RUNNING, TaskStatus.PENDING):
            raise ValueError(f"任务状态为{task.status.value}，不可恢复")
        
        # 从数据库恢复工作流状态
        state = WorkflowState(
            task_id=task_id,
            current_step=self._determine_resume_step(task),
            started_at=task.created_at
        )
        
        self._active_states[task_id] = state
        
        self._log_action("task_resumed", task_id, {
            "resume_step": state.current_step.value
        })
        
        return state
    
    def _determine_resume_step(self, task: TaskContract) -> WorkflowStep:
        """确定恢复点"""
        # 简化实现：从pending恢复到第一步
        # 实际应该从checkpoint恢复
        return WorkflowStep.COLLECT
    
    def get_state(self, task_id: str) -> Optional[WorkflowState]:
        """获取工作流状态"""
        return self._active_states.get(task_id)
    
    def _log_action(self, action: str, task_id: str, details: Dict[str, Any]):
        """记录审计日志"""
        audit = AuditLog(
            log_id=str(uuid.uuid4()),
            action=action,
            actor="orchestrator",
            details=details,
            task_id=task_id
        )
        self.db.log_audit(audit)


# 全局实例
_orchestrator: Optional[WorkflowOrchestrator] = None

def get_orchestrator() -> WorkflowOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = WorkflowOrchestrator()
    return _orchestrator
