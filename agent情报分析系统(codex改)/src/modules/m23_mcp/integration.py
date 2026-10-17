"""M23 与主系统的"只插不覆"集成层。

原则（对齐主人要求：不破坏现有 m1-m21 / BaseAgent 字典分派）：
- 不改 base_agent.py 的 _execute_sub_task；这里只提供一个 register 助手，
  把 type='reverse_intel' 的协程注册进 agent.tools，天然复用现有分派；
- 不改 main.py 主体；提供 m23_lifespan 钩子与 create_m23_router()，
  在用户自己的 main.py 里用两行接入（见 docs 与文件尾注释）；
- 单个 MCP server 挂掉只在 health 里标 dead，不影响 FastAPI 启动。
"""
from __future__ import annotations
import json
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import APIRouter

from .engine import ReverseMCPModule, default_reverse_server_config
from .mcp_client import MCPServerConfig

_module: Optional[ReverseMCPModule] = None


async def start_m23(configs=None, backend: str = "binutils") -> ReverseMCPModule:
    global _module
    await stop_m23()
    _module = ReverseMCPModule()
    await _module.configure_and_start(configs=configs, backend=backend)
    return _module


async def stop_m23():
    global _module
    if _module is not None:
        try:
            await _module.close()
        except Exception:
            pass
    _module = None


def get_m23() -> Optional[ReverseMCPModule]:
    return _module


async def register_reverse_tool(agent, model_id: str = "") -> bool:
    """把 reverse_intel 工具挂到任意 BaseAgent 子类实例上（增量，不覆盖其它工具）。

    agent 需已有 register_tool(name, coro)（BaseAgent 已具备）。
    """
    m = _module
    if m is None:
        return False

    async def reverse_intel(target: str = "", question: str = "", **_kw):
        from .engine import litellm_call
        model = model_id or "openai/gpt-4o-mini"
        if not target:
            return {"error": "缺少 target"}
        prompt = f"分析目标二进制 {target}。问题：{question or '给出函数/导入/关键字符串与校验机制'}。"
        return await m.analyze(prompt, litellm_call(model))

    agent.register_tool("reverse_intel", reverse_intel)
    return "reverse_intel" in agent.tools


@asynccontextmanager
async def m23_lifespan(app, configs=None, backend: str = "binutils"):
    """可与现有 lifespan 组合：with m23_lifespan(app): ... 或在其中 await start/stop。"""
    await start_m23(configs=configs, backend=backend)
    try:
        yield
    finally:
        await stop_m23()


def create_m23_router() -> APIRouter:
    router = APIRouter(prefix="/mcp", tags=["m23-mcp"])

    @router.get("/health")
    async def health():
        m = get_m23()
        if m is None:
            return {"status": "not_started"}
        h = m.health()
        return {"status": "running" if h["alive"] else "degraded", **h}

    @router.get("/tools")
    async def tools():
        m = get_m23()
        return {"tools": m.list_tools() if m else []}

    @router.post("/analyze")
    async def analyze(body: Dict[str, Any]):
        m = get_m23()
        if m is None:
            return {"ok": False, "error": "M23 未启动"}
        target = body.get("target", "")
        question = body.get("question", "")
        model_id = body.get("model_id", "")
        from .engine import litellm_call
        prompt = f"分析目标二进制 {target}。问题：{question}。"
        result = await m.analyze(prompt, litellm_call(model_id or "openai/gpt-4o-mini"),
                                 max_iterations=int(body.get("max_iterations", 12)))
        return {"ok": result["stop_reason"] == "final_answer", **result}

    return router


# ── 接入现有 src/api/main.py 的最小 diff（可选，默认不改）──────────────
# 1) 顶部:  from ..modules.m23_mcp.integration import start_m23, stop_m23, create_m23_router
# 2) lifespan 内 yield 前: await start_m23(backend="binutils")
#    yield 后:              await stop_m23()
# 3) app 建完:  app.include_router(create_m23_router())
# 4) 某 agent 上挂工具:  await register_reverse_tool(agent, model_id="...")
