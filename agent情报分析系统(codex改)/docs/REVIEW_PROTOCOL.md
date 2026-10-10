# 多AI审查协议 (Multi-AI Review Protocol)

**版本**: V1.0  
**生效日期**: 2026-10-09  
**目的**: 每次代码改进推送前，必须经过至少3个独立AI系统审查

---

## 一、审查流程

```
代码改动 → 生成审查包 → 发送给5个AI → 汇总意见 → 修改 → 推送GitHub
```

### 1.1 触发条件

以下情况必须执行多AI审查：
- [ ] 新增功能模块
- [ ] 修改核心逻辑（验证闸门、红队、检查点、预测闭环）
- [ ] 修复P0/P1级BUG
- [ ] 架构变更
- [ ] 安全相关改动

### 1.2 审查AI列表（按推荐优先级）

| 序号 | AI系统 | 擅长领域 | 访问方式 |
|------|--------|---------|---------|
| 1 | **GPT-4o** (ChatGPT) | 综合推理、代码审查 | https://chat.openai.com |
| 2 | **Claude 3.5 Sonnet** | 长文本分析、安全性 | https://claude.ai |
| 3 | **Gemini 1.5 Pro** | 多模态、大规模代码 | https://aistudio.google.com |
| 4 | **DeepSeek-Coder** | 代码质量、最佳实践 | https://chat.deepseek.com |
| 5 | **Perplexity** | 事实核查、最新信息 | https://perplexity.ai |

**最低要求**: 至少获得3个AI的审查意见方可推送

---

## 二、审查包生成

### 2.1 自动生成审查包

```bash
cd intel_system
python3 scripts/pre_review.py --type "feature" --description "新增红队阈值配置"
```

生成文件：
- `docs/reviews/review_package_YYYYMMDD_HHMMSS.md` - 完整审查请求
- `docs/reviews/changes_summary.md` - 改动摘要
- `docs/reviews/code_diff.md` - 关键代码差异

### 2.2 审查包内容

每个审查包包含：
1. **改动描述** (What changed)
2. **改动原因** (Why)
3. **影响范围** (Impact)
4. **关键代码** (Key code snippets)
5. **测试情况** (Test status)
6. **审查问题** (Review questions for AI)

---

## 三、审查问题模板

### 3.1 通用审查问题

向每个AI发送以下问题：

```
请审查以下代码改动，回答以下问题：

1. 【正确性】这个改动是否引入了新的BUG？
2. 【安全性】是否存在安全风险（认证、授权、注入等）？
3. 【性能】是否影响系统性能或可扩展性？
4. 【可维护性】代码是否清晰、易维护？
5. 【边界情况】是否考虑了异常输入、并发、超时等？
6. 【建议改进】你有什么优化建议？

请用以下格式回答：
- 问题编号: [PASS/FAIL/WARN]
- 说明: ...
- 建议: ...
```

### 3.2 专项审查问题

根据改动类型添加专项问题：

**安全类改动**:
- 是否符合OWASP API Security Top 10？
- 认证/授权是否有绕过风险？

**数据类改动**:
- 数据一致性是否保证？
- 并发场景是否安全？

**算法类改动**:
- 时间复杂度/空间复杂度是否合理？
- 是否有数值稳定性问题？

---

## 四、意见汇总与决策

### 4.1 汇总模板

```markdown
# 审查意见汇总

**改动**: [改动描述]  
**审查日期**: YYYY-MM-DD  
**参与AI**: GPT-4o, Claude 3.5, Gemini 1.5 Pro

## 各AI结论

| AI | 结论 | 关键问题 |
|----|------|---------|
| GPT-4o | ✅ 通过 | 无 |
| Claude 3.5 | ⚠️ 有条件通过 | 建议增加XX测试 |
| Gemini 1.5 Pro | ✅ 通过 | 无 |

## 分歧点

[如有分歧，记录各AI观点]

## 最终决策

- [ ] 直接推送
- [ ] 修改后推送（修改内容：...）
- [ ] 需要进一步讨论

## 修改记录

[根据AI建议做的修改]
```

### 4.2 决策规则

- **全票通过** (3/3或以上): 直接推送
- **有条件通过** (有WARN但无FAIL): 修改WARN项后推送
- **有FAIL**: 必须修改后重新审查
- **分歧严重**: 人工介入决策

---

## 五、自动化集成

### 5.1 CI/CD集成

在 `.github/workflows/ci.yml` 中添加：

```yaml
- name: Generate Review Package
  if: contains(github.event.head_commit.message, 'feature:')
  run: python3 scripts/pre_review.py --type "feature"

- name: Upload Review Package
  uses: actions/upload-artifact@v3
  with:
    name: review-package
    path: docs/reviews/
```

### 5.2 Git Hook（可选）

```bash
# .git/hooks/pre-push
#!/bin/bash
if [[ $1 == "origin" ]]; then
  echo "检查是否需要多AI审查..."
  python3 scripts/check_review_required.py
  if [ $? -ne 0 ]; then
    echo "❌ 缺少审查包，请先运行 scripts/pre_review.py"
    exit 1
  fi
fi
```

---

## 六、审查记录归档

所有审查记录保存在：
```
docs/reviews/
├── 20261009_143022_red_team_threshold.md
├── 20261009_143022_gpt4o_feedback.md
├── 20261009_143022_claude_feedback.md
├── 20261009_143022_gemini_feedback.md
└── 20261009_143022_summary.md
```

---

## 七、快速启动

```bash
# 1. 生成审查包
python3 scripts/pre_review.py --type "feature" --desc "你的改动描述"

# 2. 复制审查包内容，发送给各AI
cat docs/reviews/review_package_*.md

# 3. 收集反馈，填写汇总表
# 4. 根据反馈修改代码
# 5. 推送GitHub
git push origin main
```

---

**注意**: 本协议不强制自动化（因需要各AI的API Key），但要求人工执行审查流程。未来可接入各AI的API实现自动化。
