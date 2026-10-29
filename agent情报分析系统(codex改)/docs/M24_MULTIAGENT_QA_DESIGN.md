# M24 需求反推与多模型交叉质检模块 · 设计文档 v2（待架构确认）

> 状态：**设计草案 v2，未写实现代码，未提交 git。** 主人确认架构/模型绑定/开放决策点后再编码。
> 日期：2026-10-21　归属仓：Intelligence-Collection-Analysis-Evaluation-and-Prediction-Multi-Agent-System（仓库名不变）
> v2 变更要点：①从"新建一整套"改为"挂接仓库既有资产，只新增真正缺失的 4 块"；②修复三家厂商矛盾；③新增 M23/M24 联用路由与授权门；④模型独立/证据独立两本账；⑤审计加 request_id 等服务端证据、cost 三字段；⑥五道准入门映射既有 WORKSHEET/scorecard，不新增 M 编号；⑦评分只排序、致命问题走硬闸门。

---

## 0. 先把三个"逆向"语义彻底分开（前提审查）

| 名字 | 真实含义 | 落点 |
|---|---|---|
| **M23 二进制逆向** | 对二进制样本做只读静态分析（file/nm/strings/objdump/伪C），软件安全/RE 语义 | `src/modules/m23_mcp/`（已完成、已发布） |
| **M24 需求逆向（本稿）** | 自然语言需求 → 功能模块 → 岗位/专业/技术栈反推 → 调度 → 多模型质检 | 本设计 `m24_requirement_qa` |
| **参考项目逆向（既有）** | 拆解开源参考项目来设计/复刻自己的项目，含 adopt/adapt/reject | 既有 skill 模板 `REVERSE_ENGINEERING_WORKSHEET.md` A–G 节 |

三者**不共享术语、库、编号**；后两者亲缘近，M24 直接吸收 WORKSHEET，而不是重造。豆包帖《需求拆解与技能调度器》的"逆向工程"是第②义，**全文无任何二进制内容**；其 5 个 agent 被作者承认为"同一底层模型扮演、无独立 key"，本设计不采纳该实现。

---

## 1. 前提裁决（本质冲突先解决）

1. **M23 不改名、不扩张职责**，继续只管二进制只读逆向（ChatGPT 与我一致）。
2. **不重造治理件**：编排/闸门/红队/证据链/岗位映射/评分卡在仓库已有成熟实现，M24 挂接复用（见 §2）。
3. **不假多 agent**：完整交叉质检强制 3 家不同厂商真实 API，缺一不跑完整流程；无 key / 无 litellm / 鉴权失败一律 fail-fast，生产路径禁止 `[模拟]`、禁止 `local:True` 兜底；桩仅限 tests。
4. **不直接改 `UnifiedLLMClient`**：它被 M1–M23 依赖，且 ImportError 时返回 `[模拟]`、`local:True`。M24 用**独立的 strict-real 网关**包住它的 litellm 通道，不动旧类、不影响存量模块（避免未核调用方依赖就改核心）。
5. **阈值是先验不是规律**：<2 / 2–3.5 / >3.5 等全部标 `prior_until_backtested`、可配；评分只用于排序分流，**不代表真伪概率**。
6. **不新增 M 编号**：ChatGPT 所说"M-RE1~M-RE5"在仓库中并不存在（全仓 grep 无此编号，是它对 WORKSHEET A–G 的归纳）。五道准入门直接映射 WORKSHEET B–G 与 scorecard hard gates，沿用原生结构。
7. **排除 Gemini**：升级既有 `REVIEW_PROTOCOL.md` 时从审查清单剔除 Gemini（旧版 V1.0 含它，与主人当前要求冲突）。
8. **不迁移豆包无口径数值**：其热度 92/85、总分 4.14 等无来源/样本量，不沿用；非可复现来源一律显式标先验。

---

## 2. 复用优先：M24 挂接哪些既有件（只新增 4 块）

