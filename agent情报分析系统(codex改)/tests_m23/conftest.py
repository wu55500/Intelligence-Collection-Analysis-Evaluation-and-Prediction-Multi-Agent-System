import os, shutil, subprocess, sys, tempfile
import pytest

ROOT = os.path.abspath(os.path.dirname(__file__) + "/..")
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, ROOT)  # 使 `import src...` 可用

CRACKME_C = os.path.join(os.path.dirname(__file__), "fixtures", "crackme.c")


@pytest.fixture(scope="session")
def crackme_bin():
    """把自写授权样本源码编译到临时目录，返回二进制路径（二进制不入库）。"""
    gcc = shutil.which("gcc")
    if not gcc or not os.path.exists(CRACKME_C):
        pytest.skip("gcc 或 fixtures/crackme.c 缺失，跳过真实逆向端到端")
    d = tempfile.mkdtemp(prefix="m23_crackme_")
    out = os.path.join(d, "crackme_bin")
    subprocess.run([gcc, "-O0", "-fno-inline", "-o", out, CRACKME_C],
                   check=True, capture_output=True)
    yield out
    shutil.rmtree(d, ignore_errors=True)
