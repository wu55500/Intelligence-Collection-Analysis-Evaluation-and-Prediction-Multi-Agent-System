"""
M3 EDA探索性分析模块

P0需求：
- 统计描述与可视化
- 分布检查
- 异常值识别
- 相关性初步分析
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from datetime import datetime


@dataclass
class StatisticalSummary:
    """统计摘要"""
    count: int
    mean: float
    median: float
    std: float
    min: float
    max: float
    q1: float
    q3: float
    iqr: float
    skewness: float
    kurtosis: float


@dataclass
class OutlierDetection:
    """异常值检测结果"""
    method: str  # "iqr", "zscore"
    outlier_indices: List[int]
    outlier_values: List[float]
    threshold: float
    total_count: int
    outlier_ratio: float


@dataclass
class CorrelationResult:
    """相关性分析结果"""
    pearson_r: Optional[float]
    pearson_p: Optional[float]
    spearman_r: Optional[float]
    spearman_p: Optional[float]
    interpretation: str
    sample_size: int


@dataclass
class EDAResult:
    """EDA完整结果"""
    statistical_summary: StatisticalSummary
    outlier_detection: OutlierDetection
    correlation_result: Optional[CorrelationResult]
    distribution_check: Dict[str, Any]
    recommendations: List[str]
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class EDAAnalyzer:
    """
    EDA探索性分析器
    
    职责：
    1. 统计描述
    2. 异常值检测（IQR法、Z-score法）
    3. 分布检查
    4. 相关性分析（Pearson + Spearman双系数）
    """
    
    def analyze(
        self,
        data: List[float],
        second_data: Optional[List[float]] = None
    ) -> EDAResult:
        """
        执行完整EDA分析
        
        Args:
            data: 主数据序列
            second_data: 第二数据序列（用于相关性分析）
        """
        if not data:
            raise ValueError("数据不能为空")
        
        # 1. 统计描述
        summary = self._calculate_summary(data)
        
        # 2. 异常值检测
        outliers = self._detect_outliers_iqr(data)
        
        # 3. 分布检查
        dist_check = self._check_distribution(data)
        
        # 4. 相关性分析（如果有第二数据）
        corr_result = None
        if second_data and len(second_data) == len(data):
            corr_result = self._calculate_correlation(data, second_data)
        
        # 5. 生成建议
        recommendations = self._generate_recommendations(summary, outliers, corr_result)
        
        return EDAResult(
            statistical_summary=summary,
            outlier_detection=outliers,
            correlation_result=corr_result,
            distribution_check=dist_check,
            recommendations=recommendations
        )
    
    def _calculate_summary(self, data: List[float]) -> StatisticalSummary:
        """计算统计摘要"""
        arr = np.array(data)
        
        q1 = float(np.percentile(arr, 25))
        q3 = float(np.percentile(arr, 75))
        
        return StatisticalSummary(
            count=len(data),
            mean=float(np.mean(arr)),
            median=float(np.median(arr)),
            std=float(np.std(arr, ddof=1)) if len(data) > 1 else 0.0,
            min=float(np.min(arr)),
            max=float(np.max(arr)),
            q1=q1,
            q3=q3,
            iqr=q3 - q1,
            skewness=float(self._calculate_skewness(arr)),
            kurtosis=float(self._calculate_kurtosis(arr))
        )
    
    def _detect_outliers_iqr(
        self,
        data: List[float],
        multiplier: float = 1.5
    ) -> OutlierDetection:
        """
        IQR法检测异常值
        
        规则：超出Q1-1.5*IQR 或 Q3+1.5*IQR 的点视为异常
        """
        arr = np.array(data)
        q1 = np.percentile(arr, 25)
        q3 = np.percentile(arr, 75)
        iqr = q3 - q1
        
        lower_bound = q1 - multiplier * iqr
        upper_bound = q3 + multiplier * iqr
        
        outlier_mask = (arr < lower_bound) | (arr > upper_bound)
        outlier_indices = np.where(outlier_mask)[0].tolist()
        outlier_values = arr[outlier_mask].tolist()
        
        return OutlierDetection(
            method="iqr",
            outlier_indices=outlier_indices,
            outlier_values=outlier_values,
            threshold=multiplier,
            total_count=len(data),
            outlier_ratio=len(outlier_indices) / len(data) if data else 0.0
        )
    
    def _detect_outliers_zscore(
        self,
        data: List[float],
        threshold: float = 3.0
    ) -> OutlierDetection:
        """Z-score法检测异常值"""
        arr = np.array(data)
        mean = np.mean(arr)
        std = np.std(arr, ddof=1)
        
        if std == 0:
            return OutlierDetection(
                method="zscore",
                outlier_indices=[],
                outlier_values=[],
                threshold=threshold,
                total_count=len(data),
                outlier_ratio=0.0
            )
        
        z_scores = np.abs((arr - mean) / std)
        outlier_mask = z_scores > threshold
        outlier_indices = np.where(outlier_mask)[0].tolist()
        outlier_values = arr[outlier_mask].tolist()
        
        return OutlierDetection(
            method="zscore",
            outlier_indices=outlier_indices,
            outlier_values=outlier_values,
            threshold=threshold,
            total_count=len(data),
            outlier_ratio=len(outlier_indices) / len(data) if data else 0.0
        )
    
    def _check_distribution(self, data: List[float]) -> Dict[str, Any]:
        """检查数据分布"""
        arr = np.array(data)
        
        # 简化的正态性检查
        skewness = abs(self._calculate_skewness(arr))
        kurtosis = abs(self._calculate_kurtosis(arr))
        
        # 经验规则：偏度<2且峰度<7近似正态
        is_approx_normal = skewness < 2 and kurtosis < 7
        
        return {
            "skewness": float(skewness),
            "kurtosis": float(kurtosis),
            "is_approx_normal": is_approx_normal,
            "recommendation": "近似正态分布" if is_approx_normal else "非正态分布，建议使用非参数方法"
        }
    
    def _calculate_correlation(
        self,
        x: List[float],
        y: List[float]
    ) -> CorrelationResult:
        """
        计算相关性
        
        规则：Pearson + Spearman双系数同报，分叉=分布异常信号
        """
        x_arr = np.array(x)
        y_arr = np.array(y)
        
        # Pearson相关
        pearson_r, pearson_p = self._pearson_correlation(x_arr, y_arr)
        
        # Spearman相关
        spearman_r, spearman_p = self._spearman_correlation(x_arr, y_arr)
        
        # 解释
        interpretation = self._interpret_correlation(pearson_r, spearman_r)
        
        return CorrelationResult(
            pearson_r=pearson_r,
            pearson_p=pearson_p,
            spearman_r=spearman_r,
            spearman_p=spearman_p,
            interpretation=interpretation,
            sample_size=len(x)
        )
    
    def _pearson_correlation(
        self,
        x: np.ndarray,
        y: np.ndarray
    ) -> Tuple[float, float]:
        """计算Pearson相关系数"""
        n = len(x)
        if n < 2:
            return 0.0, 1.0
        
        mean_x = np.mean(x)
        mean_y = np.mean(y)
        
        numerator = np.sum((x - mean_x) * (y - mean_y))
        denominator = np.sqrt(np.sum((x - mean_x)**2) * np.sum((y - mean_y)**2))
        
        if denominator == 0:
            return 0.0, 1.0
        
        r = numerator / denominator
        
        # 简化的p值计算（使用t分布近似）
        t_stat = r * np.sqrt((n - 2) / (1 - r**2 + 1e-10))
        # 这里简化处理，实际应该用scipy.stats
        p_value = min(1.0, 2.0 * np.exp(-0.717 * abs(t_stat) - 0.416 * t_stat**2))
        
        return float(r), float(p_value)
    
    def _spearman_correlation(
        self,
        x: np.ndarray,
        y: np.ndarray
    ) -> Tuple[float, float]:
        """计算Spearman相关系数（基于秩次）"""
        # 转换为秩次
        rank_x = self._calculate_ranks(x)
        rank_y = self._calculate_ranks(y)
        
        return self._pearson_correlation(rank_x, rank_y)
    
    def _calculate_ranks(self, arr: np.ndarray) -> np.ndarray:
        """计算秩次"""
        temp = arr.argsort()
        ranks = np.empty_like(temp, dtype=float)
        ranks[temp] = np.arange(len(arr)) + 1
        return ranks
    
    def _calculate_skewness(self, arr: np.ndarray) -> float:
        """计算偏度"""
        n = len(arr)
        if n < 3:
            return 0.0
        
        mean = np.mean(arr)
        std = np.std(arr, ddof=1)
        
        if std == 0:
            return 0.0
        
        skewness = (n / ((n - 1) * (n - 2))) * np.sum(((arr - mean) / std)**3)
        return float(skewness)
    
    def _calculate_kurtosis(self, arr: np.ndarray) -> float:
        """计算峰度"""
        n = len(arr)
        if n < 4:
            return 0.0
        
        mean = np.mean(arr)
        std = np.std(arr, ddof=1)
        
        if std == 0:
            return 0.0
        
        kurtosis = ((n * (n + 1)) / ((n - 1) * (n - 2) * (n - 3))) * \
                   np.sum(((arr - mean) / std)**4) - \
                   (3 * (n - 1)**2) / ((n - 2) * (n - 3))
        
        return float(kurtosis)
    
    def _interpret_correlation(
        self,
        pearson_r: float,
        spearman_r: float
    ) -> str:
        """解释相关性结果"""
        # 检查Pearson和Spearman是否分叉
        divergence = abs(pearson_r - spearman_r)
        
        if divergence > 0.3:
            return f"相关系数分叉（Pearson={pearson_r:.3f}, Spearman={spearman_r:.3f}），可能存在分布异常或非线性关系"
        
        # 解释强度
        abs_r = abs(pearson_r)
        if abs_r < 0.3:
            strength = "弱"
        elif abs_r < 0.7:
            strength = "中等"
        else:
            strength = "强"
        
        direction = "正" if pearson_r > 0 else "负"
        
        return f"{strength}{direction}相关（r={pearson_r:.3f}）"
    
    def _generate_recommendations(
        self,
        summary: StatisticalSummary,
        outliers: OutlierDetection,
        correlation: Optional[CorrelationResult]
    ) -> List[str]:
        """生成分析建议"""
        recommendations = []
        
        # 样本量检查
        if summary.count < 30:
            recommendations.append(f"样本量较小（n={summary.count}），结论可能不稳定，建议作为方向性证据")
        
        # 异常值建议
        if outliers.outlier_ratio > 0.1:
            recommendations.append(f"异常值比例较高（{outliers.outlier_ratio:.1%}），建议检查数据质量或考虑稳健统计方法")
        
        # 偏度建议
        if abs(summary.skewness) > 2:
            recommendations.append(f"数据偏度较大（{summary.skewness:.2f}），建议使用非参数方法或数据转换")
        
        # 相关性建议
        if correlation:
            if correlation.pearson_p and correlation.pearson_p < 0.05:
                recommendations.append("相关性统计显著，但注意相关不等于因果")
            else:
                recommendations.append("相关性不显著，可能需要更大样本量")
        
        return recommendations
