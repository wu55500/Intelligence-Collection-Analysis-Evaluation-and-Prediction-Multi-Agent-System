# V2 真实性审计报告

## 审计原则

**不假设代码正确，只相信可复现的证据**

每个P0项必须提供：
- 代码位置（精确到行号）
- 可复现步骤（可执行的命令）
- 预期行为（明确定义）
- 实际行为（运行结果截图或日志）
- 测试证据（pytest输出）
- 修复状态（PASS/FAIL/PENDING）

---

## 统计核查

### 测试数量

| 测试文件 | 收集数量 | 通过数量 |
|---------|---------|---------|
| test_core.py | 6 | ? |
| test_modules.py | 8 | ? |
| test_services.py | 13 | ? |
| test_v2_integration.py | 24 | ? |
| **总计** | **51** | ? |

**结论**: 51 = 6 + 8 + 13 + 24 ✓

### 模块实现状态

| 模块 | 实现文件 | 代码行数 | __init__.py状态 | 可导入 |
|-----|---------|---------|---------------|--------|
| m1_collection | 1 | 494 | HAS_EXPORTS | ✓ |
| m2_governance | 1 | 313 | HAS_EXPORTS | ✓ |
| m3_eda | 1 | 389 | HAS_EXPORTS | ✓ |
| m4_features | 1 | 128 | HAS_EXPORTS | ✓ |
| m5_causal | 1 | 285 | HAS_EXPORTS | ✓ |
| m6_model | 1 | 110 | HAS_EXPORTS | ✓ |
| m7_eval | 1 | 107 | HAS_EXPORTS | ✓ |
| m8_forecast | 1 | 161 | HAS_EXPORTS | ✓ |
| m9_optimization | 1 | 112 | HAS_EXPORTS | ✓ |
| m10_alert | 1 | 228 | HAS_EXPORTS | ✓ |
| m11_knowledge | 1 | 275 | HAS_EXPORTS | ✓ |
| m12_evidence | 1 | 298 | HAS_EXPORTS | ✓ |
| m13_report | 1 | 379 | HAS_EXPORTS | ✓ |
| m14_permission | 1 | 219 | HAS_EXPORTS | ✓ |
| m15_metrics | 1 | 121 | HAS_EXPORTS | ✓ |
| m16_evaluation | 1 | 136 | HAS_EXPORTS | ✓ |
| m17_ops_algo | 1 | 110 | HAS_EXPORTS | ✓ |
| m18_simulation | 1 | 140 | HAS_EXPORTS | ✓ |
| m19_orchestrator | 0 | 0 | EMPTY | ⚠️ |
| m20_model_health | 1 | 173 | HAS_EXPORTS | ✓ |
| m21_commitment | 1 | 213 | HAS_EXPORTS | ✓ |

**发现问题**: m19_orchestrator的__init__.py为空，实际实现在src/services/orchestrator_v2.py

**结论**: 20/21模块可导入，m19在services层实现

### CI/CD状态

- GitHub Actions工作流文件: `.github/workflows/ci.yml` ✓
- 实际执行状态: ⚠️ 未验证（需要推送到GitHub后查看）

---

## P0-1: 验收闸门是否真正生效

### 测试场景

#### 场景1.1: 无效输出（空数据）

**代码位置**: `src/core/validation_gate.py:80-145`

**可复现步骤**:
```python
from src.core.validation_gate import ValidationGate, ModuleOutput, ModuleStatus

gate = ValidationGate()
output = ModuleOutput(
    module_name="m1_collection",
    status=ModuleStatus.SUCCESS,
    output_data={}  # 空数据
)
result = gate.validate(output)
print(f"Passed: {result.passed}")
print(f"Should block: {gate.should_block(result)}")
```

**预期行为**: 
- 采集模块无证据引用 → `passed=False`
- 关键模块失败 → `should_block=True`

**实际行为**: 待验证

**测试证据**: 待运行

**修复状态**: PENDING

---

#### 场景1.2: 缺失证据引用

**代码位置**: `src/core/validation_gate.py:113-117`

**可复现步骤**:
```python
output = ModuleOutput(
    module_name="m1_collection",
    status=ModuleStatus.SUCCESS,
    output_data={"count": 0}
)
result = gate.validate(output)
```

**预期行为**: `passed=False`（采集模块必须产生证据引用）

**实际行为**: 待验证

**修复状态**: PENDING

---

#### 场景1.3: 关键模块失败

**代码位置**: `src/core/validation_gate.py:124-125`

**可复现步骤**:
```python
output = ModuleOutput(
    module_name="m1_collection",  # 关键模块
    status=ModuleStatus.FAILED,
    errors=["connection timeout"]
)
result = gate.validate(output)
```

**预期行为**: 
- `passed=False`
- `should_block=True`

**实际行为**: 待验证

**修复状态**: PENDING

---

#### 场景1.4: 非关键模块失败（不应阻断）

**代码位置**: `src/core/validation_gate.py:43`

**可复现步骤**:
```python
output = ModuleOutput(
    module_name="m3_eda",  # 非关键模块
    status=ModuleStatus.FAILED,
    errors=["insufficient data"]
)
result = gate.validate(output)
```

