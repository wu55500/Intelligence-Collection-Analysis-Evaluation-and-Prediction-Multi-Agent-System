"""Ghidra headless 后端（可选，本地启用）。

与 binutils 同契约，额外通过 Ghidra analyzeHeadless + 一个导出脚本产出伪 C。
云机默认不装 JDK21/Ghidra，故本后端仅在本地存在以下条件时可用：
  GHIDRA_HOME 环境变量指向 Ghidra 安装目录（含 support/analyzeHeadless）。
全程只读：把样本复制进临时工程分析，不运行样本，不改原文件。
"""
from __future__ import annotations
import os, shutil, subprocess, tempfile, textwrap
from pathlib import Path

from .base import BackendError, Evidence, ReverseResult
from .binutils_backend import BinutilsBackend

_DECOMP_SCRIPT = r"""
# Ghidra Headless 导出脚本（由 m23 自动生成到临时目录）
# @category: M23
import json
from ghidra.app.decompiler import DecompInterface

out = {}
fm = currentProgram.getFunctionManager()
target_name = str(System.getProperty("m23.func", ""))
decomp = DecompInterface(); decomp.openProgram(currentProgram)
funcs = []
for f in fm.getFunctions(True):
    funcs.append({"name": f.getName(), "addr": str(f.getEntryPoint())})
    if target_name and f.getName() == target_name:
        res = decomp.decompileFunction(f, 60, monitor)
        if res and res.decompileCompleted():
            out["pseudo_c"] = res.getDecompiledFunction().getC()
out["functions"] = funcs
with open(str(System.getProperty("m23.outfile")), "w") as fp:
    fp.write(json.dumps(out))
"""


class GhidraBackend:
    name = "ghidra"

    def __init__(self, ghidra_home: str | None = None):
        self.ghidra_home = ghidra_home or os.environ.get("GHIDRA_HOME", "")
        self.bin = shutil.which("analyzeHeadless") or (
            str(Path(self.ghidra_home) / "support" / "analyzeHeadless") if self.ghidra_home else "")
        if not self.bin or not Path(self.bin).exists():
            raise BackendError(
                "未找到 Ghidra：请安装 Ghidra + JDK21 并设置 GHIDRA_HOME（含 support/analyzeHeadless）。"
                "云机可先用默认 binutils 后端跑通链路。")
        # 复用 binutils 的 strings/imports/file（headless 全量分析较重，这几类直接用 binutils 更快）
        self._bu = BinutilsBackend()

    def _run_headless(self, target: str, func: str = "") -> dict:
        import json
        target_p = Path(target).resolve()
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "proj"; proj.mkdir()
            script = Path(td) / "m23_decomp.py"; script.write_text(_DECOMP_SCRIPT)
            outfile = Path(td) / "out.json"
            cmd = [self.bin, str(proj), "m23", "-import", str(target_p),
                   "-postScript", str(script), "-deleteProject",
                   "-scriptPath", str(td)]
            env = dict(os.environ, M23FUNC=func or "")
            # 通过 -D 传 JVM 属性
            cmd += [f"-Dm23.func={func}", f"-Dm23.outfile={outfile}"]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env)
            if not outfile.exists():
                raise BackendError("Ghidra 分析无输出: " + (r.stderr or r.stdout)[-300:])
            return json.loads(outfile.read_text())

    def file_info(self, target: str) -> ReverseResult:
        return self._bu.file_info(target)

    def get_strings(self, target: str, min_len: int = 4) -> ReverseResult:
        return self._bu.get_strings(target, min_len)

    def get_imports(self, target: str) -> ReverseResult:
        return self._bu.get_imports(target)

    def list_functions(self, target: str) -> ReverseResult:
        data = self._run_headless(target)
        ev = [Evidence(f"函数 {f['name']}", f"{f['addr']} @Ghidra", "analyzeHeadless",
                       f"{f['name']} {f['addr']}").to_dict() for f in data["functions"][:200]]
        return ReverseResult(True, "list_functions", target, self.name, ev, note="Ghidra 自动分析后函数清单")

    def decompile_function(self, target: str, function: str) -> ReverseResult:
        data = self._run_headless(target, function)
        c = data.get("pseudo_c")
        if not c:
            return ReverseResult(False, "decompile_function", target, self.name,
                                 error=f"Ghidra 未能反编译 {function}（可能被内联/加壳）")
        return ReverseResult(True, "decompile_function", target, self.name,
                             [Evidence(f"{function} 伪C", function, "Ghidra Decompiler", c).to_dict()],
                             note="伪C仅供理解，强壳/混淆/虚拟化保护可能失败")
