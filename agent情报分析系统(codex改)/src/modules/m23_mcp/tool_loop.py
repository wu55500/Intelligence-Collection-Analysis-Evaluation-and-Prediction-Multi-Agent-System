"""M23 工具调用循环：让模型自己决定调哪个 MCP 工具，直到给出最终答案。

这是原 BaseAgent 缺失的一环（原本是按子任务 type 写死分派）。
设计：
- llm_call 可注入：生产传 UnifiedLLMClient.complete 的适配，测试传脚本化桩，
  因此整条循环无需真实 API key 即可端到端验证；
- 工具只来自 MCPClientManager 的只读白名单，名字 mcp__server__tool；
- 每次调用记 trace（谁、参数、ok、证据摘要），满足"每步留痕/证据可追溯"；
- max_iterations 硬上限防失控；模型不再返回 tool_calls 即终止。
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .mcp_client import MCPClientManager

# llm_call(messages, tools) -> {"content": str, "tool_calls": [{"id","function":{"name","arguments"}}]}
LLMCall = Callable[[List[Dict[str, Any]], List[Dict[str, Any]]],
                   Dict[str, Any]]

SYSTEM_PROMPT = (
    "你是受控逆向分析助手。只能调用给定的只读逆向工具，禁止臆测二进制内容。"
    "每条机制结论必须来自工具返回的地址/证据；区分'直接观察'与'推断'；"
    "至少考虑一个替代解释。无法从证据得出就明确说'证据不足'。"
    "拿到足够证据后，用中文给出结论+证据地址列表，不再调用工具。"
)


@dataclass
class LoopResult:
    final_answer: str
    iterations: int
    stop_reason: str
    trace: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"final_answer": self.final_answer, "iterations": self.iterations,
                "stop_reason": self.stop_reason, "trace": self.trace}


class MCPToolLoop:
    def __init__(self, manager: MCPClientManager, llm_call: LLMCall,
                 max_iterations: int = 12, system_prompt: str = SYSTEM_PROMPT):
        self.mgr = manager
        self.llm_call = llm_call
        self.max_iterations = max_iterations
        self.system_prompt = system_prompt

    async def run(self, user_prompt: str) -> LoopResult:
        tools = self.mgr.openai_tools()
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        trace: List[Dict[str, Any]] = []

        for it in range(1, self.max_iterations + 1):
            resp = await self.llm_call(messages, tools)
            calls = resp.get("tool_calls") or []

            if not calls:
                return LoopResult(resp.get("content", ""), it, "final_answer", trace)

            for call in calls:
                name = call["function"]["name"]
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = await self.mgr.call_qualified(name, args)
                text = result.get("text") or result.get("error") or json.dumps(result, ensure_ascii=False)
                # trace 保留完整工具输出以满足证据可复核（QC-RE07）；喂给模型仍截断防上下文膨胀
                trace.append({"iter": it, "tool": name, "args": args,
                              "ok": result.get("ok", False),
                              "evidence_head": text[:300],
                              "raw_result": text})
                messages.append({"role": "assistant", "content": None,
                                 "tool_calls": [{"id": call.get("id", f"c{it}"),
                                                 "type": "function",
                                                 "function": {"name": name,
                                                              "arguments": json.dumps(args, ensure_ascii=False)}}]})
                messages.append({"role": "tool", "tool_call_id": call.get("id", f"c{it}"),
                                 "content": text[:8000]})

        return LoopResult("达到最大迭代次数，强制终止（未获最终结论）", self.max_iterations,
                          "max_iterations", trace)