| 能力 | 仓库既有实现（已读码/读文核实） | M24 怎么用 |
|---|---|---|
| 工作流编排/步骤重跑/熔断/检查点 | `services/orchestrator_v2.py`（四层 L1–L4、`ValidationGate`、红队、checkpoint、StepDiff） | M24 作为新增 step 序列接入 V2，must_fix 回跑复用 checkpoint，不另写编排器 |
| 模块输出契约/验收闸门 | `core/validation_gate.py` `ModuleOutput`+`ValidationGate`（"不能凭返回对象判成功"） | 五角色输出全部走 `ModuleOutput`；异源/真实API/证据完整做成新增校验规则 |
| 独立第三方复核 | `services/red_team.py` `IndependentVerifier`（来源独立性/反证/方法/基线/证伪锚点；"不自动有否决权"） | E 终审扩展它，不重写 |
| 证据分级/三角验证/矛盾管理 | `m12_evidence/chain.py`（CRAAP×相关×诊断、≥3独立源、孤证限用） | B 的数据/反例维、"证据独立性账本"复用此判据 |
| 模型能力画像/路由 | `agents/router/model_registry.py`（ModelProfile/find_best_for_task） | 扩展加"异源约束"，角色→provider 绑定挂这里 |
| 统一存储 | `core/database.py`（tasks/evidence/claims/forecasts/audit_logs） | M24 新表挂同一 Database 同构模式，不开裸连接 |
| **需求反推/岗位映射人工模板** | `skills/ai-project-feature-completion/templates/REVERSE_ENGINEERING_WORKSHEET.md`（A–G）、`JOB_COMPETENCY_MATRIX.md`（岗位要求→项目证据，带来源日期、诚实标 gap） | **M24 的核心母版**：把人工填写升级为"真实API半自动执行+证据落库"，E 节即技术→功能→岗位映射 |
| **评分与硬闸门理念** | `references/scorecard.md`（Hard gates 在 100 分之外，致命项直接 NOT RELEASE-READY） | 三层分流走分数；安全/造假/前提崩塌走独立 hard gate，不被均分抵消 |
| 多 AI 审查（人工版） | `docs/REVIEW_PROTOCOL.md` V1.0（人工发审查包给网页 AI，≥3 票） | 升级为**程序自动调真实多厂商 API**；去 Gemini；保留"审查包/汇总/修改"结构 |

**真正全新、仓库与豆包都没有的只有 4 块**：
1. 需求→岗位/专业/技术栈的**可执行反推器**（WORKSHEET 是静态模板，没有执行器和分区库）；
2. **行业+岗位分区技术栈库**（带来源/时间/样本/TTL/去重）；
3. **跨厂商真实模型的异源强制 + 调用审计网关**（核心价值）；
4. 三层分流 + 五道准入门的**确定性执行器**（模板里是人工判断，没有代码裁决）。

---

## 3. M23 × M24 联用与路由（回答"逆向游戏服务器/软件系统"场景）

### 3.1 三类场景路由

| 场景 | 主导 | M23 | M24 |
|---|---|---|---|
| ① 从零开发（绿地软件/游戏服务器） | M24 | 不介入（无目标可逆） | 全程：反推→映射→质检→准入 |
| ② 纯二进制/样本（可疑文件、私有协议、找算法） | M23 | 全程只读逆向 | 多模型盲审**可选**做第二意见 |
| ③ 混合：要做/仿一个有现成实现的系统（**主人举的游戏服务器属此类**） | M24 | 按需被点 | 主导 |

混合场景数据流：
```
M24 反推出功能模块/技术栈
   └─ 遇到"现成系统某模块怎么实现/私有协议·文件格式·校验逻辑搞不懂、且无源码"
        → 子 agent【提议】逆向某目标 + 理由
        → 确定性【逆向授权门】(§3.2) 核准
             → 调 M23 只读工具取证(file/nm/strings/imports/decompile)
             → 证据(带地址/来源)回流 M24，作为 B 反证、E 终审的可追溯证据
        → M24 五道准入门裁决 adopt / adapt / reject
```

### 3.2 子 agent 的"判断权 vs 拍板权"（合规边界）

- **可以给子 agent 的**：意图识别、路由建议——"这个任务是否需要逆向、建议逆哪个模块、为什么"。
- **必须确定性门掌握、agent 不能自行决定的**：是否真的对某文件执行逆向。`reverse_dispatch_gate` 全部满足才放行：
  1. 目标是**主人授权样本/自有资产/明确许可分析的开源文件**；
  2. 文件真实存在、哈希已记录；
  3. 只走 M23 只读白名单工具（file_info/list_functions/get_imports/get_strings/decompile_function）；
  4. 不触碰未授权第三方生产系统、绕过技术保护措施、解密受保护内容；
  5. 高不确定时挂起转人工（返回 NEEDS_HUMAN_AUTH，不擅自执行）。
- 这与 `base_agent`"关键规则由确定性服务执行，agent 无越权权力"、M23 既有只读白名单一致。

---

## 4. 五个角色（异源与锚定控制）

