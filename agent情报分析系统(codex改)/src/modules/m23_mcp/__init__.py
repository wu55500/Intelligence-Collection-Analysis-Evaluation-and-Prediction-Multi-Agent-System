"""M23 MCP 工具集成模块：把外部 MCP server（含只读逆向引擎）接入情报系统。"""
from .engine import ReverseMCPModule, default_reverse_server_config, litellm_call
from .mcp_client import MCPClientManager, MCPServerConfig
from .tool_loop import MCPToolLoop

__all__ = ["ReverseMCPModule", "default_reverse_server_config", "litellm_call",
           "MCPClientManager", "MCPServerConfig", "MCPToolLoop"]
