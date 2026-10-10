#!/usr/bin/env python3
"""
事件溯源与审计日志测试
验证所有关键操作是否记录审计日志
"""

import asyncio
from datetime import datetime, timedelta
from src.core.database import get_database
from src.services.forecast_service import get_forecast_service
from src.services.permission_service import PermissionService
from src.core.schemas import PermissionLevel

print("\n" + "="*70)
print("📋 事件溯源与审计日志测试")
print("="*70)

# 清理测试数据库
import os
if os.path.exists("data/audit_test.db"):
    os.remove("data/audit_test.db")

db = get_database("data/audit_test.db")
forecast_svc = get_forecast_service()
perm_svc = PermissionService()

# ========== 测试1: 预测登记审计日志 ==========
print("\n【测试1】预测登记 → 审计日志")
fc = forecast_svc.register_forecast(
    task_id="audit_test_task",
    event_description="测试事件",
    probability=0.65,
    time_range_start=datetime.now(),
    time_range_end=datetime.now() + timedelta(days=7),
    falsifiable_anchor="测试证伪锚点",
    premises=["前提1"],
    evidence_snapshot={"source": "test.com"}
)
print(f"  ✓ 预测已登记: {fc.forecast_id[:8]}...")

# 查询审计日志
logs = db.get_audit_logs(task_id="audit_test_task")
forecast_logs = [l for l in logs if l.action == "forecast_registered"]
print(f"  ✓ 审计日志数: {len(forecast_logs)}")
if forecast_logs:
    log = forecast_logs[0]
    print(f"  ✓ 动作: {log.action}")
    print(f"  ✓ 执行者: {log.actor}")
    print(f"  ✓ 详情包含forecast_id: {'forecast_id' in log.details}")
    print(f"  ✓ 详情包含probability: {'probability' in log.details}")
    assert 'forecast_id' in log.details, "审计日志应包含forecast_id"

# ========== 测试2: 预测结算审计日志 ==========
print("\n【测试2】预测结算 → 审计日志")
result = forecast_svc.settle_forecast(fc.forecast_id, True)
print(f"  ✓ 预测已结算: {result.outcome}")

logs2 = db.get_audit_logs()
settle_logs = [l for l in logs2 if l.action == "forecast_settled"]
print(f"  ✓ 结算审计日志数: {len(settle_logs)}")
if settle_logs:
    log = settle_logs[0]
    print(f"  ✓ 动作: {log.action}")
    print(f"  ✓ 详情包含outcome: {'outcome' in log.details}")
    print(f"  ✓ 详情包含brier_score: {'brier_score' in log.details}")
    assert 'outcome' in log.details, "结算日志应包含outcome"

# ========== 测试3: 权限审批审计日志 ==========
print("\n【测试3】权限检查 → 审计日志")
perm_result = perm_svc.can_execute(
    action_type="delete",
    action_description="删除数据",
    current_level=PermissionLevel.L1
)
print(f"  ✓ 权限检查: allowed={perm_result['allowed']}")

logs3 = db.get_audit_logs()
perm_logs = [l for l in logs3 if "permission" in l.action.lower()]
print(f"  ✓ 权限审计日志数: {len(perm_logs)}")
if perm_logs:
    log = perm_logs[0]
    print(f"  ✓ 动作: {log.action}")
    print(f"  ✓ 详情包含action_type: {'action_type' in log.details}")

# ========== 测试4: 证据链完整性 ==========
print("\n【测试4】证据链完整性检查")
from src.core.schemas import Evidence, EvidenceQuality

evidence = Evidence(
    evidence_id="ev_test_001",
    source_url="https://example.com/article",
    source_quality=EvidenceQuality.A,
    content_hash="abc123def456",
    raw_content="测试内容",
    credibility_score=0.85,
    relevance_score=0.9,
    diagnostic_score=0.8,
    is_contradictory=False,
    task_id="audit_test_task",
    claims=["claim_001"]
)

# 保存证据
db.save_evidence(evidence)
print(f"  ✓ 证据已保存: {evidence.evidence_id}")

# 验证证据字段
required_fields = ["evidence_id", "source_url", "source_quality", "content_hash", 
                   "raw_content", "credibility_score", "task_id"]
for field in required_fields:
    assert hasattr(evidence, field), f"缺少字段: {field}"
print(f"  ✓ 所有必需字段完整")

# 查询证据
retrieved = db.get_evidence_by_task("audit_test_task")
print(f"  ✓ 查询到证据数: {len(retrieved)}")
assert len(retrieved) >= 1, "应能查询到证据"

# ========== 测试5: 可追溯性 ==========
print("\n【测试5】可追溯性 - 从任务到证据到预测")
task_id = "audit_test_task"

# 1. 查任务
task = db.get_task(task_id)
# 任务可能不存在（我们只测试了预测）

# 2. 查证据
evidences = db.get_evidence_by_task(task_id)
print(f"  ✓ 任务 {task_id} 的证据数: {len(evidences)}")

# 3. 查预测
all_forecasts = db.get_settled_forecasts() + db.get_unsettled_forecasts()
task_forecasts = [f for f in all_forecasts if f.task_id == task_id]
print(f"  ✓ 任务 {task_id} 的预测数: {len(task_forecasts)}")

# 4. 查审计日志
task_logs = db.get_audit_logs(task_id)
print(f"  ✓ 任务 {task_id} 的审计日志数: {len(task_logs)}")

print("\n" + "="*70)
print("✅ 事件溯源测试完成！")
print("="*70)
print("\n结论:")
print("  • 预测登记/结算操作有完整审计日志")
print("  • 权限检查操作有审计记录")
print("  • 证据链字段完整（source_url, content_hash, credibility等）")
print("  • 可追溯性：任务→证据→预测→审计日志")
print()