**预期行为**: 
- `passed=False`
- `should_block=False`（非关键模块不阻断）

**实际行为**: 待验证

**修复状态**: PENDING

---

## P0-2: 检查点是否能跨进程恢复

### 测试场景

#### 场景2.1: 进程中断后恢复

**代码位置**: `src/services/checkpoint.py`

**可复现步骤**:
```bash
# 1. 启动任务
python -c "
from src.services.checkpoint import CheckpointService, Checkpoint
svc = CheckpointService()
cp = Checkpoint(task_id='recovery_test', step_name='collect')
svc.save_checkpoint(cp)
print(f'Created: {cp.checkpoint_id}')
"

# 2. 强制终止（模拟）

# 3. 新进程恢复
python -c "
from src.services.checkpoint import CheckpointService
svc = CheckpointService()
info = svc.get_recovery_info('recovery_test')
print(f'Can resume: {info[\"can_resume\"]}')
print(f'Last step: {info[\"last_completed\"]}')
"
```

**预期行为**: 
- 跨进程可以读取检查点
- `can_resume=True`

**实际行为**: 待验证

**修复状态**: PENDING

---

#### 场景2.2: 重复执行一致性

**代码位置**: `src/services/checkpoint.py:95-120`

**可复现步骤**:
```python
svc = CheckpointService()
cp1 = Checkpoint(task_id='dup_test', step_name='govern')
id1 = svc.save_checkpoint(cp1)

cp2 = Checkpoint(task_id='dup_test', step_name='govern')
id2 = svc.save_checkpoint(cp2)

# 应该覆盖而非新增
assert id1 == id2 or len(svc.get_task_checkpoints('dup_test')) == 1
```

**预期行为**: 幂等性保证

**实际行为**: 待验证

**修复状态**: PENDING

---

#### 场景2.3: 重试上限

**代码位置**: `src/services/checkpoint.py:165-180`

**可复现步骤**:
```python
svc = CheckpointService()
cp = Checkpoint(task_id='retry_test', step_name='eda', max_retries=3)
cp_id = svc.save_checkpoint(cp)

for i in range(5):  # 超过max_retries
    svc.mark_failed(cp_id, f"error {i}")
    
final = svc.get_checkpoint(cp_id)
print(f"Status: {final.status}")  # 应该是failed
print(f"Retry count: {final.retry_count}")  # 应该是5
```

**预期行为**: 超过max_retries后status=failed

**实际行为**: 待验证

**修复状态**: PENDING

---

#### 场景2.4: 新旧结果留痕

**代码位置**: `src/services/orchestrator_v2.py:200-220`

**可复现步骤**:
```python
# 需要测试rerun_step功能
# 保留StepDiff记录
```

**预期行为**: 每次重新运行保留差异

**实际行为**: 待验证

**修复状态**: PENDING

---

## P0-3: 验证红队是否真正独立

### 测试场景

#### 场景3.1: 发现伪独立来源

**代码位置**: `src/services/red_team.py:120-160`

**可复现步骤**:
```python
from src.services.red_team import IndependentVerifier
import asyncio

async def test():
    v = IndependentVerifier()
    # 所有证据来自同一域名（伪独立）
    evidence = [
        {"source_url": "https://example.com/a", "is_contradictory": False},
        {"source_url": "https://example.com/b", "is_contradictory": False},
        {"source_url": "https://example.com/c", "is_contradictory": False},
    ]
    report = await v.verify(
        task_id="t1",
        claim="测试结论",
        commitment_level="A",
        evidence_list=evidence,
        methodology={"method": "correlation"}
    )
    print(f"Result: {report.overall_result}")
    print(f"Findings: {len(report.findings)}")
    
    # 找到source_independence检查
    source_finding = next(f for f in report.findings if f.check_type == "source_independence")
    print(f"Source check: {source_finding.result}")
    
asyncio.run(test())
```

**预期行为**: 
- 识别出所有来源相同
- `source_independence`检查结果为`CONTRADICTED`或`WEAKENED`

**实际行为**: 待验证

**修复状态**: PENDING

---

#### 场景3.2: 识别方法不适当

**代码位置**: `src/services/red_team.py:200-240`

**可复现步骤**:
```python
async def test():
    v = IndependentVerifier()
    evidence = [
        {"source_url": "https://a.com", "is_contradictory": False},
    ]
    # 用correlation方法声称因果
    report = await v.verify(
        task_id="t2",
        claim="X导致Y",  # 声称因果
        commitment_level="A",
        evidence_list=evidence,
        methodology={"method": "correlation"}  # 方法不当
    )
    
    method_finding = next(f for f in report.findings if f.check_type == "methodology")
    print(f"Method check: {method_finding.result}")
    print(f"Description: {method_finding.description}")
    
asyncio.run(test())
```

**预期行为**: 
- 识别出"correlation方法不能声称因果"
- `methodology`检查结果为`WEAKENED`

**实际行为**: 待验证

**修复状态**: PENDING

---

#### 场景3.3: 红队阻断高置信度反驳

