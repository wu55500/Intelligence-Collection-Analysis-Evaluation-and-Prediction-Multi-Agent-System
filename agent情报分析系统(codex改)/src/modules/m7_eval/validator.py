"""
M7 模型评估模块
支持模型评估、性能指标、诊断分析
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class EvaluationResult:
    """评估结果"""
    metric_name: str
    metric_value: float
    is_acceptable: bool
    threshold: float
    timestamp: datetime = datetime.now()


class ModelEvaluator:
    """
    模型评估器
    
    支持：
    - 回归指标：MSE、RMSE、MAE、R²
    - 分类指标：准确率、召回率、F1、AUC
    - 诊断分析：残差分析、过拟合检测
    """
    
    def __init__(self):
        self.results: List[EvaluationResult] = []
    
    def evaluate_regression(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, EvaluationResult]:
        """评估回归模型"""
        results = {}
        
        # MSE
        mse = np.mean((y_true - y_pred) ** 2)
        results['mse'] = EvaluationResult('MSE', mse, mse < 1.0, 1.0)
        
        # RMSE
        rmse = np.sqrt(mse)
        results['rmse'] = EvaluationResult('RMSE', rmse, rmse < 1.0, 1.0)
        
        # MAE
        mae = np.mean(np.abs(y_true - y_pred))
        results['mae'] = EvaluationResult('MAE', mae, mae < 0.5, 0.5)
        
        # R²
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        results['r2'] = EvaluationResult('R²', r2, r2 > 0.7, 0.7)
        
        self.results.extend(results.values())
        return results
    
    def evaluate_classification(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, EvaluationResult]:
        """评估分类模型"""
        results = {}
        
        # 准确率
        accuracy = np.mean(y_true == y_pred)
        results['accuracy'] = EvaluationResult('Accuracy', accuracy, accuracy > 0.8, 0.8)
        
        # 精确率
        tp = np.sum((y_true == 1) & (y_pred == 1))
        fp = np.sum((y_true == 0) & (y_pred == 1))
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        results['precision'] = EvaluationResult('Precision', precision, precision > 0.8, 0.8)
        
        # 召回率
        fn = np.sum((y_true == 1) & (y_pred == 0))
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        results['recall'] = EvaluationResult('Recall', recall, recall > 0.8, 0.8)
        
        # F1
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        results['f1'] = EvaluationResult('F1', f1, f1 > 0.8, 0.8)
        
        self.results.extend(results.values())
        return results
    
    def check_overfitting(self, train_score: float, val_score: float, threshold: float = 0.1) -> bool:
        """检查过拟合"""
        gap = train_score - val_score
        return gap > threshold
    
    def analyze_residuals(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Any]:
        """残差分析"""
        residuals = y_true - y_pred
        
        return {
            'mean': float(np.mean(residuals)),
            'std': float(np.std(residuals)),
            'min': float(np.min(residuals)),
            'max': float(np.max(residuals)),
            'is_normal': self._check_normality(residuals)
        }
    
    def _check_normality(self, residuals: np.ndarray) -> bool:
        """检查残差正态性（简化实现）"""
        # 实际应该用Shapiro-Wilk或Kolmogorov-Smirnov检验
        skewness = np.abs(np.mean(((residuals - np.mean(residuals)) / np.std(residuals)) ** 3))
        return skewness < 0.5
