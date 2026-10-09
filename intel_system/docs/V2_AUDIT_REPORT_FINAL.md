# V2 真实性审计报告（最终版）

**审计日期**: 2026-10-09  
**审计原则**: 不假设代码正确，只相信可复现的证据  
**审计范围**: P0-1 到 P0-4 全部验收项

---

## 一、统计核查

### 1.1 测试数量核查

| 测试文件 | 测试数量 | 状态 |
|---------|---------|------|
| test_core.py | 6 | ✓ 全部通过 |
| test_modules.py | 8 | ✓ 全部通过 |
| test_services.py | 13 | ✓ 全部通过 |
| test_v2_integration.py | 24 | ✓ 全部通过 |
| test_v2_audit.py | 17 | ✓ 全部通过 |
| **总计** | **68** | **✓ 全部通过** |

**结论**: 实际测试数量为68个，不是之前声称的51个。所有68个测试在修复3个真实BUG后全部通过。

### 1.2 Python文件数量

**实际统计**: 79个Python文件  
**说明**: 文件数量不能完全代表功能完成度。关键是每个模块是否有真实实现、调用链是否完整、测试是否覆盖。

---

## 二、P0验收项测试结果

### P0-1: 验收闸门是否真正生效

| 测试场景 | 预期行为 | 实际行为 | 结果 |
|---------|---------|---------|------|
| 无效输出（空数据） | 关键模块无证据引用 → 阻断 | 闸门拒绝，阻断生效 | ✓ PASS |
| 缺失证据引用 | 采集模块必须产生证据引用 | 正确识别缺失并阻断 | ✓ PASS |
| 关键模块失败 | 采集/分析模块失败 → 阻断 | 关键模块失败触发阻断 | ✓ PASS |
| 非关键模块失败 | 非关键模块失败不应阻断 | 非关键模块失败只记录警告，不阻断 | ✓ PASS |

**代码位置**: `src/core/validation_gate.py`  
**验证方法**: `tests/test_v2_audit.py::TestP0_1_ValidationGate` (4个测试)

### P0-2: 检查点是否能跨进程恢复

| 测试场景 | 预期行为 | 实际行为 | 结果 |
|---------|---------|---------|------|
| 跨进程恢复 | 新建服务实例能读取检查点 | 成功恢复，can_resume=True | ✓ PASS |
| 重复执行一致性（幂等性） | 同task_id+step_name只产生1个检查点 | 通过查找已有记录复用checkpoint_id | ✓ PASS |
| 重试上限 | 超过max_retries后状态为failed | 正确计数，状态转为failed | ✓ PASS |
| 新旧结果留痕 | 不同输入应产生不同输出 | 通过input_hash区分，保留历史 | ✓ PASS |

**代码位置**: `src/services/checkpoint.py`  
**修复内容**: 
- 添加UNIQUE(task_id, step_name)约束
- save_checkpoint()先查找已有记录，复用checkpoint_id实现幂等

**验证方法**: `tests/test_v2_audit.py::TestP0_2_Checkpoint` (4个测试)

### P0-3: 验证红队是否真正独立

| 测试场景 | 预期行为 | 实际行为 | 结果 |
|---------|---------|---------|------|
| 伪独立来源识别 | 识别同源多来源为不独立 | 通过域名/URL相似度检查识别伪独立 | ✓ PASS |
| 方法不适当 | 小样本不做统计检验 | 识别样本量<30且未做统计检验 | ✓ PASS |
| 高置信度削弱 | 证伪锚点缺失+高置信度 → 阻断 | 新增规则：WEAKENED+confidence>=0.8 → 阻断 | ✓ PASS |

**代码位置**: `src/services/red_team.py`  
**修复内容**: 
- _should_block()新增规则：任何finding.result==WEAKENED且confidence>=0.8时触发阻断

**验证方法**: `tests/test_v2_audit.py::TestP0_3_RedTeam` (3个测试)

### P0-4: 验证预测闭环与权限边界

| 测试场景 | 预期行为 | 实际行为 | 结果 |
|---------|---------|---------|------|
| 预测生命周期 | 登记→结算→回测追溯 | 成功登记，结算后DB更新状态，回测查询DB获取最新状态 | ✓ PASS |
| 权限越权 | L1权限不能删除数据 | 识别危险操作，要求L3权限 | ✓ PASS |
| 路由失败状态 | 无可用模型时返回明确状态 | 返回None或记录决策原因 | ✓ PASS |
| 路由审计记录 | 所有路由决策有审计记录 | 记录total_decisions, by_task_type, by_model | ✓ PASS |

**代码位置**: `src/services/forecast_service.py`, `src/services/permission_service.py`, `src/agents/router/smart_router.py`  
**修复内容**: 
- calculate_brier_score()从DB查询已结算预测的最新状态，而非依赖传入的内存对象
- 添加Database.get_settled_forecasts()方法

**验证方法**: `tests/test_v2_audit.py::TestP0_4_ForecastPermission` (4个测试)

---

## 三、修复的3个真实BUG

### BUG-1: 检查点幂等性失效

**问题**: `save_checkpoint()`每次生成新UUID，导致同task_id+step_name产生多条记录  
**根因**: checkpoint_id作为主键，但每次调用都生成新值  
**修复**: 
1. 添加UNIQUE(task_id, step_name)约束
2. save_checkpoint()先查询已有记录，复用checkpoint_id
3. 使用INSERT OR REPLACE实现覆盖

