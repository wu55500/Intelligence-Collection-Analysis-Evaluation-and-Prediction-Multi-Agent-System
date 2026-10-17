"""M23 MCP 逆向情报模块（engine，对齐 m1-m21 的 engine.py 规范）。

对外主类 ReverseMCPModule：
- configure(configs): 注册 MCP server（默认含本地只读逆向 server）
- start/close 生命周期；list_tools/health 探针
- analyze(prompt, llm_call): 跑工具调用循环，返回带证据 trace 的结论
- as_agent_tool(): 产出可挂到 BaseAgent.register_tool 的协程

默认 server 用本模块自带 reverse_mcp_server（stdio 子进程），
后端 binutils 云机可用、本地可切 ghidra（REVERSE_BACKEND=ghidra）。
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .mcp_client import MCPClientManager, MCPServerConfig
from .tool_loop import MCPToolLoop, LoopResult

_HERE = Path(__file__).resolve().parent
_PKG_ROOT = _HERE.parent.parent  # src/


def default_reverse_server_config(backend: str = "binutils") -> MCPServerConfig:
    """拉起本模块自带的只读逆向 MCP server（python -m）。"""
    return MCPServerConfig(
        name="reverse",
        command=sys.executable,
        args=["-m", "modules.m23_mcp.reverse_mcp_server"],
        cwd=str(_PKG_ROOT),
        env={"PYTHONPATH": str(_PKG_ROOT), "REVERSE_BACKEND": backend},
        enabled=True,
        allowlist=None,  # 用默认只读白名单
    )


def litellm_call(model_id: str) -> Callable:
    """生产用 llm_call 适配：桥到现有 UnifiedLLMClient.complete（tools 已支持）。"""
    async def _call(messages, tools):
        from ...agents.router.llm_client import UnifiedLLMClient
        client = UnifiedLLMClient()
        resp = await client.complete(model_id=model_id, messages=messages, tools=tools)
        return {"content": resp.content, "tool_calls": resp.tool_calls}
    return _call


class ReverseMCPModule:
    def __init__(self):
        self.manager: Optional[MCPClientManager] = None
        self.started = False

    async def configure_and_start(self, configs: Optional[List[MCPServerConfig]] = None,
                                  backend: str = "binutils") -> "ReverseMCPModule":
        cfgs = configs if configs is not None else [default_reverse_server_config(backend)]
        self.manager = MCPClientManager(cfgs)
        await self.manager.start()
        self.started = True
        return self

    async def close(self):
        if self.manager:
            await self.manager.close()
        self.started = False

    def health(self) -> Dict[str, Any]:
        return self.manager.health() if self.manager else {"alive": [], "dead": {}, "tools": []}

    def list_tools(self) -> List[str]:
        return self.manager.tool_names() if self.manager else []

    async def analyze(self, prompt: str, llm_call: Callable,
                      max_iterations: int = 12) -> Dict[str, Any]:
        if not self.manager:
            raise RuntimeError("M23 未启动，请先 configure_and_start()")
        loop = MCPToolLoop(self.manager, llm_call, max_iterations=max_iterations)
        result: LoopResult = await loop.run(prompt)
        return result.to_dict()

    async def as_agent_tool(self):
        """供 BaseAgent.register_tool 使用：type='reverse_intel'。

        约定子任务：{"type":"reverse_intel","target":"<二进制路径>","question":"..."}
        需要调用方注入 llm_call（这里默认 litellm，模型可用环境 INTEL_... 或改这里）。
        """
        async def _tool(target: str = "", question: str = "", model_id: str = "", **_kw):
            if not target:
                return {"error": "缺少 target"}
            model = model_id or "openai/gpt-4o-mini"
            prompt = f"分析目标二进制 {target}。问题：{question or '给出函数、导入、关键字符串与机制'}。"
            return await self.analyze(prompt, litellm_call(model))
        return _tool
