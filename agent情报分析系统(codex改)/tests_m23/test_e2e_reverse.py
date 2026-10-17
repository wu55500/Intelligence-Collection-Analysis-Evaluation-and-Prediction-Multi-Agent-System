"""M23 端到端 pytest：脚本化桩 LLM（零 API key）驱动真实工具循环，
经 stdio 拉起 reverse_mcp_server 真分析 lab/crackme。
断言带地址证据：SECRET 串、XOR key 0x5a、puts 导入、check_key 反汇编；
另测 server 启动失败不阻断、非白名单工具被拒。
"""
import json, os, logging
import pytest

logging.getLogger("mcp").setLevel(logging.ERROR)
logging.disable(logging.INFO)

from src.modules.m23_mcp import ReverseMCPModule
from src.modules.m23_mcp.mcp_client import MCPClientManager, MCPServerConfig



class StubLLM:
    """状态机：轮1并行侦察→轮2反汇编 check_key→轮3给结论。"""
    def __init__(self, target):
        self.target = target; self.n = 0
    async def __call__(self, messages, tools):
        self.n += 1
        def tc(i, fn, args):
            return {"id": f"c{i}", "function": {"name": fn, "arguments": json.dumps(args)}}
        if self.n == 1:
            return {"content": None, "tool_calls": [
                tc(1, "mcp__reverse__file_info", {"target": self.target}),
                tc(2, "mcp__reverse__list_functions", {"target": self.target}),
                tc(3, "mcp__reverse__get_strings", {"target": self.target}),
                tc(4, "mcp__reverse__get_imports", {"target": self.target})]}
        if self.n == 2:
            blob = "\n".join(m.get("content") or "" for m in messages if m.get("role") == "tool")
            fname = "check_key" if "check_key" in blob else "main"
            return {"content": None, "tool_calls": [
                tc(5, "mcp__reverse__decompile_function",
                   {"target": self.target, "function": fname})]}
        return {"content": "结论：check_key 用初值0x5a滚动XOR比对 SECRET@0x2010。",
                "tool_calls": []}


@pytest.mark.asyncio
async def test_reverse_evidence_chain(crackme_bin):
    TARGET = crackme_bin
    mod = ReverseMCPModule()
    await mod.configure_and_start(backend="binutils")
    try:
        names = mod.list_tools()
        assert len(names) == 5
        readonly = {"file_info", "list_functions", "get_imports",
                    "get_strings", "decompile_function"}
        assert all(x.split("__")[-1] in readonly for x in names)

        out = await mod.analyze(
            f"分析 {TARGET}：找出校验密钥与关键字符串机制。",
            StubLLM(TARGET), max_iterations=6)
        assert out["stop_reason"] == "final_answer"
        assert out["iterations"] == 3
        # 反汇编完整返回含 XOR 初值 0x5a（不依赖300字符日志截断）
        dis = await mod.manager.call_qualified(
            "mcp__reverse__decompile_function",
            {"target": TARGET, "function": "check_key"})
        assert dis["ok"] and "0x5a" in dis["text"]

        # 字符串带真实地址（SECRET @0x2010）——直接校验工具完整返回
        st = await mod.manager.call_qualified(
            "mcp__reverse__get_strings", {"target": TARGET})
        assert st["ok"]
        stext = st["text"]
        assert "REA-MCP-LAB-2026" in stext and "0x2010" in stext

        imp = await mod.manager.call_qualified(
            "mcp__reverse__get_imports", {"target": TARGET})
        assert imp["ok"] and any(x in imp["text"] for x in ["puts", "printf"])

        dis = [t for t in out["trace"] if t["tool"].endswith("decompile_function")]
        assert dis and dis[0]["ok"]

        # 非白名单 / 未注册工具一律拒绝
        assert (await mod.manager.call_qualified("mcp__reverse__write_memory", {}))["ok"] is False
        assert (await mod.manager.call_qualified("mcp__evil__rm_rf", {}))["ok"] is False
    finally:
        await mod.close()


@pytest.mark.asyncio
async def test_dead_server_does_not_block():
    bad = MCPClientManager([MCPServerConfig(name="broken", command="/nonexistent/xyz")])
    await bad.start()
    try:
        assert "broken" in bad.dead_servers
        assert bad.openai_tools() == []
    finally:
        await bad.close()
