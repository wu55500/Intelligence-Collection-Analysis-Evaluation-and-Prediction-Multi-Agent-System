"""
研究执行Agent

职责：
- 采集多源情报
- 证据提取与整理
- 数据清洗与分层标注
- 反向检索（必带反向词）

不是LLM做确定性工作，而是协调工具调用
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from .base_agent import BaseAgent, AgentResponse
from ..core.schemas import TaskContract, Evidence, CommitmentLevel
from ..modules.m1_collection.collector import MultiSourceCollector
from ..modules.m2_governance.governor import DataGovernor
from ..modules.m12_evidence.chain import EvidenceChain


class ResearchAgent(BaseAgent):
    """
    研究执行单元
    
    职责：
    1. 执行多源采集（搜索+垂直站+API）
    2. 强制反向检索
    3. 一手源直读
    4. 数据治理（清洗去重+分层标注）
    5. 证据链评估（三角验证）
    """
    
    def __init__(self):
        super().__init__(agent_id="research_agent", role="研究执行单元")
        self.collector = MultiSourceCollector()
        self.governor = DataGovernor()
        self.evidence_chain = EvidenceChain()
        
        # 注册工具
        self.register_tool("collect", self._tool_collect)
        self.register_tool("govern", self._tool_govern)
        self.register_tool("evaluate", self._tool_evaluate)
    
    async def _tool_collect(self, **kwargs) -> Dict[str, Any]:
        """采集工具"""
        query = kwargs.get("query", "")
        task_id = kwargs.get("task_id", "")
        
        evidence_list = await self.collector.collect(
            query=query,
            task_id=task_id,
            include_reverse=True,  # 强制反向检索
            max_sources=20
        )
        
        return {
            "evidence_count": len(evidence_list),
            "evidence": evidence_list,
            "has_reverse": True
        }
    
    async def _tool_govern(self, **kwargs) -> Dict[str, Any]:
        """治理工具"""
        evidence_list = kwargs.get("data", [])
        
        result = self.governor.govern(evidence_list)
        
        return {
            "original_count": result.original_count,
            "final_count": result.final_count,
            "removed_count": result.removed_count,
            "clean_actions": [
                {"type": a.action_type, "reason": a.reason}
                for a in result.clean_actions
            ],
            "quality_distribution": result.quality_distribution,
            "quality_score": result.data_quality_report.get("quality_score", 0),
            "governed_evidence": result.governed_evidence
        }
    
    async def _tool_evaluate(self, **kwargs) -> Dict[str, Any]:
        """证据评估工具"""
        evidence_list = kwargs.get("data", [])
        conclusion = kwargs.get("conclusion", "")
        
        result = self.evidence_chain.evaluate_chain(evidence_list, conclusion)
        
        return {
            "overall_strength": result.overall_strength,
            "max_commitment_level": result.max_commitment_level,
            "verification_level": result.triangulation.verification_level,
            "independent_source_count": result.triangulation.independent_source_count,
            "conflict_count": len(result.conflicts),
            "recommendations": result.recommendations
        }
    
    async def execute(self, task: TaskContract) -> AgentResponse:
        """执行研究任务"""
        query = task.input_data.get("query", "")
        task_id = task.task_id
        
        # 第1步：采集
        collect_result = await self._tool_collect(query=query, task_id=task_id)
        evidence_list = collect_result["evidence"]
        
        # 第2步：治理
        govern_result = await self._tool_govern(data=evidence_list)
        governed_evidence = govern_result["governed_evidence"]
        
        # 第3步：评估
        evaluate_result = await self._tool_evaluate(
            data=governed_evidence,
            conclusion=query
        )
        
        # 综合响应
        content = (
            f"研究执行完成\n"
            f"- 采集证据: {collect_result['evidence_count']}条\n"
            f"- 治理后: {govern_result['final_count']}条（去除{govern_result['removed_count']}条）\n"
            f"- 证据强度: {evaluate_result['overall_strength']}\n"
            f"- 独立来源: {evaluate_result['independent_source_count']}\n"
            f"- 最高承诺等级: {evaluate_result['max_commitment_level']}"
        )
        
        return AgentResponse(
            response_id=str(uuid.uuid4()),
            task_id=task_id,
            content=content,
            tool_calls=[
                {"tool": "collect", "result": "success"},
                {"tool": "govern", "result": "success"},
                {"tool": "evaluate", "result": "success"}
            ],
            commitment_level=task.commitment_level,
            timestamp=datetime.now(),
            metadata={
                "agent_id": self.agent_id,
                "role": self.role,
                "evidence_count": len(evidence_list),
                "governed_count": govern_result["final_count"]
            }
        )
    
    async def cleanup(self):
        """清理资源"""
        await self.collector.close()
