"""
统一验收闸门 (L3 确定性治理层)

每个模块除了业务输出，还必须提供标准化验收信息：
- status: 执行状态
- input_refs: 输入引用
- output_refs: 输出引用
- method_version: 方法版本
- parameters: 执行参数
- evidence_refs: 证据引用
- validation_results: 验证结果
- errors: 错误列表
- warnings: 警告列表

主控不能仅凭模块返回了一个对象就判定任务成功
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class ModuleStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    VALIDATION_ERROR = "validation_error"


@dataclass
class ModuleOutput:
    """
    统一模块输出契约
    
    所有模块必须返回此格式，主控通过验收闸门判断是否通过
    """
    module_name: str
    status: ModuleStatus = ModuleStatus.SUCCESS
    output_data: Dict[str, Any] = field(default_factory=dict)
    input_refs: List[str] = field(default_factory=list)
    output_refs: List[str] = field(default_factory=list)
    method_version: str = "1.0"
    parameters: Dict[str, Any] = field(default_factory=dict)
    evidence_refs: List[str] = field(default_factory=list)
    validation_results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    task_id: str = ""


@dataclass
class ValidationResult:
    """闸门验证结果"""
    passed: bool
    module_name: str
    status: ModuleStatus
    critical_issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class ValidationGate:
    """
    统一验收闸门
    
    职责：
    1. 检查模块输出是否符合契约
    2. 验证执行状态
    3. 检查证据引用完整性
    4. 判断是否允许继续流程
    """
    
    # 关键模块列表 - 这些模块失败会阻断流程
    CRITICAL_MODULES = {"m1_collection", "m2_governance", "m8_forecast", "m21_commitment"}
    
    # 必须存在的字段
    REQUIRED_FIELDS = {"status", "output_data", "method_version"}
    
    def __init__(self):
        self.validation_history: List[ValidationResult] = []
    
    def validate(self, output: ModuleOutput) -> ValidationResult:
        """
        验证模块输出
        
        Returns:
            ValidationResult: 验证结果
        """
        issues = []
        warnings = list(output.warnings)
        info = []
        
        # 1. 检查执行状态
        if output.status == ModuleStatus.FAILED:
            issues.append(f"模块 {output.module_name} 执行失败: {'; '.join(output.errors)}")
        elif output.status == ModuleStatus.TIMEOUT:
            issues.append(f"模块 {output.module_name} 执行超时")
        elif output.status == ModuleStatus.VALIDATION_ERROR:
            issues.append(f"模块 {output.module_name} 验证错误")
        
        # 2. 检查输出数据是否为空
        if output.status == ModuleStatus.SUCCESS and not output.output_data:
            warnings.append(f"模块 {output.module_name} 成功但无输出数据")
        
        # 3. 检查证据引用
        if output.module_name in ["m1_collection", "m12_evidence"] and not output.evidence_refs:
            if output.module_name == "m1_collection":
                issues.append("采集模块未产生任何证据引用")
            else:
                warnings.append("证据评估模块未引用证据")
        
        # 4. 检查错误列表
        if output.errors and output.status == ModuleStatus.SUCCESS:
            warnings.append(f"模块标记为成功但存在 {len(output.errors)} 个错误记录")
        
        # 5. 检查关键模块
        if output.module_name in self.CRITICAL_MODULES and output.status != ModuleStatus.SUCCESS:
            issues.append(f"关键模块 {output.module_name} 未成功完成")
        
        # 6. 检查方法版本
        if not output.method_version:
            warnings.append("缺少方法版本号，影响可追溯性")
        
        # 判断是否通过
        passed = len(issues) == 0
        
        result = ValidationResult(
            passed=passed,
            module_name=output.module_name,
            status=output.status,
            critical_issues=issues,
            warnings=warnings,
            info=info
        )
        
        self.validation_history.append(result)
        return result
    
    def should_block(self, result: ValidationResult) -> bool:
        """判断是否应该阻断流程"""
        if not result.passed and result.module_name in self.CRITICAL_MODULES:
            return True
        return False
    
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """获取验证摘要"""
        total = len(self.validation_history)
        passed = sum(1 for v in self.validation_history if v.passed)
        failed = total - passed
        
        return {
            "total_validations": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / total if total > 0 else 0,
            "recent_issues": [
                {"module": v.module_name, "issues": v.critical_issues}
                for v in self.validation_history[-5:] if not v.passed
            ]
        }
