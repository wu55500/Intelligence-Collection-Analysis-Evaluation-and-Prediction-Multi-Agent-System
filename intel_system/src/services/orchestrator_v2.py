"""
M19 工作流编排器 V2 - 四层架构 + 验收闸门 + 红队 + 检查点

四层架构：
L1 · 交互与任务编排层 - M13报告、M19工作流、主控Agent
L2 · 情报与分析能力层 - M1-M7, M9-M12, M16-M18
L3 · 确定性治理层 - M8预测、M14权限、M20健康、M21承诺
L4 · 数据与基础设施层 - 数据库、缓存、检索、检查点

关键改进：
- 集成统一验收闸门
- 集成独立红队验证
- 集成持久化检查点
- 支持任意步骤重新运行
- 保留新旧运行差异
"""

from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import uuid
import json

from ..core.schemas import TaskContract, TaskStatus, CommitmentLevel, AuditLog
from ..core.config import get_settings
from ..core.database import get_database
from ..core.validation_gate import ValidationGate, ModuleOutput, ModuleStatus
from ..services.red_team import IndependentVerifier
from ..services.checkpoint import CheckpointService, Checkpoint, CheckpointStatus


class WorkflowStep(str, Enum):
    """工作流步骤（四层分类）"""
    # L2 · 情报与分析能力层
    COLLECT = "collect"           # M1 采集
    GOVERN = "govern"             # M2 治理
    EDA = "eda"                   # M3 EDA
    CAUSAL_REVIEW = "causal"      # M5 因果审查
    EVIDENCE_EVAL = "eval"        # M12 证据评估
    # L3 · 确定性治理层
    COMMITMENT = "commitment"     # M21 承诺等级
    FORECAST = "forecast"         # M8 预测登记
    PERMISSION = "permission"     # M14 权限检查
    # L2 · 独立红队
    RED_TEAM = "red_team"         # 独立验证
    # L1 · 交互与任务编排层
    REPORT = "report"             # M13 报告
    COMPLETE = "complete"


@dataclass
class StepDiff:
    """步骤运行差异（保留新旧运行之间的差异）"""
    step_name: str
    old_output: Dict[str, Any]
    new_output: Dict[str, Any]
    changed_fields: List[str]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class WorkflowState:
    """工作流状态"""
    task_id: str
    current_step: WorkflowStep
    step_results: Dict[str, ModuleOutput] = field(default_factory=dict)
    step_diffs: List[StepDiff] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    started_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    is_blocked: bool = False
    block_reason: str = ""
    red_team_passed: bool = False


