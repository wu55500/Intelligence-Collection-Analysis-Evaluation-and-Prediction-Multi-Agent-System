"""
模型注册表 - 记录各模型的能力和适用场景
不同功能模块自动路由到最擅长的模型
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class Capability(str, Enum):
    """模型能力维度"""
    REASONING = "reasoning"           # 逻辑推理
    MATH = "math"                     # 数值计算
    CODING = "coding"                 # 代码生成
    WRITING = "writing"               # 文本写作
    SEARCH = "search"                 # 搜索检索
    NER = "ner"                       # 实体识别
    VISION = "vision"                 # 图像理解
    TOOL_USE = "tool_use"             # 工具调用
    LONG_CONTEXT = "long_context"     # 长上下文
    MULTILINGUAL = "multilingual"     # 多语言
    SPEED = "speed"                   # 速度
    COST_EFFICIENCY = "cost"          # 成本效率


class TaskType(str, Enum):
    """任务类型"""
    RESEARCH = "research"             # 研究采集
    ANALYSIS = "analysis"             # 数据分析
    FORECAST = "forecast"             # 预测登记
    CAUSAL_REVIEW = "causal_review"   # 因果审查
    REPORT = "report"                 # 报告生成
    EVIDENCE_EVAL = "evidence_eval"   # 证据评估
    KNOWLEDGE_GRAPH = "knowledge_graph"  # 知识图谱
    NER_EXTRACTION = "ner_extraction" # 实体抽取
    CODE_GENERATION = "code"          # 代码生成
    SUMMARIZATION = "summary"         # 摘要压缩
    TRANSLATION = "translation"       # 翻译
    GENERAL = "general"               # 通用对话


@dataclass
class ModelProfile:
    """模型能力档案"""
    model_id: str                    # 唯一标识
    provider: str                    # openai, anthropic, google, local
    model_name: str                  # 显示名称
    capabilities: Dict[Capability, float] = field(default_factory=dict)  # 0-1能力分数
    max_context_tokens: int = 128000
    cost_per_1k_tokens: float = 0.01  # 美元
    avg_latency_ms: int = 2000
    supports_tools: bool = True
    supports_vision: bool = False
    supports_streaming: bool = True
    is_available: bool = True
    notes: str = ""


class ModelRegistry:
    """
    模型注册表
    
    记录所有可用模型的能力画像
    """
    
    def __init__(self):
        self._models: Dict[str, ModelProfile] = {}
        self._register_default_models()
    
    def register(self, profile: ModelProfile):
        """注册模型"""
        self._models[profile.model_id] = profile
    
    def get(self, model_id: str) -> Optional[ModelProfile]:
        """获取模型信息"""
        return self._models.get(model_id)
    
    def list_models(self, provider: Optional[str] = None) -> List[ModelProfile]:
        """列出模型"""
        models = list(self._models.values())
        if provider:
            models = [m for m in models if m.provider == provider]
        return [m for m in models if m.is_available]
    
    def find_best_for_task(self, task_type: TaskType, 
                          exclude: List[str] = None,
                          max_cost: Optional[float] = None) -> Optional[ModelProfile]:
        """根据任务类型找最佳模型"""
        exclude = exclude or []
        
        # 任务类型 → 关键能力映射
        task_capability_map = {
            TaskType.RESEARCH: [
                (Capability.SEARCH, 0.35),
                (Capability.REASONING, 0.25),
                (Capability.MULTILINGUAL, 0.20),
                (Capability.LONG_CONTEXT, 0.20)
            ],
            TaskType.ANALYSIS: [
                (Capability.REASONING, 0.35),
                (Capability.MATH, 0.30),
                (Capability.CODING, 0.20),
                (Capability.LONG_CONTEXT, 0.15)
            ],
            TaskType.FORECAST: [
                (Capability.MATH, 0.35),
                (Capability.REASONING, 0.35),
                (Capability.LONG_CONTEXT, 0.15),
                (Capability.SPEED, 0.15)
            ],
            TaskType.CAUSAL_REVIEW: [
                (Capability.REASONING, 0.45),
                (Capability.MATH, 0.25),
                (Capability.LONG_CONTEXT, 0.15),
                (Capability.CODING, 0.15)
            ],
            TaskType.REPORT: [
                (Capability.WRITING, 0.35),
                (Capability.REASONING, 0.25),
                (Capability.LONG_CONTEXT, 0.20),
                (Capability.MULTILINGUAL, 0.20)
            ],
            TaskType.EVIDENCE_EVAL: [
                (Capability.REASONING, 0.40),
                (Capability.LONG_CONTEXT, 0.25),
                (Capability.MATH, 0.20),
                (Capability.SEARCH, 0.15)
            ],
            TaskType.KNOWLEDGE_GRAPH: [
                (Capability.NER, 0.35),
                (Capability.REASONING, 0.25),
                (Capability.LONG_CONTEXT, 0.20),
                (Capability.TOOL_USE, 0.20)
            ],
            TaskType.NER_EXTRACTION: [
                (Capability.NER, 0.50),
                (Capability.REASONING, 0.20),
                (Capability.SPEED, 0.15),
                (Capability.COST_EFFICIENCY, 0.15)
            ],
            TaskType.CODE_GENERATION: [
                (Capability.CODING, 0.50),
                (Capability.REASONING, 0.25),
                (Capability.TOOL_USE, 0.15),
                (Capability.SPEED, 0.10)
            ],
            TaskType.SUMMARIZATION: [
                (Capability.WRITING, 0.35),
                (Capability.LONG_CONTEXT, 0.30),
                (Capability.SPEED, 0.20),
                (Capability.COST_EFFICIENCY, 0.15)
            ],
            TaskType.TRANSLATION: [
                (Capability.MULTILINGUAL, 0.50),
                (Capability.WRITING, 0.25),
                (Capability.SPEED, 0.15),
                (Capability.COST_EFFICIENCY, 0.10)
            ],
            TaskType.GENERAL: [
                (Capability.REASONING, 0.30),
                (Capability.WRITING, 0.25),
                (Capability.SPEED, 0.20),
                (Capability.COST_EFFICIENCY, 0.25)
            ]
        }
        
        weights = task_capability_map.get(task_type, [(Capability.REASONING, 1.0)])
        
        best_score = -1
        best_model = None
        
        for model_id, model in self._models.items():
            if not model.is_available or model_id in exclude:
                continue
            if max_cost and model.cost_per_1k_tokens > max_cost:
                continue
            
            score = sum(
                model.capabilities.get(cap, 0) * weight
                for cap, weight in weights
            )
            
            if score > best_score:
                best_score = score
                best_model = model
        
        return best_model
    
    def _register_default_models(self):
        """注册默认的前沿模型"""
        
        # OpenAI 系列
        self.register(ModelProfile(
            model_id="openai_gpt4o",
            provider="openai",
            model_name="GPT-4o",
            capabilities={
                Capability.REASONING: 0.92,
                Capability.MATH: 0.88,
                Capability.WRITING: 0.90,
                Capability.CODING: 0.90,
                Capability.SEARCH: 0.70,
                Capability.NER: 0.85,
                Capability.TOOL_USE: 0.95,
                Capability.LONG_CONTEXT: 0.80,
                Capability.MULTILINGUAL: 0.88,
                Capability.VISION: 0.90,
                Capability.SPEED: 0.75,
                Capability.COST_EFFICIENCY: 0.50
            },
            max_context_tokens=128000,
            cost_per_1k_tokens=0.01,
            avg_latency_ms=2500,
            supports_vision=True,
            notes="全能型，工具调用最强"
        ))
        
        self.register(ModelProfile(
            model_id="openai_o1",
            provider="openai",
            model_name="o1 (Reasoning)",
            capabilities={
                Capability.REASONING: 0.97,
                Capability.MATH: 0.95,
                Capability.CODING: 0.92,
                Capability.WRITING: 0.80,
                Capability.NER: 0.80,
                Capability.LONG_CONTEXT: 0.85,
                Capability.TOOL_USE: 0.70,
                Capability.SPEED: 0.30,
                Capability.COST_EFFICIENCY: 0.25
            },
            max_context_tokens=200000,
            cost_per_1k_tokens=0.06,
            avg_latency_ms=15000,
            notes="深度推理最强，适合因果分析和预测"
        ))
        
        self.register(ModelProfile(
            model_id="openai_gpt4o_mini",
            provider="openai",
            model_name="GPT-4o-mini",
            capabilities={
                Capability.REASONING: 0.78,
                Capability.MATH: 0.72,
                Capability.WRITING: 0.75,
                Capability.CODING: 0.78,
                Capability.SEARCH: 0.60,
                Capability.NER: 0.72,
                Capability.TOOL_USE: 0.85,
                Capability.LONG_CONTEXT: 0.70,
                Capability.MULTILINGUAL: 0.75,
                Capability.SPEED: 0.90,
                Capability.COST_EFFICIENCY: 0.90
            },
            max_context_tokens=128000,
            cost_per_1k_tokens=0.001,
            avg_latency_ms=800,
            notes="快速便宜，适合批量NER和摘要"
        ))
        
        # Anthropic Claude 系列
        self.register(ModelProfile(
            model_id="anthropic_claude_sonnet",
            provider="anthropic",
            model_name="Claude 3.5 Sonnet",
            capabilities={
                Capability.REASONING: 0.93,
                Capability.MATH: 0.85,
                Capability.WRITING: 0.95,
                Capability.CODING: 0.93,
                Capability.NER: 0.88,
                Capability.TOOL_USE: 0.92,
                Capability.LONG_CONTEXT: 0.95,
                Capability.MULTILINGUAL: 0.85,
                Capability.SPEED: 0.70,
                Capability.COST_EFFICIENCY: 0.65
            },
            max_context_tokens=200000,
            cost_per_1k_tokens=0.006,
            avg_latency_ms=2000,
            notes="写作和长文本最强，报告生成首选"
        ))
        
        self.register(ModelProfile(
            model_id="anthropic_claude_opus",
            provider="anthropic",
            model_name="Claude 3 Opus",
            capabilities={
                Capability.REASONING: 0.95,
                Capability.MATH: 0.88,
                Capability.WRITING: 0.93,
                Capability.CODING: 0.90,
                Capability.NER: 0.90,
                Capability.TOOL_USE: 0.88,
                Capability.LONG_CONTEXT: 0.95,
                Capability.MULTILINGUAL: 0.88,
                Capability.SPEED: 0.40,
                Capability.COST_EFFICIENCY: 0.30
            },
            max_context_tokens=200000,
            cost_per_1k_tokens=0.03,
            avg_latency_ms=5000,
            notes="最强综合推理，适合复杂因果分析"
        ))
        
        # Google Gemini 系列
        self.register(ModelProfile(
            model_id="google_gemini_pro",
            provider="google",
            model_name="Gemini 1.5 Pro",
            capabilities={
                Capability.REASONING: 0.88,
                Capability.MATH: 0.85,
                Capability.WRITING: 0.82,
                Capability.CODING: 0.85,
                Capability.SEARCH: 0.80,
                Capability.NER: 0.82,
                Capability.TOOL_USE: 0.85,
                Capability.LONG_CONTEXT: 0.98,
                Capability.MULTILINGUAL: 0.90,
                Capability.VISION: 0.88,
                Capability.SPEED: 0.65,
                Capability.COST_EFFICIENCY: 0.60
            },
            max_context_tokens=1000000,
            cost_per_1k_tokens=0.005,
            avg_latency_ms=3000,
            supports_vision=True,
            notes="超长上下文王者，百万token，多模态强"
        ))
        
        self.register(ModelProfile(
            model_id="google_gemini_flash",
            provider="google",
            model_name="Gemini 1.5 Flash",
            capabilities={
                Capability.REASONING: 0.75,
                Capability.MATH: 0.72,
                Capability.WRITING: 0.70,
                Capability.CODING: 0.75,
                Capability.SEARCH: 0.70,
                Capability.NER: 0.75,
                Capability.TOOL_USE: 0.78,
                Capability.LONG_CONTEXT: 0.95,
                Capability.MULTILINGUAL: 0.80,
                Capability.SPEED: 0.95,
                Capability.COST_EFFICIENCY: 0.92
            },
            max_context_tokens=1000000,
            cost_per_1k_tokens=0.0005,
            avg_latency_ms=500,
            notes="极快极便宜，百万上下文，批量处理首选"
        ))
        
        # DeepSeek
        self.register(ModelProfile(
            model_id="deepseek_v3",
            provider="deepseek",
            model_name="DeepSeek V3",
            capabilities={
                Capability.REASONING: 0.85,
                Capability.MATH: 0.90,
                Capability.CODING: 0.88,
                Capability.WRITING: 0.75,
                Capability.NER: 0.78,
                Capability.TOOL_USE: 0.80,
                Capability.LONG_CONTEXT: 0.75,
                Capability.MULTILINGUAL: 0.82,
                Capability.SPEED: 0.70,
                Capability.COST_EFFICIENCY: 0.85
            },
            max_context_tokens=128000,
            cost_per_1k_tokens=0.002,
            avg_latency_ms=2000,
            notes="数学和代码强，性价比高"
        ))
        
        # Perplexity（搜索专用）
        self.register(ModelProfile(
            model_id="perplexity_sonar",
            provider="perplexity",
            model_name="Perplexity Sonar",
            capabilities={
                Capability.SEARCH: 0.98,
                Capability.REASONING: 0.75,
                Capability.WRITING: 0.72,
                Capability.MULTILINGUAL: 0.80,
                Capability.LONG_CONTEXT: 0.70,
                Capability.SPEED: 0.75,
                Capability.COST_EFFICIENCY: 0.70
            },
            max_context_tokens=128000,
            cost_per_1k_tokens=0.003,
            avg_latency_ms=3000,
            notes="实时搜索最强，数据采集首选"
        ))
        
        # 本地模型（离线可用）
        self.register(ModelProfile(
            model_id="local_qwen25_72b",
            provider="local",
            model_name="Qwen2.5-72B",
            capabilities={
                Capability.REASONING: 0.80,
                Capability.MATH: 0.78,
                Capability.WRITING: 0.75,
                Capability.CODING: 0.78,
                Capability.NER: 0.80,
                Capability.TOOL_USE: 0.70,
                Capability.LONG_CONTEXT: 0.65,
                Capability.MULTILINGUAL: 0.85,
                Capability.SPEED: 0.50,
                Capability.COST_EFFICIENCY: 0.95
            },
            max_context_tokens=32000,
            cost_per_1k_tokens=0.0,
            avg_latency_ms=5000,
            notes="本地部署，完全离线，中文能力强"
        ))
    
    def get_routing_recommendation(self, task_type: TaskType) -> Dict[str, Any]:
        """获取任务路由推荐"""
        candidates = []
        for i in range(3):
            exclude = [c["model_id"] for c in candidates]
            model = self.find_best_for_task(task_type, exclude=exclude)
            if model:
                candidates.append({
                    "rank": i + 1,
                    "model_id": model.model_id,
                    "model_name": model.model_name,
                    "provider": model.provider,
                    "reason": model.notes
                })
        
        return {
            "task_type": task_type.value,
            "recommendations": candidates
        }
