"""全 agent 装载验证：ResearchAgent/AnalysisAgent 均增量获得 reverse_intel，
未启动 M23 时安全降级；启动后经真实 stdio server 出证据；开关关闭则不挂载。"""
import asyncio, json, logging, os
import pytest
logging.disable(logging.INFO)

from src.agents.research_agent import ResearchAgent
from src.agents.analysis_agent import AnalysisAgent
from src.modules.m23_mcp import integration
from src.modules.m23_mcp import engine as eng



class StubLLM:
    def __init__(self, target): self.target = target; self.n = 0
    async def __call__(self, messages, tools):
        self.n += 1
        if self.n == 1:
            return {"content": None, "tool_calls": [
                {"id": "1", "function": {"name": "mcp__reverse__get_strings",
                                         "arguments": json.dumps({"target": self.target})}}]}
        return {"content": "结论：发现 SECRET@0x2010。", "tool_calls": []}


def test_both_agents_have_tool():
    for ag in (ResearchAgent(), AnalysisAgent()):
        assert "reverse_intel" in ag.tools


@pytest.mark.asyncio
async def test_safe_degrade_when_not_started(crackme_bin):
    TARGET = crackme_bin
    await integration.stop_m23()
    r = ResearchAgent()
    out = await r.tools["reverse_intel"](target=TARGET, question="x")
    assert out["ok"] is False and "未启动" in out["error"]


@pytest.mark.asyncio
async def test_missing_target_guarded(crackme_bin):
    TARGET = crackme_bin
    await integration.start_m23(backend="binutils")
    try:
        a = AnalysisAgent()
        out = await a.tools["reverse_intel"](question="x")
        assert out["ok"] is False and "target" in out["error"]
    finally:
        await integration.stop_m23()


@pytest.mark.asyncio
async def test_live_reverse_through_agent(monkeypatch, crackme_bin):
    TARGET = crackme_bin
    # 用桩 llm 替换 litellm_call，避免真实 API key，但走的是真实 stdio 逆向 server
    stub = StubLLM(TARGET)  # 必须持久实例，保持轮次状态
    monkeypatch.setattr(eng, "litellm_call",
                        lambda model_id="": (lambda messages, tools: stub(messages, tools)))
    await integration.start_m23(backend="binutils")
    try:
        r = ResearchAgent()
        out = await r.tools["reverse_intel"](target=TARGET, question="找关键字符串")
        assert out["ok"] is True
        blob = json.dumps(out, ensure_ascii=False)
        assert "REA-MCP-LAB-2026" in blob and "0x2010" in blob
    finally:
        await integration.stop_m23()


def test_disable_switch(monkeypatch):
    monkeypatch.setenv("INTEL_M23_MCP_ENABLED", "0")
    import importlib, src.modules.m23_mcp.agent_wiring as w
    importlib.reload(w)
    assert w.attach_reverse_tool(ResearchAgent()) is False
