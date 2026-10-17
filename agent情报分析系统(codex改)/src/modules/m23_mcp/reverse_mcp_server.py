"""M23 只读逆向 MCP Server（stdio）。

用官方 mcp SDK 把逆向后端的 5 个只读工具暴露给任意 MCP 客户端
（Claude Code/Cursor/本系统 m23 工具循环）。

安全：
- 只注册 list_functions/get_imports/get_strings/decompile_function/file_info；
- 不运行目标、不写内存、不下断点；路径经后端规范化、subprocess argv 化；
- 后端默认 binutils（云机可用），设 REVERSE_BACKEND=ghidra 且本地装了 Ghidra 才用 ghidra。
"""
from __future__ import annotations
import json, os

from mcp.server.fastmcp import FastMCP

from .reverse_backends import get_backend, BackendError

mcp = FastMCP("m23-reverse-readonly")
_backend = None


def backend():
    global _backend
    if _backend is None:
        _backend = get_backend(os.environ.get("REVERSE_BACKEND", "binutils"))
    return _backend


@mcp.tool()
def file_info(target: str) -> str:
    """识别二进制文件类型（ELF/PE/架构/是否stripped）。只读，不执行目标。target: 二进制路径"""
    try:
        return json.dumps(backend().file_info(target).to_dict(), ensure_ascii=False)
    except BackendError as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@mcp.tool()
def list_functions(target: str) -> str:
    """列出已定义函数及入口地址（带地址证据）。stripped程序可能很少。target: 二进制路径"""
    try:
        return json.dumps(backend().list_functions(target).to_dict(), ensure_ascii=False)
    except BackendError as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@mcp.tool()
def get_imports(target: str) -> str:
    """列出动态导入/未定义符号，用于推断程序行为（如WSAStartup/VirtualAlloc）。target: 二进制路径"""
    try:
        return json.dumps(backend().get_imports(target).to_dict(), ensure_ascii=False)
    except BackendError as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@mcp.tool()
def get_strings(target: str, min_len: int = 4) -> str:
    """提取可打印字符串及文件内偏移。target: 二进制路径；min_len: 最短长度(>=4)"""
    try:
        return json.dumps(backend().get_strings(target, min_len).to_dict(), ensure_ascii=False)
    except BackendError as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@mcp.tool()
def decompile_function(target: str, function: str) -> str:
    """反汇编/反编译指定函数。binutils给带地址汇编，ghidra后端给伪C。target路径 + function函数名"""
    try:
        return json.dumps(backend().decompile_function(target, function).to_dict(), ensure_ascii=False)
    except BackendError as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
