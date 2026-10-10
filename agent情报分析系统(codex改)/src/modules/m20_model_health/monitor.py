"""
M20 模型健康模块
支持漂移检测、版本管理、健康检查
"""

import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class DriftReport:
    """漂移报告"""
    feature_name: str
    drift_score: float
    is_drifted: bool
    method: str
    threshold: float
    reference_mean: float
    current_mean: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ModelVersion:
    """模型版本"""
    version_id: str
    model_name: str
    created_at: datetime = field(default_factory=datetime.now)
    metrics: Dict[str, float] = field(default_factory=dict)
    is_active: bool = False
    config_hash: str = ""


class ModelHealthMonitor:
    """
    模型健康监控
    
    支持：
    - 数据漂移检测（PSI、KS检验）
    - 模型性能趋势
    - 版本管理
    - 异常告警
    """
    
    def __init__(self):
        self.versions: List[ModelVersion] = []
        self._reference_data: Dict[str, np.ndarray] = {}
        self.drift_history: List[DriftReport] = []
    
    def set_reference(self, feature_name: str, reference_data: np.ndarray):
        """设置参考数据"""
        self._reference_data[feature_name] = reference_data
    
    def detect_drift(self, feature_name: str, current_data: np.ndarray,
                    threshold: float = 0.2, method: str = "psi") -> DriftReport:
        """检测数据漂移"""
        reference = self._reference_data.get(feature_name)
        if reference is None:
            return DriftReport(
                feature_name=feature_name,
                drift_score=0.0,
                is_drifted=False,
                method=method,
                threshold=threshold,
                reference_mean=0.0,
                current_mean=float(np.mean(current_data))
            )
        
        if method == "psi":
            score = self._calculate_psi(reference, current_data)
        elif method == "ks":
            score = self._calculate_ks(reference, current_data)
        else:
            score = abs(float(np.mean(current_data) - np.mean(reference)))
        
        report = DriftReport(
            feature_name=feature_name,
            drift_score=score,
            is_drifted=score > threshold,
            method=method,
            threshold=threshold,
            reference_mean=float(np.mean(reference)),
            current_mean=float(np.mean(current_data))
        )
        
        self.drift_history.append(report)
        return report
    
    def _calculate_psi(self, reference: np.ndarray, current: np.ndarray, n_bins: int = 10) -> float:
        """计算PSI（群体稳定性指标）"""
        breakpoints = np.linspace(min(reference.min(), current.min()),
                                  max(reference.max(), current.max()),
                                  n_bins + 1)
        
        ref_hist, _ = np.histogram(reference, bins=breakpoints)
        cur_hist, _ = np.histogram(current, bins=breakpoints)
        
        ref_pct = ref_hist / len(reference)
        cur_pct = cur_hist / len(current)
        
        # 避免除零
        ref_pct = np.clip(ref_pct, 1e-6, None)
        cur_pct = np.clip(cur_pct, 1e-6, None)
        
        psi = np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct))
        return float(psi)
    
    def _calculate_ks(self, reference: np.ndarray, current: np.ndarray) -> float:
        """计算KS统计量"""
        combined = np.concatenate([reference, current])
        thresholds = np.sort(np.unique(combined))
        
        max_diff = 0
        for t in thresholds:
            ref_cdf = np.mean(reference <= t)
            cur_cdf = np.mean(current <= t)
            diff = abs(ref_cdf - cur_cdf)
            max_diff = max(max_diff, diff)
        
        return float(max_diff)
    
    def register_version(self, model_name: str, metrics: Dict[str, float],
                        is_active: bool = False) -> ModelVersion:
        """注册模型版本"""
        version = ModelVersion(
            version_id=hashlib.md5(f"{model_name}_{datetime.now()}".encode()).hexdigest()[:12],
            model_name=model_name,
            metrics=metrics,
            is_active=is_active
        )
        
        if is_active:
            for v in self.versions:
                v.is_active = False
        
        self.versions.append(version)
        return version
    
    def get_health_status(self) -> Dict[str, Any]:
        """获取健康状态"""
        recent_drifts = self.drift_history[-10:] if self.drift_history else []
        drifted_count = sum(1 for d in recent_drifts if d.is_drifted)
        
        if drifted_count == 0:
            status = HealthStatus.HEALTHY
        elif drifted_count <= 2:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.UNHEALTHY
        
        active_version = next((v for v in self.versions if v.is_active), None)
        
        return {
            "status": status.value,
            "drifted_features": drifted_count,
            "total_versions": len(self.versions),
            "active_version": active_version.version_id if active_version else None,
            "recent_drifts": [
                {"feature": d.feature_name, "score": d.drift_score, "is_drifted": d.is_drifted}
                for d in recent_drifts[-5:]
            ]
        }