| 角色 | 职责 | provider（国外优先，排除 Gemini） | 独立性 |
|---|---|---|---|
| **A** MetricArchitect 指标搭建 | 业务目标→可检验一级/二级指标、定义、权重依据(先验)、数据需求 | 厂商①（Anthropic Claude 旗舰档） | — |
| **B** CriticalEvaluator 批判反证 | **先在看到 A 的详细指标前**独立做首轮反证（假设/反例/数据缺口/边界/替代），随后再对照 A 方案评审；从原始需求出发，不只给 A 打分 | 厂商②（OpenAI GPT 旗舰档） | 必须 ≠ A |
| **C** Librarian 流程库管 | 问题三层分流、问题/版本/回归库、A/B 实验提案；**流程管理角色，不算独立验证票** | 可复用①或②（建议用编码档/Codex 类） | 不计入独立性票数 |
| **D** TechCollector 技术采集 | 真实搜索/浏览器/官方文档/招聘 JD 采集，岗位↔技术栈入分区库，每条带来源+时间+证据等级；**不靠模型记忆答** | 可用成本档模型（任一已配置厂商） | 采集工具真实性独立审计 |
| **E** IndependentReviewer 独立终审 | 输入=**原始需求+验收标准+可追溯证据+待交付产物**；**只不看 A/B 结论草稿**；检查需求/证据/技术风险/完整度/致命项；分歧由确定性程序合并 | 厂商③（必须异于①和②，如 xAI 或 OpenRouter 聚合到的第三家真实厂商） | **必须异于 A、B** |

**硬规则（确定性校验，不靠模型自觉）**：
- 完整 A/B/E 交叉质检 = 必须 **3 家不同 provider**；启动校验路由与厂商身份，不满足拒绝进入完整流程，返回 `NEED_MULTI_PROVIDER_KEYS`。
- 只有 2 家：允许跑 A/B，但结果明确打标 `NO_INDEPENDENT_FINAL_REVIEW`，**不得宣称完成多 Agent 交叉质检**。
- 只有 1 家：strict 模式拒绝。不提供"同模型换角色"开关。
- 用聚合服务（如 OpenRouter）时，要校验其路由到的**底层真实厂商**确实是三家不同，统一入口不等于模型异源。
- B 的首轮反证在 A 详细方案曝光前完成（防锚定）；E 全程盲于 A/B 草稿（防从众）。

---

## 5. 真实 API 契约（P0，模块可信度的根）

### 5.1 生产调用契约
- 每角色声明 provider/model/配置；只能用正式厂商 API 或明确配置的真实聚合，**禁止用网页聊天结果冒充 API 回包**。
- 请求真实发出，响应做校验；**配置里写的模型名不能代替真实响应记录**。
- 失败即失败：无密钥/依赖缺失/鉴权错/限流/超时/响应非法 → 类型化异常，run 标 `FAILED_REAL_API`，指出缺哪家；不造内容、不静默降级。
- **调用真实性与判断正确性分开验收**：API 真通只证明调用发生过，不证明答案对；答案对也不能反推它来自所声称的 API。

### 5.2 审计字段（证明"真的打到了厂商"，而非仅防篡改）
每次调用写受控审计日志（脱敏、密钥不入库）：
- 服务端回传的**真实 model 标识**（model echo，核对与请求是否一致）；
- 厂商 **request_id**（若提供；无则显式记 null，不编造）；
- HTTP 状态、请求/响应时间、延迟；
- 真实 prompt/completion/total **token 用量**；
- finish_reason、错误信息；
- **费用三字段分列**：`tokens_actual`（真实用量）/ `cost_estimated`（按可追溯计价规则估算，可空）/ `cost_settled`（已结算，可空）；缺失标 unknown，**不用虚构费用填满**；
- prompt/response 的 sha256（仅用于防篡改、查重，**不单独当作调用真实性证据**）；
- 提示词模板版本 + 模型配置版本。

### 5.3 模型独立 ≠ 证据独立（两本账）
- `model_provenance`：登记每角色 provider/model/request_id（证明模型来源独立）。
- `evidence_independence`：登记每个关键结论背后的**原始来源 URL/出处**，做来源聚类——三个模型引同一篇错文章、共同语料、共同 prompt 偏差，**不算三份独立证据**；复用 M12 三角验证判据（≥3 真正独立源才强验证）。
- 关键事实不按"三票多数"认定；需原始来源核验 + 反例搜索 + 必要人工复核。

### 5.4 strict-real 网关 `RealLLMGateway`
- 启动自检：litellm 可导入、各所需 key 存在、（可选/省钱开关）最小探活。
- 依赖注入：生产注入 Real、测试注入 `tests_m24/fakes.py::FakeLLM`；**生产代码不 import fakes**（CI grep + import 边界双保险）。
- 不改 `UnifiedLLMClient`，独立成类，复用其 litellm 用法但移除一切模拟/本地兜底。

