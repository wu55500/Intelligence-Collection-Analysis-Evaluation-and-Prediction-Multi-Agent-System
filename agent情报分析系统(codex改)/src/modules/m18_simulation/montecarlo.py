"""
M18 仿真推演模块
支持蒙特卡洛仿真、情景推演、敏感性分析
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SimulationResult:
    """仿真结果"""
    scenario_name: str
    n_iterations: int
    mean: float
    std: float
    percentile_5: float
    percentile_50: float
    percentile_95: float
    distribution: List[float]


@dataclass
class Scenario:
    """情景定义"""
    name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    probability: float = 1.0


class MonteCarloSimulator:
    """
    蒙特卡洛仿真器
    
    支持：
    - 随机采样
    - 概率分布
    - 多情景对比
    - 敏感性分析
    """
    
    def run_simulation(
        self,
        model_func,
        parameters: Dict[str, Tuple[str, float, float]],
        n_iterations: int = 10000,
        scenario_name: str = "default"
    ) -> SimulationResult:
        """
        运行蒙特卡洛仿真
        
        Args:
            model_func: 模型函数，接受参数字典，返回结果
            parameters: {param_name: (distribution, param1, param2)}
            n_iterations: 迭代次数
            scenario_name: 情景名称
        """
        results = []
        
        for _ in range(n_iterations):
            # 采样
            sampled = {}
            for param_name, (dist, p1, p2) in parameters.items():
                if dist == "uniform":
                    sampled[param_name] = np.random.uniform(p1, p2)
                elif dist == "normal":
                    sampled[param_name] = np.random.normal(p1, p2)
                elif dist == "lognormal":
                    sampled[param_name] = np.random.lognormal(p1, p2)
                else:
                    sampled[param_name] = p1
            
            result = model_func(sampled)
            results.append(result)
        
        results_array = np.array(results)
        
        return SimulationResult(
            scenario_name=scenario_name,
            n_iterations=n_iterations,
            mean=float(np.mean(results_array)),
            std=float(np.std(results_array)),
            percentile_5=float(np.percentile(results_array, 5)),
            percentile_50=float(np.percentile(results_array, 50)),
            percentile_95=float(np.percentile(results_array, 95)),
            distribution=results_array.tolist()[:1000]  # 限制大小
        )
    
    def sensitivity_analysis(
        self,
        model_func,
        base_params: Dict[str, float],
        param_to_vary: str,
        vary_range: Tuple[float, float],
        n_steps: int = 20
    ) -> Dict[str, Any]:
        """
        敏感性分析
        
        改变一个参数，观察输出变化
        """
        results = []
        values = np.linspace(vary_range[0], vary_range[1], n_steps)
        
        for value in values:
            params = base_params.copy()
            params[param_to_vary] = float(value)
            result = model_func(params)
            results.append({"value": float(value), "output": result})
        
        outputs = [r["output"] for r in results]
        
        return {
            "parameter": param_to_vary,
            "range": vary_range,
            "data": results,
            "sensitivity": (max(outputs) - min(outputs)) / (vary_range[1] - vary_range[0])
        }
    
    def compare_scenarios(self, scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
        """比较多情景"""
        comparison = []
        for scenario in scenarios:
            sim_result = self.run_simulation(
                model_func=scenario["model_func"],
                parameters=scenario["parameters"],
                n_iterations=scenario.get("n_iterations", 5000),
                scenario_name=scenario["name"]
            )
            comparison.append({
                "name": scenario["name"],
                "mean": sim_result.mean,
                "std": sim_result.std,
                "p5": sim_result.percentile_5,
                "p95": sim_result.percentile_95
            })
        
        return {"scenarios": comparison}
