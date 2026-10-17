"""逆向后端契约与安全约束。"""
from dataclasses import dataclass, field
from typing import List, Dict, Any

# 只读白名单：M23 默认只允许这些操作。任何写内存/运行样本/下断的动作都不进白名单。
READONLY_TOOLS = {"list_functions", "get_imports", "get_strings", "decompile_function", "file_info"}


class BackendError(RuntimeError):
    pass


@dataclass
class Evidence:
    """每条发现必须可定位：函数名/地址 + 原始工具 + 证据片段。"""
    claim: str
    location: str
    source_tool: str
    raw: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"claim": self.claim, "location": self.location,
                "source_tool": self.source_tool, "raw": self.raw}


@dataclass
class ReverseResult:
    ok: bool
    tool: str
    target: str
    engine: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    error: str = ""
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "tool": self.tool, "target": self.target,
                "engine": self.engine, "evidence": self.evidence,
                "error": self.error, "note": self.note}