class WorkflowOrchestratorV2:
    """
    工作流编排器 V2
    
    改进：
    1. 每步输出经过验收闸门
    2. 关键步骤后触发红队验证
    3. 每步持久化检查点
    4. 支持单步重新运行并保留差异
    """
    
    # 步骤执行顺序
    STEP_ORDER = [
        WorkflowStep.COLLECT,
        WorkflowStep.GOVERN,
        WorkflowStep.EDA,
        WorkflowStep.CAUSAL_REVIEW,
        WorkflowStep.EVIDENCE_EVAL,
        WorkflowStep.COMMITMENT,
        WorkflowStep.PERMISSION,
        WorkflowStep.FORECAST,
        WorkflowStep.RED_TEAM,
        WorkflowStep.REPORT,
        WorkflowStep.COMPLETE
    ]
    
    # 关键步骤 - 这些步骤失败会阻断流程
    CRITICAL_STEPS = {
        WorkflowStep.COLLECT,
        WorkflowStep.GOVERN,
        WorkflowStep.COMMITMENT,
        WorkflowStep.FORECAST
    }
    
    # 触发红队的步骤
    RED_TEAM_TRIGGERS = {
        WorkflowStep.EVIDENCE_EVAL,
        WorkflowStep.FORECAST
    }
    
    def __init__(self):
        self.settings = get_settings()
        self.db = get_database()
        self.validation_gate = ValidationGate()
        self.red_team = IndependentVerifier()
        self.checkpoint_service = CheckpointService()
        self._active_states: Dict[str, WorkflowState] = {}
        self._step_handlers: Dict[WorkflowStep, Callable] = {}
    
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
        
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        self.db.save_task(task)
        
        self._log_action("task_started", task.task_id, {
            "task_type": task.task_type,
            "architecture": "v2_four_layer"
        })
        
        return state
    
    async def execute_next_step(self, task_id: str) -> WorkflowState:
        """执行下一步"""
        state = self._active_states.get(task_id)
        if not state:
            raise ValueError(f"任务 {task_id} 状态不存在")
        
        if state.is_blocked:
            raise RuntimeError(f"任务已阻断: {state.block_reason}")
        
        current_step = state.current_step
        
        # 1. 创建检查点
        checkpoint = Checkpoint(
            task_id=task_id,
            step_name=current_step.value
        )
        self.checkpoint_service.save_checkpoint(checkpoint)
        
        # 2. 获取处理函数
        handler = self._step_handlers.get(current_step)
        if not handler:
            module_output = ModuleOutput(
                module_name=current_step.value,
                status=ModuleStatus.SKIPPED,
                output_data={"skipped": True}
            )
            state.step_results[current_step.value] = module_output
            return self._advance_step(state)
        
        # 3. 执行步骤
        try:
            raw_result = await handler(task_id, {
                step.value: state.step_results[step.value].output_data
                for step in self.STEP_ORDER
                if step.value in state.step_results
            })
            
            # 4. 包装为 ModuleOutput（如果不是的话）
            if isinstance(raw_result, ModuleOutput):
                module_output = raw_result
            else:
                module_output = ModuleOutput(
                    module_name=current_step.value,
                    status=ModuleStatus.SUCCESS,
                    output_data=raw_result if isinstance(raw_result, dict) else {"result": raw_result}
                )
            
            # 5. 验收闸门检查
            validation = self.validation_gate.validate(module_output)
            
            if validation.passed:
                # 检查点标记完成
                self.checkpoint_service.mark_completed(
                    checkpoint.checkpoint_id, module_output.output_data
                )
                
                # 记录结果
                state.step_results[current_step.value] = module_output
                state.last_updated = datetime.now()
                state.retry_count = 0
                
                self._log_action("step_completed", task_id, {
                    "step": current_step.value,
                    "validation": "passed"
                })
                
                # 6. 红队检查
                if current_step in self.RED_TEAM_TRIGGERS:
                    await self._run_red_team(state, current_step)
                
                return self._advance_step(state)
            
            else:
                # 验收不通过
                self.checkpoint_service.mark_failed(
                    checkpoint.checkpoint_id,
                    "; ".join(validation.critical_issues)
                )
                
                if current_step in self.CRITICAL_STEPS:
                    state.is_blocked = True
                    state.block_reason = f"关键步骤 {current_step.value} 验收不通过: {'; '.join(validation.critical_issues)}"
                    self._fail_task(state)
                else:
                    state.errors.append({
                        "step": current_step.value,
                        "issues": validation.critical_issues,
                        "warnings": validation.warnings
                    })
                    return self._advance_step(state)
        
        except Exception as e:
            self.checkpoint_service.mark_failed(checkpoint.checkpoint_id, str(e))
            return await self._handle_step_error(state, current_step, e)
    
    async def _run_red_team(self, state: WorkflowState, step: WorkflowStep):
        """运行红队验证"""
        evidence_data = []
        if "eval" in state.step_results:
            evidence_data = state.step_results["eval"].output_data.get("evidence_list", [])
        
        claim = state.step_results.get("eda", ModuleOutput(
            module_name="eda", output_data={"claim": ""}
        )).output_data.get("claim", "")
        
        if not claim and "report" in state.step_results:
            claim = state.step_results["report"].output_data.get("conclusion", "")
        
        methodology = {
            "method": step.value,
            "data_characteristics": {
                "sample_size": len(evidence_data)
            }
        }
        
        forecast = None
        if "forecast" in state.step_results:
            forecast = state.step_results["forecast"].output_data
        
        red_team_report = await self.red_team.verify(
            task_id=state.task_id,
            claim=claim,
            commitment_level="C",
            evidence_list=evidence_data,
            methodology=methodology,
            forecast=forecast
        )
        
        state.red_team_passed = not red_team_report.should_block
        
        if red_team_report.should_block:
            state.is_blocked = True
            state.block_reason = f"红队阻断: {red_team_report.block_reason}"
    
    async def rerun_step(self, task_id: str, step: WorkflowStep) -> WorkflowState:
        """
        重新运行指定步骤
        
        保留新旧运行之间的差异
        """
        state = self._active_states.get(task_id)
        if not state:
            raise ValueError(f"任务 {task_id} 状态不存在")
        
        old_output = state.step_results.get(step.value)
        
        # 重新执行
        old_step = state.current_step
        state.current_step = step
        
        new_state = await self.execute_next_step(task_id)
        
        # 记录差异
        new_output = state.step_results.get(step.value)
        if old_output and new_output:
            diff = self._compute_diff(step.value, old_output, new_output)
            if diff:
                state.step_diffs.append(diff)
        
        state.current_step = old_step
        return new_state
    
    def _compute_diff(self, step_name: str, old: ModuleOutput, new: ModuleOutput) -> Optional[StepDiff]:
        """计算差异"""
        changed_fields = []
        
        all_keys = set(list(old.output_data.keys()) + list(new.output_data.keys()))
        for key in all_keys:
            old_val = old.output_data.get(key)
            new_val = new.output_data.get(key)
            if old_val != new_val:
                changed_fields.append(key)
        
        if not changed_fields:
            return None
        
        return StepDiff(
            step_name=step_name,
            old_output=old.output_data,
            new_output=new.output_data,
            changed_fields=changed_fields
        )
    
    def _advance_step(self, state: WorkflowState) -> WorkflowState:
        """推进到下一步"""
        current_idx = self.STEP_ORDER.index(state.current_step)
        if current_idx + 1 >= len(self.STEP_ORDER):
            self._complete_task(state)
        else:
            state.current_step = self.STEP_ORDER[current_idx + 1]
        return state
    
    async def _handle_step_error(self, state, step, error):
        """处理错误"""
        state.retry_count += 1
        state.errors.append({
            "step": step.value,
            "error": str(error),
            "retry_count": state.retry_count
        })
        
        if state.retry_count >= state.max_retries:
            if step in self.CRITICAL_STEPS:
                state.is_blocked = True
                state.block_reason = f"关键步骤 {step.value} 连续失败{state.retry_count}次"
            self._fail_task(state)
        return state
    
    def _complete_task(self, state):
        """完成任务"""
        self.db.update_task_status(state.task_id, TaskStatus.SUCCESS, completed_at=datetime.now())
        self._log_action("task_completed", state.task_id, {
            "total_steps": len(state.step_results),
            "red_team_passed": state.red_team_passed
        })
    
    def _fail_task(self, state):
        """任务失败"""
        status = TaskStatus.FAILED
        if state.is_blocked:
            status = TaskStatus.CIRCUIT_BREAK
        self.db.update_task_status(
            state.task_id, status, completed_at=datetime.now(),
            error_code=state.block_reason or (state.errors[-1]["error"] if state.errors else "unknown")
        )
    
    async def resume_task(self, task_id: str) -> WorkflowState:
        """从检查点恢复任务"""
        recovery = self.checkpoint_service.get_recovery_info(task_id)
        
        if not recovery["can_resume"]:
            raise RuntimeError(f"任务 {task_id} 无法恢复: 失败步骤超出重试限制")
        
        last_completed = recovery["last_completed"]
        if last_completed:
            resume_step_idx = self.STEP_ORDER.index(WorkflowStep(last_completed)) + 1
            if resume_step_idx >= len(self.STEP_ORDER):
                resume_step_idx = len(self.STEP_ORDER) - 1
        else:
            resume_step_idx = 0
        
        state = WorkflowState(
            task_id=task_id,
            current_step=self.STEP_ORDER[resume_step_idx]
        )
        self._active_states[task_id] = state
        
        self._log_action("task_resumed", task_id, {
            "resume_step": state.current_step.value,
            "completed_steps": recovery["completed"]
        })
        
        return state
    
    def get_step_diffs(self, task_id: str) -> List[Dict[str, Any]]:
        """获取步骤运行差异"""
        state = self._active_states.get(task_id)
        if not state:
            return []
        
        return [
            {
                "step": d.step_name,
                "changed_fields": d.changed_fields,
                "timestamp": d.timestamp.isoformat()
            }
            for d in state.step_diffs
        ]
    
    def _log_action(self, action, task_id, details):
        audit = AuditLog(
            log_id=str(uuid.uuid4()),
            action=action,
            actor="orchestrator_v2",
            details=details,
            task_id=task_id
        )
        self.db.log_audit(audit)
