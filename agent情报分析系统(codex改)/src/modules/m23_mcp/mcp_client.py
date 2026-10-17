"""MCP 连接管理器（M23）。

职责：
- 按配置拉起/缓存多个 MCP server（stdio 会话常驻，不在每次调用重连）；
- 聚合各 server 工具，统一命名空间 mcp__<server>__<tool>，防撞名、便于路由；
- 只读白名单：默认只放行 allowlist 中的工具（逆向 server 只给 5 个只读工具）；
- 单个 server 启动/调用失败不阻断主服务（fail-open=False：失败工具返回错误，其它照常）。

与 litellm/llm_client 解耦：这里只负责"工具从哪来、怎么调"，不决定"何时调"。
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 默认只读白名单（逆向）。其它 server 在 config 里显式给 allowlist。
DEFAULT_READONLY_ALLOWLIST: Set[str] = {
    "file_info", "list_functions", "get_imports", "get_strings", "decompile_function",
}


@dataclass
class MCPServerConfig:
    name: str
    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    cwd: Optional[str] = None
    enabled: bool = True
    allowlist: Optional[List[str]] = None  # None=用默认只读白名单；[]显式全禁


@dataclass
class ToolDescriptor:
    qualified: str          # mcp__server__tool
    server: str
    tool: str
    description: str
    input_schema: Dict[str, Any]

    def to_openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.qualified,
                "description": self.description[:1024],
                "parameters": self.input_schema or {"type": "object", "properties": {}},
            },
        }


class MCPClientManager:
    """多 server MCP 客户端管理。async with 生命周期内保持会话常驻。"""

    def __init__(self, configs: Optional[List[MCPServerConfig]] = None,
                 default_allowlist: Optional[Set[str]] = None):
        self.configs = {c.name: c for c in (configs or [])}
        self.default_allowlist = default_allowlist or DEFAULT_READONLY_ALLOWLIST
        self._ctx: Dict[str, Any] = {}       # name -> (stdio_cm, session_cm)
        self._sessions: Dict[str, ClientSession] = {}
        self._tools: Dict[str, ToolDescriptor] = {}
        self.dead_servers: Dict[str, str] = {}

    def _allowed(self, cfg: MCPServerConfig) -> Set[str]:
        if cfg.allowlist is None:
            return set(self.default_allowlist)
        return set(cfg.allowlist)

    async def start(self):
        for name, cfg in self.configs.items():
            if not cfg.enabled:
                continue
            try:
                await self._connect(cfg)
            except Exception as e:  # 单个 server 挂了不拖垮主服务
                self.dead_servers[name] = f"{type(e).__name__}: {e}"
        return self

    async def _connect(self, cfg: MCPServerConfig):
        params = StdioServerParameters(
            command=cfg.command, args=cfg.args, env=cfg.env or None, cwd=cfg.cwd)
        stdio_cm = stdio_client(params)
        read, write = await stdio_cm.__aenter__()
        session_cm = ClientSession(read, write)
        session = await session_cm.__aenter__()
        await session.initialize()
        listed = await session.list_tools()
        allowed = self._allowed(cfg)
        for t in listed.tools:
            if t.name not in allowed:
                continue
            desc = ToolDescriptor(
                qualified=f"mcp__{cfg.name}__{t.name}", server=cfg.name, tool=t.name,
                description=t.description or "", input_schema=t.inputSchema or {})
            self._tools[desc.qualified] = desc
        self._ctx[cfg.name] = (stdio_cm, session_cm)
        self._sessions[cfg.name] = session

    async def close(self):
        for name, (stdio_cm, session_cm) in list(self._ctx.items()):
            for cm in (session_cm, stdio_cm):
                try:
                    await cm.__aexit__(None, None, None)
                except Exception:
                    pass
        self._ctx.clear(); self._sessions.clear()

    async def __aenter__(self):
        await self.start(); return self

    async def __aexit__(self, *exc):
        await self.close()

    def openai_tools(self) -> List[Dict[str, Any]]:
        return [d.to_openai_schema() for d in self._tools.values()]

    def tool_names(self) -> List[str]:
        return sorted(self._tools)

    async def call_qualified(self, qualified: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """按 mcp__server__tool 路由调用；越权/不存在/死server 一律返回结构化错误。"""
        d = self._tools.get(qualified)
        if d is None:
            return {"ok": False, "error": f"工具未注册或不在只读白名单: {qualified}"}
        session = self._sessions.get(d.server)
        if session is None:
            return {"ok": False, "error": f"server 不可用: {d.server} ({self.dead_servers.get(d.server,'?')})"}
        try:
            res = await session.call_tool(d.tool, arguments or {})
            texts = []
            for c in (res.content or []):
                if getattr(c, "type", None) == "text":
                    texts.append(c.text)
            return {"ok": not res.isError, "server": d.server, "tool": d.tool,
                    "text": "\n".join(texts), "isError": bool(res.isError)}
        except Exception as e:
            return {"ok": False, "server": d.server, "tool": d.tool,
                    "error": f"{type(e).__name__}: {e}"}

    def health(self) -> Dict[str, Any]:
        return {"alive": sorted(self._sessions), "dead": self.dead_servers,
                "tools": self.tool_names()}
