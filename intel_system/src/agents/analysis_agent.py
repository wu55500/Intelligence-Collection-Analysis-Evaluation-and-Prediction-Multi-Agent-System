"""
分析执行Agent

职责：
- EDA探索性分析
- 统计检验（Pearson+Spearman双系数）
- 因果审查门
- 基线模型
- 预测分析
"""

from typing import List, Dict, Any
from datetime import datetime
import uuid

from .base_agent import BaseAgent, AgentResponse
from ..core.schemas import TaskContract, CommitmentLevel
from ..modules.m3_eda.analyzer import EDAAnalyzer
from ..modules.m5_causal.reviewer import CausalReviewer
from ..services.forecast_service import ForecastService
from ..services.commitment_engine import CommitmentEngine, CommitmentInput


class AnalysisAgent(BaseAgent):
    """
    分析执行单元
    
    职责：
    1. EDA探索性分析
    2. 统计检验（双系数、FDR校正、Bootstrap）
    3. 因果推断审查门
    4. 预测登记
    5. 承诺等级评估
    """
    
    def __init__(self):
        super().__init__(agent_id="analysis_agent", role="分析执行单元")
        self.eda_analyzer = EDAAnalyzer()
        self.causal_reviewer = CausalReviewer()
        self.forecast_service = ForecastService()
        self.commitment_engine = CommitmentEngine()
        
        # 注册工具
        self.register_tool("eda", self._tool_eda)
        self.register_tool("causal_review", self._tool_causal_review)
        self.register_tool("commitment_eval", self._tool_commitment_eval)
        self.register_tool("forecast_register", self._tool_forecast_register)
    
    async def _tool_eda(self, **kwargs) -> Dict[str, Any]:
        """EDA分析工具"""
        data = kwargs.get("data", [])
        second_data = kwargs.get("second_data")
        
        result = self.eda_analyzer.analyze(data, second_data)
        
        return {
            "count": result.statistical_summary.count,
            "mean": result.statistical_summary.mean,
            "std": result.statistical_summary.std,
            "outlier_ratio": result.outlier_detection.outlier_ratio,
            "distribution": result.distribution_check,
            "correlation": {
                "pearson_r": result.correlation_result.pearson_r,
                "spearman_r": result.correlation_result.spearman_r,
                "interpretation": result.correlation_result.interpretation
            } if result.correlation_result else None,
            "recommendations": result.recommendations
        }
    
    async def _tool_causal_review(self, **kwargs) -> Dict[str, Any]:
        """因果审查工具"""
        claim = kwargs.get("claim", "")
        method = kwargs.get("method", "granger")
        data_chars = kwargs.get("data_characteristics", {})
        
        result = self.causal_reviewer.review(claim, method, data_chars)
        language = self.causal_reviewer.get_allowed_language(result)
        
        return {
            "can_claim_causality": result.can_claim_causality,
            "allowed_statement": result.allowed_statement,
            "allowed_terms": language["allowed_terms"],
            "forbidden_terms": language["forbidden_terms"],
            "suggested_rewording": language["suggested_rewording"],
            "warnings": result.warnings
        }
    
    async def _tool_commitment_eval(self, **kwargs) -> Dict[str, Any]:
        """承诺等级评估工具"""
        evidence_list = kwargs.get("evidence_list", [])
        input_data = CommitmentInput(**kwargs)
        
        decision = self.commitment_engine.evaluate(input_data)
        
        return {
            "level": decision.level.value,
            "reason": decision.reason,
            "conditions": decision.conditions
        }
    
    async def _tool_forecast_register(self, **kwargs) -> Dict[str, Any]:
        """预测登记工具"""
        try:
            forecast = self.forecast_service.register_forecast(
                task_id=kwargs["task_id"],
                event_description=kwargs["event_description"],
                probability=kwargs["probability"],
                time_range_start=datetime.fromisoformat(kwargs["time_range_start"]),
                time_range_end=datetime.fromisoformat(kwargs["time_range_end"]),
                falsifiable_anchor=kwargs["falsifiable_anchor"],
                premises=kwargs.get("premises", []),
                evidence_snapshot=kwargs.get("evidence_snapshot", {})
            )
            return {
                "success": True,
                "forecast_id": forecast.forecast_id,
                "registered_at": forecast.registered_at.isoformat()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def execute(self, task: TaskContract) -> AgentResponse:
        """执行分析任务"""
        task_id = task.task_id
        data = task.input_data.get("data", [])
        claim = task.input_data.get("claim", "")
        
        results = {}
        tool_calls = []
        
        # 第1步：EDA
        if data:
            eda_result = await self._tool_eda(data=data)
            results["eda"] = eda_result
            tool_calls.append({"tool": "eda", "result": "success"})
        
        # 第2步：因果审查
        if claim:
            causal_result = await self._tool_causal_review(
                claim=claim,
                method=task.input_data.get("method", "granger"),
                data_characteristics=task.input_data.get("data_characteristics", {})
            )
            results["causal"] = causal_result
            tool_calls.append({"tool": "causal_review", "result": "success"})
        
        content = f"分析执行完成\n"
        for key, val in results.items():
            content += f"- {key}: 已完成\n"
        
        return AgentResponse(
            response_id=str(uuid.uuid4()),
            task_id=task_id,
            content=content,
            tool_calls=tool_calls,
            commitment_level=task.commitment_level,
            timestamp=datetime.now(),
            metadata={"agent_id": self.agent_id, "role": self.role}
        )
