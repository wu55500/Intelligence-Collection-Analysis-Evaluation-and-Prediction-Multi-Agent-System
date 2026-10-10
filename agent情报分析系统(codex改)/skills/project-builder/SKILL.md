---
name: project-builder
description: "用其他skill协同完善项目：代码审查→测试→安全审计→修复→推送"
version: "1.0"
---

# Project Builder Skill

## 用途

编排多个skill对项目进行系统性完善：
1. code-review → 发现代码问题
2. testing → 补充测试覆盖
3. security-audit → 安全审计
4. 汇总修复 → 按优先级修复
5. 验证 → 所有测试通过
6. 推送 → 提交到GitHub

## 执行流程

```
输入: 项目路径
  ↓
[1] 代码审查 (code-review)
  ↓ 生成问题清单
[2] 测试补充 (testing)
  ↓ 覆盖新增/修改代码
[3] 安全审计 (security-audit)
  ↓ 发现安全问题
[4] 汇总修复
  ↓ 按P0/P1/P2优先级修复
[5] 验证: pytest + robustness + event_sourcing
  ↓ 全部通过
[6] 提交GitHub
```

## 修复优先级

- **P0**: 导致崩溃/数据损坏/安全漏洞 → 立即修复
- **P1**: 影响功能正确性 → 本轮修复
- **P2**: 代码质量/性能优化 → 记录待后续处理
