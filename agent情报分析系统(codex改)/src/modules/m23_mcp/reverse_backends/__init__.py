"""M23 逆向引擎后端（可插拔）。

- binutils：云机/服务器无 GUI 默认可用（objdump/nm/readelf/strings/file），
  只做只读静态分析，输出带地址证据；无需安装重型工具。
- ghidra ：本地有 Ghidra + analyzeHeadless/JDK 时启用，额外产出伪 C。
通过 get_backend(name) 选择；所有后端只暴露只读操作，不运行目标、不改目标。
"""
from .binutils_backend import BinutilsBackend
from .base import BackendError

__all__ = ["BinutilsBackend", "BackendError", "get_backend"]


def get_backend(name: str = "binutils", **kw):
    name = (name or "binutils").lower()
    if name == "binutils":
        return BinutilsBackend(**kw)
    if name == "ghidra":
        from .ghidra_backend import GhidraBackend  # 延迟导入，缺环境不影响默认链路
        return GhidraBackend(**kw)
    raise BackendError(f"未知逆向后端: {name}（支持 binutils / ghidra）")
