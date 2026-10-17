"""从 config/mcp_servers.json（或样例）加载 MCP server 配置。"""
from __future__ import annotations
import json
from pathlib import Path
from typing import List, Optional

from .mcp_client import MCPServerConfig


def load_server_configs(path: str | Path) -> tuple[List[MCPServerConfig], str]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"MCP 配置不存在: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    backend = data.get("backend_default", "binutils")
    out = []
    for s in data.get("servers", []):
        if s.get("name", "").startswith("_"):
            continue
        env = dict(s.get("env") or {})
        if s["name"] == "reverse" and "REVERSE_BACKEND" not in env:
            env["REVERSE_BACKEND"] = backend
        out.append(MCPServerConfig(
            name=s["name"], command=s["command"], args=s.get("args", []),
            env=env, cwd=s.get("cwd"), enabled=bool(s.get("enabled", True)),
            allowlist=s.get("allowlist")))
    return out, backend
