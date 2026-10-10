---
name: testing
description: "生成和执行测试，确保代码质量。覆盖单元/集成/故障注入/边界值测试"
version: "1.0"
---

# Testing Skill

## 测试类型

### 1. 单元测试 (Unit Tests)
- 测试单个函数/类的行为
- 模拟外部依赖
- 快速执行

### 2. 集成测试 (Integration Tests)
- 测试模块间交互
- 真实数据库/缓存
- 端到端流程

### 3. 故障注入测试 (Fault Injection)
- 模拟服务不可用
- 模拟数据损坏
- 模拟并发冲突
- 模拟网络超时

### 4. 边界值测试 (Edge Cases)
- 空值/None输入
- 极值（0, 负数, 超大数）
- 特殊字符
- 并发场景

## 执行流程

```bash
# 1. 运行全部测试
cd {project_root}
python3 -m pytest tests/ -v

# 2. 运行特定类型
python3 -m pytest tests/ -v -k "test_v2"

# 3. 生成覆盖率报告
python3 -m pytest tests/ --cov=src --cov-report=term-missing

# 4. 故障注入测试
python3 test_robustness.py

# 5. 事件溯源测试
python3 test_event_sourcing.py
```

## 新增测试模板

```python
def test_{module}_{scenario}():
    """测试{module}在{scenario}场景下的行为"""
    # Arrange: 准备测试数据
    # Act: 执行被测代码
    # Assert: 验证结果
    pass
```

## 质量标准

- 测试覆盖率 > 80%
- 所有P0测试必须通过
- 故障注入测试全部通过
- 无flaky测试