---

## 6. 五道功能准入门（采纳 ChatGPT，映射既有 WORKSHEET/scorecard，不新增 M 编号）

候选功能（尤其从开源/逆向对象借鉴的）必须依次过：

| 门 | 检查 | 对应既有资产 |
|---|---|---|
| ① 来源与授权门 | 固定 commit、许可证、依赖许可证、使用范围、provenance | WORKSHEET B 节 + M23 授权门 §3.2 |
| ② 机制证据门 | 区分：源码实际行为 / 测试验证行为 / 文档声称行为 / 未验证推断；不看 star 定质量 | WORKSHEET B/C、M23 证据链 |
| ③ 反证与替代方案门 | 有无更简实现、是否与现有模块重复、是否真解决目标问题；"技术本身不是需求" | WORKSHEET E/G、red_team、reflection |
| ④ 增益验证门 | 引入前后对照：准确率/召回/延迟/API成本/资源/安全/维护负担；无可测增益不准入 | WORKSHEET F、scorecard Data/AI 维 |
| ⑤ 集成与回滚门 | 接口兼容、依赖可用、测试通过、数据迁移可控、有回滚；新依赖/容器/沙箱/权限变化**先经主人确认** | WORKSHEET G、scorecard Hard gates |

裁决：**通过 / 有条件通过 / 阻断 / 等待人工决策**。

---

## 7. 评分：排序工具，不是真伪概率

- B 对二级指标按五问给 0–5 分，**每项必须引用证据**，无证据不入库。
- 三层分流（阈值集中配置，标先验待回测）：

| 区间 | 分流 | 动作 |
|---|---|---|
| `<2.0` | must_fix | blocker，修复回跑（计 qa_round，超 `max_qa_rounds=3` 转 `BLOCKED_NEEDS_HUMAN`） |
| `2.0–3.5` | user_decision | C 出 2–3 个带工作量的方案，挂起等主人选或组合 |
| `>3.5` | suggestion | 自主（低于设定人时直接做）或询问，不阻塞 |

- **Hard gates（分数之外，命中即阻断，不被均分抵消，复用 scorecard 理念）**：密钥/敏感泄露、致命安全问题、关键前提不成立、证据造假/无证据结论、失败测试被瞒报、未授权改动、真实 API 调用成功但证据链不完整。
- 交付条件（确定性）：must_fix=0、E fatal_count=0、所有 hard gate 未命中、真实 API provenance 完整。

---

## 8. 数据（挂接 core/database，不另起裸连接）

沿用 `Database` 同构模式，新增 M24 表（库文件不入库，`data/` 已 ignore）：
- `tech_stack(industry, role_category, tech_name, tech_type, function_note, heat, source_url, source_method, sample_size, fetched_at, ttl_days, course_ref, UNIQUE(industry,role_category,tech_name))` + 分区索引。
- `requirement_runs / function_modules(模块→岗位/专业/技术栈/调度/验收)`。
- `metric_sets(权重带 weight_prior 标记)`、`evaluations(五问+证据)`。
- `issues(tier 三档, options_json)`、`ab_tests`、`independent_reviews`。
- `artifacts/versions`、`agent_memory(industry,role_category 分区, 启动召回最近20)`。
- `agent_turns`：在 v1 字段上**增加** `server_model_echo, request_id, http_status, cost_estimated, cost_settled, prompt_template_version, config_version`；`cost` 单字段改为三字段。
- `evidence_independence(conclusion_id, source_url, source_cluster_id, independent_bool)`：证据独立账本。
- 预置岗位分类 `references/role_taxonomy.yaml`：游戏（TA/策划/客户端/服务端/建模/美术/音乐/测试UI）；互联网（前端/后端/算法AI/大数据/数仓/BI/DBA/运维/测试/爬虫/自动化/云计算/Ops/安全）。可追加。

---

## 9. 文件结构（确认后再建，挂接为主、体量比 v1 小）

