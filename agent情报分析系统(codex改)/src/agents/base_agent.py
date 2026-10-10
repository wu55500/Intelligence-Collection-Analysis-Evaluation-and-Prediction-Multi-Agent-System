"""
Agent基类

关键设计：
- 统一工具调用接口
- 支持任务分解、多步执行
- 不拥有绕过规则的权力
- 关键规则由确定性服务执行
"""

from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import uuid

from ..core.schemas import TaskContract, CommitmentLevel
from ..core.config import get_settings


@dataclass
class AgentResponse:
    """Agent响应"""
    response_id: str
    task_id: str
    content: str
    tool_calls: List[Dict[str, Any]]
    commitment_level: CommitmentLevel
    timestamp: datetime
    metadata: Dict[str, Any]


class BaseAgent:
    """
    Agent基类
    
    职责：
    1. 接收任务，分解为子步骤
    2. 调用工具执行子步骤
    3. 综合结果，生成响应
    4. 不拥有绕过确定性规则的权力
    """
    
    def __init__(self, agent_id: str, role: str):
        self.agent_id = agent_id
        self.role = role
        self.settings = get_settings()
        self.tools: Dict[str, Callable] = {}
    
    def register_tool(self, tool_name: str, tool_func: Callable):
        """注册工具"""
        self.tools[tool_name] = tool_func
    
    async def execute(self, task: TaskContract) -> AgentResponse:
        """执行任务"""
        # 1. 分解任务
        sub_tasks = await self._decompose_task(task)
        
        # 2. 依次执行子任务
        results = []
        tool_calls = []
        
        for sub_task in sub_tasks:
            result, calls = await self._execute_sub_task(sub_task)
            results.append(result)
            tool_calls.extend(calls)
        
        # 3. 综合结果
        content = await self._synthesize_results(task, results)
        
        # 4. 生成响应
        response = AgentResponse(
            response_id=str(uuid.uuid4()),
            task_id=task.task_id,
            content=content,
            tool_calls=tool_calls,
            commitment_level=task.commitment_level,
            timestamp=datetime.now(),
            metadata={
                "agent_id": self.agent_id,
                "role": self.role,
                "sub_task_count": len(sub_tasks)
            }
        )
        
        return response
    
    async def _decompose_task(self, task: TaskContract) -> List[Dict[str, Any]]:
        """分解任务为子步骤"""
        # 简化实现：根据任务类型返回不同的子任务
        # 实际应该由LLM动态分解
        
        if task.task_type == "research":
            return [
                {"type": "collect", "query": task.input_data.get("query", "")},
                {"type": "analyze", "data": "collected_evidence"},
                {"type": "summarize", "findings": "analysis_results"}
            ]
        elif task.task_type == "analysis":
            return [
                {"type": "eda", "dataset": task.input_data.get("dataset", "")},
                {"type": "statistical_test", "hypothesis": task.input_data.get("hypothesis", "")},
                {"type": "interpret", "results": "test_results"}
            ]
        else:
            return [{"type": "default", "input": task.input_data}]
    
    async def _execute_sub_task(
        self,
        sub_task: Dict[str, Any]
    ) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """执行子任务"""
        tool_calls = []
        
        # 根据子任务类型选择工具
        task_type = sub_task.get("type")
        
        if task_type in self.tools:
            tool = self.tools[task_type]
            try:
                result = await tool(**sub_task)
                tool_calls.append({
                    "tool": task_type,
                    "input": sub_task,
                    "output": result,
                    "success": True
                })
                return result, tool_calls
            except Exception as e:
                tool_calls.append({
                    "tool": task_type,
                    "input": sub_task,
                    "error": str(e),
                    "success": False
                })
                return {"error": str(e)}, tool_calls
        
        # 无对应工具，返回默认结果
        return {"status": "no_tool", "input": sub_task}, tool_calls
    
    async def _synthesize_results(
        self,
        task: TaskContract,
        results: List[Dict[str, Any]]
    ) -> str:
        """综合结果"""
        # 简化实现：拼接结果
        # 实际应该由LLM综合
        summary_parts = []
        for i, result in enumerate(results, 1):
            if "error" in result:
                summary_parts.append(f"步骤{i}失败: {result['error']}")
            else:
                summary_parts.append(f"步骤{i}完成")
        
        return f"任务{task.task_id}执行完成。" + "; ".join(summary_parts)
