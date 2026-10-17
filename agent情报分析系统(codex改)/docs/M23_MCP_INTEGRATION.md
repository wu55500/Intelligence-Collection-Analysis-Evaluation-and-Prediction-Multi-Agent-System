# M23 · MCP 工具集成与受控只读逆向（集成文档 / Runbook）

> 新增模块，**不改** m1–m21 既有能力与 BaseAgent 字典分派；以"只插不覆"方式接入。
> 逆向工具**全部只读**；本模块用于你本人授权的二进制分析，产物默认本地、不入公开仓。

## 1. 它解决什么
原系统 `UnifiedLLMClient.complete()` 已能把 `tools` 传给 litellm 并解析 `tool_calls`，
但缺两块：①没有真实外部工具源；②没有"模型决定调工具→执行→回填→再问"的闭环，
BaseAgent 只能按子任务 `type` 写死分派。M23 补齐这两块：

- 真实工具源：MCP（Model Context Protocol）server，默认带一个**只读逆向 server**；
- 真正的工具循环：模型自主多轮调用，直到产出结论，全程留痕、有最大轮次上限。

## 2. 文件清单（新增，均在 src/modules/m23_mcp/）
| 文件 | 职责 |
|---|---|
| `mcp_client.py` | 多 server 连接管理：stdio 会话常驻、`mcp__server__tool` 命名空间、**只读白名单过滤**、单 server 挂掉不阻断 |
| `tool_loop.py` | 工具调用循环（可注入 llm_call，最大轮次、每步 trace、tool 消息回填） |
| `engine.py` | 对外主类 `ReverseMCPModule`（对齐 m1–m21 engine 规范）+ litellm 适配 + 默认逆向 server 配置 |
| `integration.py` | 只插不覆：`m23_lifespan` 钩子、`create_m23_router()`（/mcp/health·/tools·/analyze）、`register_reverse_tool()` |
| `config_loader.py` | 读取 config/mcp_servers.json |
| `reverse_mcp_server.py` | FastMCP stdio server，暴露 5 个**只读**工具 |
| `reverse_backends/` | 可插拔引擎：`binutils_backend.py`（云机零依赖）、`ghidra_backend.py`（本地可选，出伪 C）、`base.py`（契约/证据结构） |

配置：`config/mcp_servers.example.json`；依赖：requirements 追加 `mcp>=1.2.0`。

## 3. 五个只读工具（白名单，越权即拒）
`file_info` · `list_functions` · `get_imports` · `get_strings` · `decompile_function`
——全部不写盘、不执行目标、不联网；subprocess 用 argv 列表（无 shell）、30s 超时、
函数/字符串条数上限，防目标内恶意参数注入与资源膨胀。

## 4. 接入主系统（最小 diff，默认不改）
在 `src/api/main.py`：
```python
from ..modules.m23_mcp.integration import start_m23, stop_m23, create_m23_router
# lifespan 内：yield 前 await start_m23(backend="binutils")；yield 后 await stop_m23()
# app 建完：app.include_router(create_m23_router())
```
给某个 agent 挂逆向能力（复用现有 register_tool/字典分派，无需改 base_agent.py）：
```python
from ..modules.m23_mcp.integration import register_reverse_tool
await register_reverse_tool(agent, model_id="openai/gpt-4o-mini")
# 子任务 {"type":"reverse_intel","target":"/path/bin","question":"校验机制是什么"}
```

## 5. 已真实验证（云机，gcc 11 + binutils）
自写授权样本 `lab/crackme.c`（滚动 XOR，初值 0x5a，SECRET="REA-MCP-LAB-2026"），
经 stdio 真拉起 server、桩 LLM 驱动 3 轮工具循环（零 API key）：
- `SECRET` 字符串带地址 **0x2010**；`Correct!`@0x2032；`Wrong key`@0x203b
- XOR 初值 **0x5a**：`mov BYTE PTR [rbp-0x9],0x5a`；`check_key` 反汇编成功
- 导入含 `printf/puts/__libc_start_main`
- 非白名单 / 未注册工具被拒；坏 server 仅记 dead 不阻断；FastAPI lifespan + 探针路由通过
`python3 -m pytest tests_m23 -q` → 3 passed。

## 6. 本地 Ghidra 出伪 C（可选增强）
云机只有 JRE11 无 javac，跑不了 Ghidra；在你**本机**：
1. 装 Ghidra（需 JDK 17+），设 `GHIDRA_HOME` 指向解压目录（含 `support/analyzeHeadless`）；
2. `config/mcp_servers.json` 里 reverse 的 env 设 `"REVERSE_BACKEND":"ghidra"`（或改 backend_default）；
3. 重启即可，`decompile_function` 返回 DecompInterface 伪 C；未装则自动报错并可回退 binutils。
binutils 给汇编/地址/导入/字符串，Ghidra 给可读伪 C，二者同一套只读契约。

## 7. 能力边界（诚实标注，别对外吹过头）
- 只读静态分析：**无动态调试/脱壳/反混淆**；VMProtect/UPX 等加壳样本只能看到壳；
- 服务端逻辑、云端下发代码不可见；stripped 二进制符号会缺失（靠字符串/导入推断）；
- 反汇编/伪 C 是证据，**机制结论仍可能错**：报告必须区分"观察/推断"、给替代解释、证据不足就说不足。
- 这与 REA 的定位一致：编排层不是引擎，真正出证据的是 binutils/Ghidra/IDA 这类后端。

## 8. 安全/隐私自检
- 只读白名单 + 命名空间隔离 + argv 无 shell + 超时 + 条数上限；
- 目标路径 resolve 后才访问；server 与证据产物放本地工作区，**不进 public 仓、不上传样本**；
- 逆向产物仅用于你本人授权目标；不内置任何"绕过许可/分发破解"能力。