```
src/modules/m24_requirement_qa/
  models.py            # 类型/枚举/类型化异常
  gateway.py           # RealLLMGateway（strict-real，独立于 UnifiedLLMClient）
  role_config.py       # 角色→provider 绑定 + 三家异源校验（扩展 model_registry）
  reverse_map.py       # 需求反推执行器（母版=REVERSE_ENGINEERING_WORKSHEET A–E）
  tech_store.py        # 行业+岗位分区技术栈库（挂 core/database）
  roles/               # A metric_architect / B critical_evaluator(先反证) /
                       # C librarian / D tech_collector / E independent_reviewer(盲)
  triage.py            # 三层分流 + hard gates（确定性）
  admission_gates.py   # 五道准入门（映射 worksheet/scorecard）
  dispatch.py          # M23/M24 路由 + 逆向授权门 reverse_dispatch_gate
  orchestration.py     # 作为 step 接入 orchestrator_v2，复用 checkpoint/gate/red_team
  integration.py / agent_wiring.py   # start/stop、router、挂 research/analysis，开关 INTEL_M24_ENABLED
references/role_taxonomy.yaml
config/m24_models.example.yaml       # 角色→provider/型号占位，无密钥
tests_m24/fakes.py + conftest.py + test_*.py
docs/M24_MULTIAGENT_QA_DESIGN.md     # 本文
（另）升级 docs/REVIEW_PROTOCOL.md 到 V2.0：人工网页版 → 程序真实API版，去 Gemini
```

---

## 10. 验收测试契约（离线 Fake 验证逻辑 + 真实 API 二段验收）

**离线（无 key，交付即真跑，Fake 注入）**：
1. 反推完整性与分区落库；2. 三层分流边界（1.9/2.0/3.5/3.6 不串档）；3. must_fix 回跑与 max 轮熔断；
4. **三家异源**：A/B 同厂拒绝、E 与 A/B 任一相同拒绝、仅 2 家标 `NO_INDEPENDENT_FINAL_REVIEW`、仅 1 家拒绝；
5. **真实失败即停**：ImportError/无 key/鉴权失败抛错、run 标 FAILED_REAL_API；断言生产路径无 `[模拟]`、生产代码不 import fakes；
6. **审计契约**：缺 request_id/用量字段时记 null/unknown 不伪造；cost 三字段分列；
7. **证据独立**：三模型引同一来源不计三独立证据；8. E 输入含需求/验收/证据但不含 A/B 草稿字样；
9. hard gate：评分够但有致命安全项仍阻断；调用成功但证据链不全不判交付；
10. 回归：修复后旧用例再失败不通过；无增益的高成本新功能不准入；M23 授权门拒绝未授权目标。

**真实端到端（需主人在部署环境给 3 家 key 后，不预设通过）**：
11. 示例需求真跑，核对 agent_turns 里 A/B/E 来自三家真实回包、真实 request_id/model echo/token；
12. 错 key/断网演练 fail-fast；13. 真实采集一条技术栈并打开 source 核验；14. 混合场景实跑一次 M24 点 M23 取证据→回流评审。

> 当前云机无 key、无 litellm，只能完成 1–10；11–14 在配 key 前不宣称通过。

---

## 11. 三档去向（外部方法准入）

- **执行**：需求反推三段式、岗位/技术栈映射、五角色分工、B 批判五问、三层分流(先验)、问题/版本/记忆库按行业岗位分区、独立终审、A/B 提案、排除 Gemini；ChatGPT 的三家异源、两本账、request_id 审计、hard gate、五道准入、B 先反证、E 完整隔离输入。
- **留库知识层**：豆包行业岗位分类作 taxonomy 初始参考（技术名可用、热度分不沿用）；ChatGPT 评审作为本稿质量基线存档。
- **不采纳（写明理由）**：①同一模型扮多角；②无 key 仍宣称多 agent；③无口径热度/评分；④把需求反推与二进制逆向混用术语；⑤自动建沙箱/装 Docker 等重环境动作（纳入建议、主人确认才执行）；⑥生造"M-RE"编号（沿用仓库原生 A–G/hard gates）；⑦直接改 UnifiedLLMClient（用独立网关，防影响 M1–M23）。

---

## 12. 待主人确认的开放决策点

1. **第三家厂商**给 E 用谁（xAI / OpenRouter 路由到的真实第三家 / 其他）？这是完整交叉质检的硬前提；只给两家则系统只跑 A/B 并打标无独立终审。
2. 是否同意把 `REVIEW_PROTOCOL.md` 升级为 V2.0（程序自动真实 API、去 Gemini），旧人工版保留为离线兜底？
3. M24 挂到 research/analysis agent，还是作为独立服务入口？
4. D 采集主源：官方文档+搜索为主、招聘 JD 为辅（反爬强），是否认可？
5. 五道准入门第⑤门涉及新依赖/容器/沙箱/权限一律先人工确认，确认这个默认。
6. 阈值先按 <2 / 2–3.5 / >3.5 上线、后续用历史验收样本回测校准，是否认可。

> 确认后按 §9 建代码、先跑通离线 1–10 并交付；真实 API（11–14）等部署环境配好 3 家 key 再联调。