**代码位置**: `src/services/red_team.py:280-300`

**可复现步骤**:
```python
async def test():
    v = IndependentVerifier()
    # 多个检查项发现严重问题
    evidence = [
        {"source_url": "https://example.com", "is_contradictory": False},
    ]
    report = await v.verify(
        task_id="t3",
        claim="无锚点结论",
        commitment_level="A",
        evidence_list=evidence,
        methodology={"method": "correlation"}
    )
    
    print(f"Should block: {report.should_block}")
    print(f"Block reason: {report.block_reason}")
    
asyncio.run(test())
```

**预期行为**: 缺少证伪锚点 → `should_block=True`

**实际行为**: 待验证

**修复状态**: PENDING

---

## P0-4: 验证预测闭环与权限边界

### 测试场景

#### 场景4.1: 预测登记→到期结算→回测追溯

**代码位置**: 
- `src/services/forecast_service.py`
- `src/core/database.py`

**可复现步骤**:
```python
from src.services.forecast_service import ForecastService
from datetime import datetime, timedelta

svc = ForecastService()

# 1. 登记预测
fc = svc.register_forecast(
    task_id="fc_test",
    event_description="7天内会下雨",
    probability=0.7,
    time_range_start=datetime.now(),
    time_range_end=datetime.now() + timedelta(days=7),
    falsifiable_anchor="如果7天内未下雨则证伪",
    premises=["气象数据显示湿度80%"],
    evidence_snapshot={"source": "weather.com"}
)
print(f"Registered: {fc.forecast_id}")

# 2. 模拟到期
# （需要等待7天或修改time_range_end为过去）

# 3. 结算
result = svc.settle_forecast(
    forecast_id=fc.forecast_id,
    actual_outcome=True  # 实际下雨了
)
print(f"Outcome: {result.outcome}")  # hit
print(f"Brier score: {result.brier_score}")

# 4. 回测
brier = svc.calculate_brier_score()
print(f"Overall Brier: {brier.score}")
print(f"Calibrated: {brier.calibrated}")
```

**预期行为**: 
- 预测可登记
- 可结算
- Brier Score可计算
- 校准度可评估

**实际行为**: 待验证

**修复状态**: PENDING

---

#### 场景4.2: 权限越权测试

**代码位置**: `src/services/permission_service.py`

**可复现步骤**:
```python
from src.services.permission_service import PermissionService
from src.core.schemas import PermissionLevel

svc = PermissionService()

# 尝试用L1权限执行危险操作
result = svc.can_execute(
    action_type="delete",
    action_description="删除所有数据",  # 包含危险关键词
    current_level=PermissionLevel.L1
)

print(f"Allowed: {result['allowed']}")  # 应该False
print(f"Required level: {result['required_level']}")  # 应该L3
```

**预期行为**: 
- `allowed=False`
- `required_level=L3`

**实际行为**: 待验证

**修复状态**: PENDING

---

#### 场景4.3: 模型路由失败时状态明确

**代码位置**: `src/agents/router/smart_router.py`

**可复现步骤**:
```python
from src.agents.router import SmartRouter, TaskType

router = SmartRouter()

# 设置极严格的约束
decision = router.route(
    TaskType.GENERAL,
    max_cost=0.0001,  # 极低成本
    max_latency_ms=100  # 极低延迟
)

if decision is None:
    print("No model available under constraints")
else:
    print(f"Selected: {decision.selected_model.model_name}")
```

**预期行为**: 无可用模型时返回None或明确状态

**实际行为**: 待验证

**修复状态**: PENDING

---

#### 场景4.4: 路由失败审计记录

**代码位置**: `src/agents/router/smart_router.py:150-180`

**可复现步骤**:
```python
# 需要检查路由决策是否记录审计日志
```

**预期行为**: 每次路由决策有审计记录

**实际行为**: 待验证

**修复状态**: PENDING

---

## 审计执行计划

### 第1轮：运行所有P0测试

```bash
# 运行现有测试
python -m pytest tests/ -v

# 运行新增的审计测试
python -m pytest tests/test_v2_audit.py -v
```

### 第2轮：手动验证每个场景

对每个P0场景执行可复现步骤，记录实际行为。

### 第3轮：生成审计报告

填写每个场景的"实际行为"和"测试证据"，更新"修复状态"。

### 第4轮：修复发现的问题

对所有FAIL项进行修复，然后重新验证。

---

## 审计结论（待填写）

- **P0-1 验收闸门**: ?/4 PASS
- **P0-2 检查点恢复**: ?/4 PASS
- **P0-3 红队独立性**: ?/3 PASS
- **P0-4 预测与权限**: ?/4 PASS

**总计**: ?/15 PASS

**是否允许进入新功能开发**: 待P0全部通过后决定

---

## 附录：代码审查清单

- [ ] m19_orchestrator的__init__.py为何为空？
- [ ] 79个Python文件是否都有测试覆盖？
- [ ] CI/CD工作流是否实际执行成功？
- [ ] 所有模块的调用链是否完整？
- [ ] 是否有mock数据冒充真实实现？

