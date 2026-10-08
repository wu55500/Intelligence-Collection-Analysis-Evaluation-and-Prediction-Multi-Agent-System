"""
服务层测试
"""

import pytest
import os
import tempfile
from datetime import datetime, timedelta

from src.core.schemas import Evidence, EvidenceQuality, CommitmentLevel, PermissionLevel
from src.core.database import Database
from src.services.commitment_engine import CommitmentEngine, CommitmentInput
from src.services.permission_service import PermissionService
from src.services.forecast_service import ForecastService


@pytest.fixture
def fresh_db():
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    db = Database(db_path=path)
    yield db
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def commitment_engine(fresh_db):
    engine = CommitmentEngine()
    engine.db = fresh_db
    return engine


@pytest.fixture
def permission_service(fresh_db):
    svc = PermissionService()
    svc.db = fresh_db
    return svc


@pytest.fixture
def forecast_service(fresh_db):
    svc = ForecastService()
    svc.db = fresh_db
    return svc


# ===== Commitment Engine =====

def test_commitment_engine_a_level(commitment_engine):
    evidence_list = [
        Evidence(
            evidence_id=f"ev-{i}",
            source_url=f"https://example{i}.com",
            source_quality=EvidenceQuality.S,
            content_hash=f"hash{i}",
            raw_content=f"内容{i}",
            extracted_at=datetime.now(),
            credibility_score=0.9,
            relevance_score=0.8,
            diagnostic_score=0.7,
            task_id="task-001"
        )
        for i in range(5)
    ]

    input_data = CommitmentInput(
        evidence_list=evidence_list,
        sample_size=50,
        has_feedback_loop=True,
        feedback_count=5,
        is_contradicted=False,
        is_expired=False,
        single_source=False,
        data_quality_level=EvidenceQuality.S,
    )

    decision = commitment_engine.evaluate(input_data)
    assert decision.level == CommitmentLevel.A


def test_commitment_engine_blocked(commitment_engine):
    input_data = CommitmentInput(evidence_list=[], sample_size=None)
    decision = commitment_engine.evaluate(input_data)
    assert decision.level == CommitmentLevel.BLOCKED


def test_commitment_engine_single_source(commitment_engine):
    ev = Evidence(
        evidence_id="ev-1",
        source_url="https://example.com",
        source_quality=EvidenceQuality.A,
        content_hash="h1", raw_content="x",
        extracted_at=datetime.now(),
        credibility_score=0.8,
        relevance_score=0.7,
        diagnostic_score=0.6,
        task_id="t1"
    )
    decision = commitment_engine.evaluate(CommitmentInput(
        evidence_list=[ev], sample_size=10, single_source=True
    ))
    assert decision.level == CommitmentLevel.C


# ===== Permission Service =====

def test_permission_dangerous_action(permission_service):
    result = permission_service.can_execute(
        action_type="delete",
        action_description="删除所有数据",
        current_level=PermissionLevel.L2
    )
    assert result["allowed"] is False
    assert result["required_level"] == PermissionLevel.L3


def test_permission_high_rpn_l3(permission_service):
    """高RPN操作需要L3，L2不够"""
    result = permission_service.can_execute(
        action_type="modify",
        action_description="批量修改系统配置",
        current_level=PermissionLevel.L2
    )
    # RPN=3*5*8=120 >= 100 → 需要L3
    assert result["required_level"] == PermissionLevel.L3


def test_permission_tightening(permission_service):
    assert permission_service.get_current_max_level() == PermissionLevel.L1
    assert permission_service.tighten_permission(PermissionLevel.L3) is True
    assert permission_service.get_current_max_level() == PermissionLevel.L3
    # 不能放宽
    assert permission_service.tighten_permission(PermissionLevel.L1) is False
    assert permission_service.get_current_max_level() == PermissionLevel.L3


def test_permission_audit_log(permission_service):
    """权限检查应该记录审计日志"""
    permission_service.can_execute(
        action_type="delete",
        action_description="删除数据",
        current_level=PermissionLevel.L1
    )
    logs = permission_service.db.get_audit_logs()
    assert any("permission_check" in l.action for l in logs)


# ===== Forecast Service =====

