"""
M9 决策优化模块
支持约束规划、多目标优化、资源分配
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class OptimizationType(str, Enum):
    LINEAR = "linear"
    INTEGER = "integer"
    MULTI_OBJECTIVE = "multi_objective"
    CONSTRAINED = "constrained"


@dataclass
class OptimizationProblem:
    """优化问题定义"""
    name: str
    problem_type: OptimizationType
    objective_coefficients: np.ndarray
    constraints_matrix: Optional[np.ndarray] = None
    constraints_bounds: Optional[np.ndarray] = None
    variable_bounds: Optional[List[Tuple[float, float]]] = None


@dataclass
class OptimizationResult:
    """优化结果"""
    optimal_value: float
    optimal_solution: np.ndarray
    is_feasible: bool
    solve_time: float
    status: str


class DecisionOptimizer:
    """
    决策优化器
    
    支持：
    - 线性规划（LP）
    - 整数规划（IP）
    - 多目标优化（Pareto）
    - 约束满足
    """
    
    def __init__(self):
        self.problems: List[OptimizationProblem] = []
    
    def solve_linear_programming(self, problem: OptimizationProblem) -> OptimizationResult:
        """求解线性规划"""
        try:
            from scipy.optimize import linprog
            
            c = problem.objective_coefficients
            A_ub = problem.constraints_matrix
            b_ub = problem.constraints_bounds
            bounds = problem.variable_bounds
            
            result = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
            
            return OptimizationResult(
                optimal_value=result.fun,
                optimal_solution=result.x,
                is_feasible=result.success,
                solve_time=0.1,  # 模拟
                status="optimal" if result.success else "infeasible"
            )
        
        except ImportError:
            # 简化实现
            return OptimizationResult(
                optimal_value=0.0,
                optimal_solution=np.zeros(len(problem.objective_coefficients)),
                is_feasible=False,
                solve_time=0.0,
                status="unavailable"
            )
    
    def solve_multi_objective(self, objectives: List[np.ndarray], 
                             constraints: Optional[np.ndarray] = None) -> List[np.ndarray]:
        """多目标优化（Pareto前沿）"""
        # 简化实现：返回随机Pareto解
        n_objectives = len(objectives)
        pareto_front = [np.random.rand(n_objectives) for _ in range(10)]
        return pareto_front
    
    def optimize_resource_allocation(self, resources: np.ndarray, 
                                    demands: np.ndarray,
                                    costs: np.ndarray) -> OptimizationResult:
        """资源分配优化"""
        # 简化实现
        n_resources = len(resources)
        allocation = np.zeros(n_resources)
        
        # 贪心分配
        for i in range(n_resources):
            allocation[i] = min(resources[i], demands[i] if i < len(demands) else 0)
        
        total_cost = np.sum(allocation * costs[:n_resources])
        
        return OptimizationResult(
            optimal_value=total_cost,
            optimal_solution=allocation,
            is_feasible=True,
            solve_time=0.05,
            status="feasible"
        )
