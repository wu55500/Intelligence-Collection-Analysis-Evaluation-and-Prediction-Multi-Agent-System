"""
统一 LLM 调用客户端
通过 litellm 统一调用不同 provider 的模型
"""

import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json


@dataclass
class LLMResponse:
    """统一响应格式"""
    content: str
    model_id: str
    provider: str
    usage: Dict[str, Any]
    finish_reason: str = "stop"
    tool_calls: Optional[List[Dict]] = None
    raw_response: Optional[Dict] = None


class UnifiedLLMClient:
    """
    统一 LLM 客户端
    
    通过 litellm 统一调用：
    - OpenAI: gpt-4o, o1, gpt-4o-mini
    - Anthropic: claude-3.5-sonnet, claude-3-opus
    - Google: gemini-1.5-pro, gemini-1.5-flash
    - DeepSeek: deepseek-v3
    - Perplexity: sonar
    - 本地: ollama, vllm
    """
    
    def __init__(self):
        self._available_providers = self._check_providers()
    
    def _check_providers(self) -> Dict[str, bool]:
        """检查哪些 provider 可用"""
        providers = {
            "openai": bool(os.environ.get("OPENAI_API_KEY")),
            "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "google": bool(os.environ.get("GOOGLE_API_KEY")),
            "deepseek": bool(os.environ.get("DEEPSEEK_API_KEY")),
            "perplexity": bool(os.environ.get("PERPLEXITY_API_KEY")),
            "local": True  # 本地模型始终可用
        }
        return providers
    
    async def complete(
        self,
        model_id: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        tools: Optional[List[Dict]] = None,
        stream: bool = False
    ) -> LLMResponse:
        """
        统一调用接口
        
        model_id 格式：provider/model_name
        例如：openai/gpt-4o, anthropic/claude-3.5-sonnet
        """
        provider, model_name = self._parse_model_id(model_id)
        
        if not self._available_providers.get(provider):
            raise ValueError(f"Provider {provider} 未配置 API Key")
        
        try:
            import litellm
            
            params = {
                "model": model_id,  # litellm 格式：provider/model
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            
            if tools and provider not in ["perplexity"]:
                params["tools"] = tools
            
            response = await litellm.acompletion(**params)
            
            content = response.choices[0].message.content or ""
            tool_calls = None
            if hasattr(response.choices[0].message, "tool_calls"):
                tool_calls = [
                    {
                        "id": tc.id,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in response.choices[0].message.tool_calls
                ] if response.choices[0].message.tool_calls else None
            
            return LLMResponse(
                content=content,
                model_id=model_id,
                provider=provider,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                    "cost": getattr(response.usage, "cost", None)
                },
                finish_reason=response.choices[0].finish_reason,
                tool_calls=tool_calls,
                raw_response=response.model_dump() if hasattr(response, "model_dump") else None
            )
        
        except ImportError:
            # litellm 未安装，使用模拟
            return LLMResponse(
                content=f"[模拟] {model_id} 响应: 处理完成",
                model_id=model_id,
                provider=provider,
                usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
            )
    
    async def complete_json(
        self,
        model_id: str,
        messages: List[Dict[str, str]],
        response_schema: Optional[Dict] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """调用并解析 JSON 响应"""
        response = await self.complete(model_id, messages, **kwargs)
        
        try:
            # 尝试从 content 提取 JSON
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            return json.loads(content.strip())
        except (json.JSONDecodeError, IndexError):
            return {"raw": response.content, "parse_error": True}
    
    def _parse_model_id(self, model_id: str) -> tuple:
        """解析 model_id"""
        if "/" in model_id:
            parts = model_id.split("/", 1)
            return parts[0], parts[1]
        return "openai", model_id
    
    def is_provider_available(self, provider: str) -> bool:
        """检查 provider 是否可用"""
        return self._available_providers.get(provider, False)
    
    def get_available_providers(self) -> List[str]:
        """获取可用 provider 列表"""
        return [p for p, available in self._available_providers.items() if available]
