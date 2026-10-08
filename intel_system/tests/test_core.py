"""
核心模块测试
"""

import pytest
from datetime import datetime
from src.core.schemas import (
    TaskContract, TaskStatus, CommitmentLevel, PermissionLevel,
    Evidence, EvidenceQuality, ForecastRecord, Claim
)
from src.core.config import get_settings, Settings
from src.core.database import Database


def test_task_contract_creation():
    """测试任务契约创建"""
    task = TaskContract(
        task_id="test-001",
        task_type="research",
        input_data={"query": "测试查询"},
        input_hash="abc123",
        method_version="v1.0",
        created_at=datetime.now(),
        status=TaskStatus.PENDING,
        commitment_level=CommitmentLevel.C,
        permission_level=PermissionLevel.L1
    )
    
    assert task.task_id == "test-001"
    assert task.task_type == "research"
    assert task.status == TaskStatus.PENDING
    assert task.commitment_level == CommitmentLevel.C


def test_evidence_creation():
    """测试证据创建"""
    evidence = Evidence(
        evidence_id="ev-001",
        source_url="https://example.com/article",
        source_quality=EvidenceQuality.A,
        content_hash="hash123",
        raw_content="测试内容",
        extracted_at=datetime.now(),
        credibility_score=0.8,
        relevance_score=0.7,
        diagnostic_score=0.6,
        task_id="task-001"
    )
    
    assert evidence.evidence_id == "ev-001"
    assert evidence.source_quality == EvidenceQuality.A
    assert evidence.credibility_score == 0.8


def test_settings_initialization():
    """测试配置初始化"""
    settings = get_settings()
    
    assert settings.debug is False
    assert settings.database.wal_mode is True
    assert settings.commitment.a_min_sample_size == 30
    assert settings.permission.monotonic is True


def test_forecast_record():
    """测试预测记录"""
    forecast = ForecastRecord(
        forecast_id="fc-001",
        event_description="测试事件",
        probability=0.7,
        time_range_start=datetime.now(),
        time_range_end=datetime(2025, 12, 31),
        falsifiable_anchor="如果X不发生则证伪",
        premises=["前提1", "前提2"],
        evidence_snapshot={"key": "value"},
        task_id="task-001"
    )
    
    assert forecast.probability == 0.7
    assert forecast.settled is False
    assert len(forecast.premises) == 2


def test_commitment_levels():
    """测试承诺等级枚举"""
    assert CommitmentLevel.A.value == "A"
    assert CommitmentLevel.BLOCKED.value == "BLOCKED"
    assert CommitmentLevel.C in [CommitmentLevel.A, CommitmentLevel.B, CommitmentLevel.C]


def test_permission_levels():
    """测试权限等级枚举"""
    assert PermissionLevel.L1.value == "L1"
    assert PermissionLevel.L3.value == "L3"
    assert PermissionLevel.L2 != PermissionLevel.L3
