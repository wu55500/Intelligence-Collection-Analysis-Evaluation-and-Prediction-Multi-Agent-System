"""
M15 系统指标模块
支持系统监控、性能指标、健康检查
"""

import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque


@dataclass
class MetricPoint:
    """指标数据点"""
    metric_name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """
    指标采集器
    
    支持：
    - 计数器（Counter）
    - 仪表（Gauge）
    - 直方图（Histogram）
    - 滑动窗口
    """
    
    def __init__(self, max_points: int = 10000):
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, deque] = {}
        self._max_points = max_points
    
    def increment(self, name: str, value: float = 1.0):
        """计数器递增"""
        self._counters[name] = self._counters.get(name, 0) + value
    
    def set_gauge(self, name: str, value: float):
        """设置仪表值"""
        self._gauges[name] = value
    
    def record_histogram(self, name: str, value: float, window_size: int = 100):
        """记录直方图"""
        if name not in self._histograms:
            self._histograms[name] = deque(maxlen=window_size)
        self._histograms[name].append(value)
    
    def get_counter(self, name: str) -> float:
        return self._counters.get(name, 0)
    
    def get_gauge(self, name: str) -> float:
        return self._gauges.get(name, 0)
    
    def get_histogram_stats(self, name: str) -> Dict[str, float]:
        """获取直方图统计"""
        if name not in self._histograms or not self._histograms[name]:
            return {"count": 0, "mean": 0, "min": 0, "max": 0, "p50": 0, "p95": 0, "p99": 0}
        
        values = sorted(self._histograms[name])
        n = len(values)
        return {
            "count": n,
            "mean": sum(values) / n,
            "min": values[0],
            "max": values[-1],
            "p50": values[n // 2],
            "p95": values[int(n * 0.95)] if n > 1 else values[-1],
            "p99": values[int(n * 0.99)] if n > 1 else values[-1]
        }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有指标"""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {k: self.get_histogram_stats(k) for k in self._histograms}
        }


class SystemHealthMonitor:
    """系统健康监控"""
    
    def __init__(self, metrics: Optional[MetricsCollector] = None):
        self.metrics = metrics or MetricsCollector()
        self._checks: Dict[str, Any] = {}
    
    def register_check(self, name: str, check_func):
        """注册健康检查"""
        self._checks[name] = check_func
    
    def run_checks(self) -> Dict[str, Any]:
        """运行所有健康检查"""
        results = {}
        for name, func in self._checks.items():
            try:
                result = func()
                results[name] = {"status": "healthy" if result else "unhealthy", "detail": result}
            except Exception as e:
                results[name] = {"status": "error", "detail": str(e)}
        return results
    
    def record_request_time(self, endpoint: str, duration_ms: float):
        """记录请求耗时"""
        self.metrics.record_histogram(f"request_duration_{endpoint}", duration_ms)
        self.metrics.increment(f"request_count_{endpoint}")
    
    def get_health_summary(self) -> Dict[str, Any]:
        """健康摘要"""
        checks = self.run_checks()
        all_healthy = all(v["status"] == "healthy" for v in checks.values())
        
        return {
            "overall": "healthy" if all_healthy else "degraded",
            "checks": checks,
            "timestamp": datetime.now().isoformat()
        }
