"""只读静态逆向后端（binutils/file），云机默认可用、零外部依赖。

安全设计：
- 只接受单个已存在的二进制文件绝对/相对路径，用 pathlib 规范化后做 resolve；
- 调用一律走 argv 列表（subprocess 不带 shell），杜绝命令注入；
- 只读：objdump -d / nm / readelf / strings / file，不执行目标、不写目标；
- 输出做条数/字节上限，防止超大二进制撑爆上下文。
"""
from __future__ import annotations
import os, shutil, subprocess
from pathlib import Path
from typing import List, Dict, Any

from .base import BackendError, Evidence, ReverseResult

MAX_FUNC = 200
MAX_STR = 200
MAX_DISASM_BYTES = 12000
TIMEOUT = 30


class BinutilsBackend:
    name = "binutils"

    def __init__(self, max_func: int = MAX_FUNC, max_str: int = MAX_STR,
                 max_disasm_bytes: int = MAX_DISASM_BYTES):
        self.max_func = max_func
        self.max_str = max_str
        self.max_disasm_bytes = max_disasm_bytes
        self._require()

    def _require(self):
        missing = [t for t in ("objdump", "nm", "strings", "file") if shutil.which(t) is None]
        if missing:
            raise BackendError(f"binutils 后端缺少工具: {missing}")

    def _target(self, path: str) -> Path:
        if not path or not isinstance(path, str):
            raise BackendError("缺少 target 路径")
        p = Path(path).expanduser().resolve()
        if not p.is_file():
            raise BackendError(f"目标不是可读文件: {path}")
        return p

    def _run(self, args: List[str]) -> str:
        try:
            out = subprocess.run(args, capture_output=True, text=True,
                                 timeout=TIMEOUT, check=False)
        except subprocess.TimeoutExpired:
            raise BackendError(f"命令超时: {' '.join(args[:2])}")
        # nm/readelf 对某些段会返回非零，stdout 仍可用；仅当完全无输出才报错
        if not out.stdout.strip() and out.returncode != 0:
            raise BackendError(f"命令失败: {out.stderr.strip()[:200]}")
        return out.stdout

    def file_info(self, target: str) -> ReverseResult:
        p = self._target(target)
        out = self._run(["file", "-b", str(p)])
        return ReverseResult(True, "file_info", str(p), self.name,
                             [Evidence("文件类型", "file", "file", out.strip()).to_dict()],
                             note="只做静态识别，未执行目标")

    def list_functions(self, target: str) -> ReverseResult:
        p = self._target(target)
        out = self._run(["nm", "--defined-only", str(p)])
        funcs, seen = [], set()
        for line in out.splitlines():
            parts = line.split()
            # 形如: 0000000000001169 T check_key
            if len(parts) >= 3 and parts[1] in ("T", "t", "W", "w"):
                addr, name = parts[0], parts[2]
                if name in seen:
                    continue
                seen.add(name)
                funcs.append(Evidence(f"函数 {name}", f"0x{addr} @nm", "nm", line).to_dict())
            if len(funcs) >= self.max_func:
                break
        return ReverseResult(True, "list_functions", str(p), self.name, funcs,
                             note=f"最多返回{self.max_func}个；stripped 二进制可能为空")

    def get_imports(self, target: str) -> ReverseResult:
        p = self._target(target)
        out = self._run(["nm", "-D", "--undefined-only", str(p)])
        imp, seen = [], set()
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[-1] not in seen:
                sym = parts[-1]
                seen.add(sym)
                loc = parts[0] if parts[0].startswith("0") else "dynsym"
                imp.append(Evidence(f"导入/未定义符号 {sym}", loc, "nm -D", line).to_dict())
            if len(imp) >= self.max_func:
                break
        return ReverseResult(True, "get_imports", str(p), self.name, imp,
                             note="动态导入；静态链接程序此处可能为空")

    def get_strings(self, target: str, min_len: int = 4) -> ReverseResult:
        p = self._target(target)
        out = self._run(["strings", "-t", "x", "-n", str(max(4, int(min_len))), str(p)])
        ev, n = [], 0
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            off, _, text = line.partition(" ")
            ev.append(Evidence(f"字符串 {text.strip()!r}", f"0x{off} @strings", "strings", line).to_dict())
            n += 1
            if n >= self.max_str:
                break
        return ReverseResult(True, "get_strings", str(p), self.name, ev,
                             note=f"最多{self.max_str}条；偏移为文件内偏移")

    def decompile_function(self, target: str, function: str) -> ReverseResult:
        """binutils 无法给伪 C，返回带地址反汇编（伪代码需切 ghidra 后端）。"""
        p = self._target(target)
        asm_all = self._run(["objdump", "-d", "-M", "intel", str(p)])
        marker = f"<{function}>:"
        lines = asm_all.splitlines()
        block, grab = [], False
        for i, ln in enumerate(lines):
            if marker in ln:
                grab = True
            if grab:
                block.append(ln)
                # 到下一个符号标签结束
                if len(block) > 1 and ln.strip().endswith(">:") and marker not in ln:
                    block.pop()
                    break
                raw = "\n".join(block)
                if len(raw) > self.max_disasm_bytes:
                    break
        if not block:
            return ReverseResult(False, "decompile_function", str(p), self.name,
                                 error=f"未找到函数 {function}（stripped 或名称不符，可先用 list_functions）",
                                 note="binutils 仅反汇编；伪C请用 ghidra 后端")
        raw = "\n".join(block)[:self.max_disasm_bytes]
        return ReverseResult(True, "decompile_function", str(p), self.name,
                             [Evidence(f"{function} 反汇编(带地址)", function, "objdump -d -M intel", raw).to_dict()],
                             note="binutils=反汇编非伪C；强壳/混淆/自修改代码需动态或更强后端，服务端逻辑不可见")

    def call(self, tool: str, args: Dict[str, Any]) -> ReverseResult:
        if tool == "list_functions":
            return self.list_functions(args.get("target", ""))
        if tool == "get_imports":
            return self.get_imports(args.get("target", ""))
        if tool == "get_strings":
            return self.get_strings(args.get("target", ""), args.get("min_len", 4))
        if tool == "decompile_function":
            return self.decompile_function(args.get("target", ""), args.get("function", ""))
        if tool == "file_info":
            return self.file_info(args.get("target", ""))
        raise BackendError(f"后端不支持工具(可能是非只读操作被拒): {tool}")
