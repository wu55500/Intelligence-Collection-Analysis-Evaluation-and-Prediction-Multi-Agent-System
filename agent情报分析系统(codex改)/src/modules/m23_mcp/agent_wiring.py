"""把只读逆向工具挂到仓内所有 BaseAgent 子类（ResearchAgent/AnalysisAgent）。

设计原则（只插不覆、安全降级）：
- 在各 agent 的 __init__ 末尾调 attach_reverse_tool(agent) 即可，不改既有工具与分派；
- 注册的 reverse_intel 是"懒"工具：被真正调用时才去取运行中的 M23 模块；
  MCP server 未启动 / mcp 包未安装 / 单个 server 挂掉，都返回结构化错误，
  绝不让 agent 构造或既有情报流程失败；
- 是否启用由环境变量 INTEL_M23_MCP_ENABLED 控制（默认 1 启用）。
"""
from __future__ import annotations
import os
from typing import Any, Dict

TOOL_NAME = "reverse_intel"


def _enabled() -> bool:
    return os.getenv("INTEL_M23_MCP_ENABLED", "1") not in ("0", "false", "False", "")


def attach_reverse_tool(agent) -> bool:
    """给任意具备 register_tool 的 agent 增量挂 reverse_intel。返回是否挂上。"""
    if not _enabled():
        return False
    if not hasattr(agent, "register_tool"):
        return False

    async def reverse_intel(target: str = "", question: str = "",
                            model_id: str = "", **_kw) -> Dict[str, Any]:
        # 运行时才依赖 mcp / M23，保证未启用或未安装不影响 agent
        try:
            from .integration import get_m23
            from .engine import litellm_call
        except Exception as e:  # pragma: no cover - 依赖缺失
            return {"ok": False, "error": f"M23 依赖不可用: {type(e).__name__}: {e}"}

        m = get_m23()
        if m is None:
            return {"ok": False, "error": "M23 MCP 未启动（INTEL_M23_MCP_ENABLED 或 lifespan start_m23）"}
        if not target:
            return {"ok": False, "error": "缺少 target（本地二进制路径）"}

        model = model_id or os.getenv("INTEL_M23_MODEL", "openai/gpt-4o-mini")
        prompt = f"分析目标二进制 {target}。问题：{question or '给出函数/导入/关键字符串与校验机制'}。"
        result = await m.analyze(prompt, litellm_call(model))
        return {"ok": result.get("stop_reason") == "final_answer", **result}

    agent.register_tool(TOOL_NAME, reverse_intel)
    return TOOL_NAME in getattr(agent, "tools", {})