def test_forecast_registration(forecast_service):
    fc = forecast_service.register_forecast(
        task_id="task-001",
        event_description="测试事件",
        probability=0.7,
        time_range_start=datetime.now(),
        time_range_end=datetime.now() + timedelta(days=30),
        falsifiable_anchor="如果X不发生则证伪",
        premises=["前提1"],
        evidence_snapshot={"key": "val"}
    )
    assert fc.forecast_id is not None
    assert fc.probability == 0.7
    assert fc.settled is False


def test_forecast_no_duplicate(forecast_service):
    fc1 = forecast_service.register_forecast(
        task_id="task-001",
        event_description="Test",
        probability=0.7,
        time_range_start=datetime.now(),
        time_range_end=datetime.now() + timedelta(days=30),
        falsifiable_anchor="anchor",
        premises=[],
        evidence_snapshot={}
    )
    # 重复登记同一个forecast_id应该失败
    from src.core.schemas import ForecastRecord
    fc2 = ForecastRecord(
        forecast_id=fc1.forecast_id,
        event_description="Duplicate",
        probability=0.5,
        time_range_start=datetime.now(),
        time_range_end=datetime.now() + timedelta(days=30),
        falsifiable_anchor="anchor2",
        premises=[],
        evidence_snapshot={},
        task_id="task-002"
    )
    with pytest.raises(ValueError, match="已存在"):
        forecast_service.db.register_forecast(fc2)


def test_forecast_invalid_probability(forecast_service):
    with pytest.raises(ValueError):
        forecast_service.register_forecast(
            task_id="task-001",
            event_description="Test",
            probability=1.5,  # > 1
            time_range_start=datetime.now(),
            time_range_end=datetime.now() + timedelta(days=7),
            falsifiable_anchor="anchor",
            premises=[],
            evidence_snapshot={}
        )


def test_forecast_settlement(forecast_service):
    fc = forecast_service.register_forecast(
        task_id="task-001",
        event_description="Test event",
        probability=0.8,
        time_range_start=datetime.now(),
        time_range_end=datetime.now() + timedelta(days=7),
        falsifiable_anchor="test anchor",
        premises=[],
        evidence_snapshot={}
    )

    result = forecast_service.settle_forecast(
        forecast_id=fc.forecast_id,
        actual_outcome=True
    )
    assert result.outcome == "hit"
    assert result.brier_score is not None
    assert result.brier_score >= 0


def test_forecast_miss(forecast_service):
    fc = forecast_service.register_forecast(
        task_id="task-001",
        event_description="Test",
        probability=0.8,
        time_range_start=datetime.now(),
        time_range_end=datetime.now() + timedelta(days=7),
        falsifiable_anchor="anchor",
        premises=[],
        evidence_snapshot={}
    )
    result = forecast_service.settle_forecast(fc.forecast_id, actual_outcome=False)
    assert result.outcome == "miss"


def test_brier_score(forecast_service):
    settled_fcs = []
    for i in range(5):
        fc = forecast_service.register_forecast(
            task_id=f"task-{i}",
            event_description=f"Event {i}",
            probability=0.6,
            time_range_start=datetime.now(),
            time_range_end=datetime.now() + timedelta(days=7),
            falsifiable_anchor=f"anchor{i}",
            premises=[],
            evidence_snapshot={}
        )
        forecast_service.settle_forecast(fc.forecast_id, actual_outcome=(i % 2 == 0))
        settled_fcs.append(fc)

    # 需要手动传入已结算的预测记录
    # 由于settle后状态变更，重新构建带settled状态的记录
    from src.core.schemas import ForecastRecord
    fc_records = []
    for fc in settled_fcs:
        fc_records.append(ForecastRecord(
            forecast_id=fc.forecast_id,
            event_description=fc.event_description,
            probability=fc.probability,
            time_range_start=fc.time_range_start,
            time_range_end=fc.time_range_end,
            falsifiable_anchor=fc.falsifiable_anchor,
            premises=fc.premises,
            registered_at=fc.registered_at,
            settled=True,
            outcome="hit" if fc.forecast_id == settled_fcs[0].forecast_id or fc.forecast_id == settled_fcs[2].forecast_id or fc.forecast_id == settled_fcs[4].forecast_id else "miss",
            evidence_snapshot=fc.evidence_snapshot,
            task_id=fc.task_id
        ))

    result = forecast_service.calculate_brier_score(fc_records)
    assert result.count == 5
    assert 0 <= result.score <= 1
