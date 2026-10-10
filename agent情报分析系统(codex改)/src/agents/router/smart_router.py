"""
智能路由 - 根据任务类型自动选择最合适的模型
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import json

from .model_registry import ModelRegistry, ModelProfile, TaskType, Capability


@dataclass
class RoutingDecision:
    """路由决策记录"""
    task_type: TaskType
    selected_model: ModelProfile
    alternative_models: List[ModelProfile]
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)
    cost_estimate: float = 0.0
    latency_estimate_ms: int = 0


class SmartRouter:
    """
    智能路由器
    
    根据任务类型、约束条件（成本、延迟、能力）自动选择最佳模型
    """
    
    def __init__(self, registry: Optional[ModelRegistry] = None):
        self.registry = registry or ModelRegistry()
        self.routing_history: List[RoutingDecision] = []
        self._custom_rules: Dict[TaskType, List[str]] = {}  # 强制偏好
        self._fallback_chain: List[str] = [
            "openai_gpt4o",
            "anthropic_claude_sonnet",
            "google_gemini_pro",
            "deepseek_v3"
        ]
    
    def route(
        self,
        task_type: TaskType,
        context: Optional[Dict[str, Any]] = None,
        max_cost: Optional[float] = None,
        max_latency_ms: Optional[int] = None,
        exclude_models: List[str] = None,
        prefer_fast: bool = False
    ) -> RoutingDecision:
        """
        路由到最佳模型
        
        Args:
            task_type: 任务类型
            context: 任务上下文（可能包含特殊需求）
            max_cost: 最大成本（美元/1k tokens）
            max_latency_ms: 最大延迟
            exclude_models: 排除的模型
            prefer_fast: 优先速度
        
        Returns:
            RoutingDecision: 路由决策
        """
        context = context or {}
        exclude_models = exclude_models or []
        
        # 1. 检查自定义规则
        preferred = self._custom_rules.get(task_type, [])
        
        # 2. 根据约束找最佳模型
        candidates = []
        for model in self.registry.list_models():
            if model.model_id in exclude_models:
                continue
            if max_cost and model.cost_per_1k_tokens > max_cost:
                continue
            if max_latency_ms and model.avg_latency_ms > max_latency_ms:
                continue
            
            candidates.append(model)
        
        # 3. 根据任务类型打分
        best = self.registry.find_best_for_task(task_type, exclude=exclude_models)
        
        # 4. 如果有偏好规则，优先使用
        if preferred:
            for pref_id in preferred:
                model = self.registry.get(pref_id)
                if model and model.is_available and model not in candidates:
                    continue
                if model and model.is_available:
                    best = model
                    break
        
        # 5. 如果要求快速，切换到快速模型
        if prefer_fast and best and best.avg_latency_ms > 3000:
            fast_model = max(
                [m for m in candidates if m.avg_latency_ms < 2000],
                key=lambda m: m.capabilities.get(Capability.SPEED, 0),
                default=best
            )
            best = fast_model
        
        # 6. 备选模型
        alternatives = [m for m in candidates if m.model_id != best.model_id][:2]
        
        # 7. 构建决策
        decision = RoutingDecision(
            task_type=task_type,
            selected_model=best,
            alternative_models=alternatives,
            reason=best.notes,
            cost_estimate=best.cost_per_1k_tokens,
            latency_estimate_ms=best.avg_latency_ms
        )
        
        self.routing_history.append(decision)
        return decision
    
    def set_preference(self, task_type: TaskType, model_ids: List[str]):
        """设置任务类型的模型偏好"""
        self._custom_rules[task_type] = model_ids
    
    def set_fallback_chain(self, model_ids: List[str]):
        """设置降级链"""
        self._fallback_chain = model_ids
    
    async def call_model(
        self,
        decision: RoutingDecision,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        tools: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        调用路由选择的模型
        
        实际集成时，这里会调用 LiteLLM 或其他 SDK
        """
        model = decision.selected_model
        
        # 构建调用参数
        call_params = {
            "model": model.model_name,
            "messages": [],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        if system_prompt:
            call_params["messages"].append({"role": "system", "content": system_prompt})
        call_params["messages"].append({"role": "user", "content": prompt})
        
        if tools and model.supports_tools:
            call_params["tools"] = tools
        
        # 实际调用（这里用模拟）
        try:
            # 实际应该用 litellm.completion() 或对应的 SDK
            result = await self._execute_call(model, call_params)
            return result
        except Exception as e:
            # 降级到备选模型
            for alt in decision.alternative_models:
                try:
                    call_params["model"] = alt.model_name
                    result = await self._execute_call(alt, call_params)
                    return result
                except Exception:
                    continue
            
            raise Exception(f"所有模型调用失败: {e}")
    
    async def _execute_call(self, model: ModelProfile, params: Dict) -> Dict[str, Any]:
        """
        执行模型调用
        
        实际实现应该集成 litellm：
        import litellm
        response = litellm.completion(**params)
        """
        # 模拟返回
        return {
            "model_used": model.model_id,
            "provider": model.provider,
            "content": f"[{model.model_name}] 处理完成",
            "usage": {
                "prompt_tokens": len(params.get("messages", [{}])[0].get("content", "")) // 4,
                "completion_tokens": 100,
                "total_cost": model.cost_per_1k_tokens * 0.1
            }
        }
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """获取路由统计"""
        if not self.routing_history:
            return {"total_decisions": 0}
        
        task_counts = {}
        model_counts = {}
        total_cost = 0
        
        for decision in self.routing_history:
            task_type = decision.task_type.value
            task_counts[task_type] = task_counts.get(task_type, 0) + 1
            
            model_id = decision.selected_model.model_id
            model_counts[model_id] = model_counts.get(model_id, 0) + 1
            
            total_cost += decision.cost_estimate
        
        return {
            "total_decisions": len(self.routing_history),
            "by_task_type": task_counts,
            "by_model": model_counts,
            "estimated_total_cost": total_cost,
            "avg_cost_per_call": total_cost / len(self.routing_history) if self.routing_history else 0
        }