**影响**: 检查点无法正确去重，恢复时可能产生混乱  
**验证**: test_p0_2_2_idempotent_save通过

### BUG-2: 红队无法阻断高置信度削弱

**问题**: 证伪锚点缺失（confidence=0.9）产生WEAKENED结果，但不触发阻断  
**根因**: _should_block()只检查CONTRADICTED，未考虑高置信度的WEAKENED  
**修复**: 新增规则：任何finding.result==WEAKENED且confidence>=0.8时触发阻断

**影响**: 严重问题（如缺少证伪锚点）无法阻断流程，可能导致错误结论交付  
**验证**: test_p0_3_3_high_confidence_block通过

### BUG-3: Brier Score计算返回count=0

**问题**: 传入已结算的预测对象，但calculate_brier_score()返回count=0  
**根因**: 
1. 传入的ForecastRecord对象是内存中的旧引用（settled=False, outcome=None）
2. settle_forecast()只更新数据库，未更新传入的对象
3. calculate_brier_score()检查f.settled，但内存对象未更新

**修复**: 
1. calculate_brier_score()从DB查询已结算预测的最新状态
2. 如果传入列表，根据forecast_id从DB刷新对象状态
3. 添加Database.get_settled_forecasts()方法

**影响**: 预测回测无法正常工作，无法评估预测准确性  
**验证**: test_p0_4_1_forecast_lifecycle通过

---

## 四、CI/CD验证

**现状**: GitHub Actions工作流文件已创建（`.github/workflows/ci.yml`），但尚未在GitHub上实际执行

**建议**: 
1. 推送代码到GitHub后，手动触发一次CI
2. 确认所有68个测试在CI环境中通过
3. 确认覆盖率报告正确生成

**本地验证**: 所有68个测试在本地环境通过（pytest tests/ -v）

---

## 五、模块实现真实性

### 5.1 已验证的模块

以下模块有真实实现、完整调用链、测试覆盖：

| 模块 | 功能 | 代码位置 | 测试覆盖 |
|-----|------|---------|---------|
| M1-M7 | 采集、治理、EDA、特征、因果、模型选择、评估 | src/modules/m1_collection ~ m7_evaluation | test_modules.py |
| M8 | 预测登记与结算 | src/modules/m8_forecast/forecaster.py + src/services/forecast_service.py | test_services.py, test_v2_audit.py |
| M9-M12 | 优化、告警、知识图谱、证据链 | src/modules/m9-m12 | test_modules.py |
| M13 | 报告生成 | src/modules/m13_report/reporter.py | test_modules.py |
| M14 | 权限治理 | src/services/permission_service.py | test_services.py, test_v2_audit.py |
| M15 | 指标收集 | src/modules/m15_metrics/ | test_v2_integration.py |
| M16-M18 | 回测、运营算法、仿真 | src/modules/m16-m18 | test_modules.py |
| M19 | 编排器 | src/services/orchestrator_v2.py | test_v2_integration.py |
| M20 | 模型健康 | src/modules/m20_model_health/ | test_v2_integration.py |
| M21 | 承诺等级 | src/services/commitment_engine.py | test_services.py, test_v2_integration.py |

### 5.2 关键基础设施

| 组件 | 功能 | 代码位置 | 测试覆盖 |
|-----|------|---------|---------|
| ValidationGate | 模块输出契约验证 | src/core/validation_gate.py | test_v2_audit.py, test_v2_integration.py |
| RedTeam | 独立验证器 | src/services/red_team.py | test_v2_audit.py, test_v2_integration.py |
| CheckpointService | 检查点持久化 | src/services/checkpoint.py | test_v2_audit.py, test_v2_integration.py |
| SmartRouter | 智能模型路由 | src/agents/router/smart_router.py | test_v2_integration.py |
| Cache | 缓存（内存降级） | src/infra/cache/ | test_v2_integration.py |
| VectorStore | 向量存储 | src/infra/vector/ | test_v2_integration.py |
| MemoryManager | 短/长/工作记忆 | src/infra/memory/ | test_v2_integration.py |
| Database | SQLite数据库 | src/core/database.py | 间接测试 |

### 5.3 待验证项

- **M19编排器**: `src/modules/m19_orchestrator/__init__.py`为空，实际逻辑在`src/services/orchestrator_v2.py`
- **真实数据采集**: 当前所有采集模块使用模拟数据，未接入真实搜索引擎API
- **CI/CD**: 工作流文件已创建，但未在GitHub上执行

---

## 六、结论

### 6.1 P0验收项

**全部通过**: P0-1, P0-2, P0-3, P0-4 全部验收项通过，有可复现的测试证据

### 6.2 修复的真实BUG

1. 检查点幂等性失效 → 已修复
2. 红队无法阻断高置信度削弱 → 已修复
3. Brier Score计算返回count=0 → 已修复

### 6.3 统计数字澄清

- 测试数量: 68个（不是51个）
- Python文件: 79个（文件数量≠功能完成度）
- CI/CD: 工作流文件已创建，未实际执行

### 6.4 下一步建议

**冻结新增功能**，等待以下确认：

1. 推送代码到GitHub，触发CI，确认所有测试在CI环境通过
2. 接入至少1个真实数据源（如Google News API），验证端到端流程
3. 编写1个端到端集成测试，模拟完整任务流程

**确认以上3点后，再讨论新功能开发。**

---

**审计结论**: V2系统通过真实性审计，所有P0验收项有可复现的证据支持。3个真实BUG已修复并验证。系统可以进入下一阶段开发，但建议先完成上述3个确认项。
