"""
M17 运筹算法模块
支持AHP层次分析、Pareto最优、多准则决策
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class AHPCriteria:
    """AHP准则"""
    name: str
    weight: float = 0.0
    priority: int = 0


@dataclass
class AHPAlternative:
    """AHP方案"""
    name: str
    scores: Dict[str, float] = field(default_factory=dict)
    final_score: float = 0.0


class AHPSolver:
    """
    AHP层次分析法
    
    支持：
    - 判断矩阵构建
    - 一致性检验
    - 权重计算
    - 方案排序
    """
    
    def solve(self, criteria: List[str], comparison_matrix: np.ndarray,
             alternatives: List[Dict[str, float]]) -> Dict[str, Any]:
        """求解AHP"""
        n = len(criteria)
        
        # 计算权重
        eigenvalues, eigenvectors = np.linalg.eig(comparison_matrix)
        max_idx = np.argmax(eigenvalues.real)
        weights = eigenvectors[:, max_idx].real
        weights = weights / weights.sum()
        
        # 一致性检验
        lambda_max = eigenvalues[max_idx].real
        ci = (lambda_max - n) / (n - 1) if n > 1 else 0
        ri_table = {1: 0, 2: 0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45}
        ri = ri_table.get(n, 1.49)
        cr = ci / ri if ri > 0 else 0
        
        # 方案评分
        scored = []
        for alt in alternatives:
            score = sum(weights[i] * alt.get(criteria[i], 0) for i in range(len(criteria)))
            scored.append({"name": alt.get("name", f"alt_{len(scored)}"), "score": score})
        
        scored.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "weights": {criteria[i]: float(weights[i]) for i in range(len(criteria))},
            "consistency_ratio": float(cr),
            "is_consistent": cr < 0.1,
            "ranking": scored
        }


class ParetoSolver:
    """
    Pareto最优求解
    
    支持多目标优化，找出非支配解集
    """
    
    def find_pareto_front(self, objectives: np.ndarray) -> List[int]:
        """
        找Pareto前沿
        
        Args:
            objectives: shape (n_solutions, n_objectives)，所有目标都是最大化
        Returns:
            Pareto前沿解的索引
        """
        n = objectives.shape[0]
        is_pareto = np.ones(n, dtype=bool)
        
        for i in range(n):
            if not is_pareto[i]:
                continue
            for j in range(n):
                if i == j or not is_pareto[j]:
                    continue
                # 如果j支配i
                if np.all(objectives[j] >= objectives[i]) and np.any(objectives[j] > objectives[i]):
                    is_pareto[i] = False
                    break
        
        return list(np.where(is_pareto)[0])
    
    def normalize_objectives(self, objectives: np.ndarray) -> np.ndarray:
        """归一化目标值"""
        mins = objectives.min(axis=0)
        maxs = objectives.max(axis=0)
        ranges = maxs - mins
        ranges[ranges == 0] = 1
        return (objectives - mins) / ranges
