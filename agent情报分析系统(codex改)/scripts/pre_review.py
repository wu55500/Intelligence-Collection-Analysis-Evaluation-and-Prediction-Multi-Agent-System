#!/usr/bin/env python3
"""
审查包生成器

用法:
  python3 scripts/pre_review.py --type feature --desc "改动描述"
  python3 scripts/pre_review.py --type bugfix --desc "修复XXX"
  python3 scripts/pre_review.py --type refactor --desc "重构XXX"
"""

import os
import sys
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
REVIEWS_DIR = PROJECT_ROOT / "docs" / "reviews"


def get_git_diff() -> str:
    """获取最近的git diff"""
    try:
        import subprocess
        result = subprocess.run(
            ['git', 'diff', '--stat', 'HEAD~1'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        return result.stdout if result.returncode == 0 else "无git历史"
    except:
        return "无法获取git diff"


def get_test_results() -> str:
    """获取最近测试结果"""
    try:
        import subprocess
        result = subprocess.run(
            ['python3', '-m', 'pytest', '-q', '--tb=line'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120
        )
        return result.stdout + result.stderr if result.returncode == 0 else "测试失败"
    except:
        return "无法运行测试"


def get_file_changes() -> List[Dict]:
    """获取文件变更列表"""
    changes = []
    try:
        import subprocess
        result = subprocess.run(
            ['git', 'diff', '--name-status', 'HEAD~1'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    changes.append({
                        'status': parts[0],
                        'file': parts[1]
                    })
    except:
        pass
    return changes


def generate_review_package(change_type: str, description: str):
    """生成审查包"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    review_id = f"review_{timestamp}"
    
    # 创建审查目录
    review_dir = REVIEWS_DIR / review_id
    review_dir.mkdir(parents=True, exist_ok=True)
    
    # 收集信息
    git_diff = get_git_diff()
    test_results = get_test_results()
    file_changes = get_file_changes()
    
    # 生成审查包
    package = f"""# 代码审查请求

**审查ID**: {review_id}  
**改动类型**: {change_type}  
**改动描述**: {description}  
**生成时间**: {datetime.now().isoformat()}

---

## 一、改动摘要

### 文件变更
{chr(10).join([f"- {c['status']}: {c['file']}" for c in file_changes]) if file_changes else "无文件变更记录"}

### Git Diff 统计
```
{git_diff}
```

---

## 二、测试情况

### 测试结果
```
{test_results}
```

---

## 三、审查问题

请回答以下问题（用 PASS/FAIL/WARN 标注）：

### 通用问题
1. 【正确性】这个改动是否引入了新的BUG？
2. 【安全性】是否存在安全风险（认证、授权、注入等）？
3. 【性能】是否影响系统性能或可扩展性？
4. 【可维护性】代码是否清晰、易维护？
5. 【边界情况】是否考虑了异常输入、并发、超时等？
6. 【建议改进】你有什么优化建议？

### 专项问题（根据改动类型）
"""
    
    # 根据类型添加专项问题
    if change_type == "feature":
        package += """
- 新功能是否与现有架构一致？
- 是否需要额外的测试覆盖？
- 文档是否需要更新？
"""
    elif change_type == "bugfix":
        package += """
- 修复是否解决了根本原因（而非表面症状）？
- 是否可能引入回归？
- 是否需要添加防止复发的测试？
"""
    elif change_type == "security":
        package += """
- 是否符合OWASP API Security Top 10？
- 认证/授权是否有绕过风险？
- 敏感数据是否得到保护？
"""
    
    package += f"""
---

## 四、回答格式

请按以下格式回答每个问题：

```
问题编号: [PASS/FAIL/WARN]
说明: ...
建议: ...
```

---

## 五、关键代码片段

[请查看 git diff 或相关文件获取完整代码]

---

**谢谢你的审查！**
"""
    
    # 写入审查包
    package_file = review_dir / "review_package.md"
    package_file.write_text(package)
    
    # 生成汇总模板
    summary = f"""# 审查意见汇总

**审查ID**: {review_id}  
**改动描述**: {description}  
**审查日期**: {datetime.now().strftime("%Y-%m-%d")}

---

## 参与AI

- [ ] GPT-4o (ChatGPT)
- [ ] Claude 3.5 Sonnet
- [ ] Gemini 1.5 Pro
- [ ] DeepSeek-Coder
- [ ] Perplexity

**最低要求**: 至少3个AI完成审查

---

## 各AI结论

| AI | 结论 | PASS | FAIL | WARN | 关键问题 |
|----|------|------|------|------|---------|
| GPT-4o | | | | | |
| Claude 3.5 | | | | | |
| Gemini 1.5 Pro | | | | | |
| DeepSeek | | | | | |
| Perplexity | | | | | |

---

## 分歧点

[如有分歧，记录各AI观点]

---

## 最终决策

- [ ] 直接推送（全票通过）
- [ ] 修改后推送（修改内容：...）
- [ ] 需要进一步讨论

---

## 修改记录

| 问题来源 | 问题描述 | 修改内容 | 状态 |
|---------|---------|---------|------|
| | | | |

---

## 审查完成确认

- [ ] 已收集至少3个AI的审查意见
- [ ] 所有FAIL项已修复
- [ ] 所有WARN项已处理或记录
- [ ] 代码已根据反馈修改
- [ ] 测试已通过

**审查完成时间**: _______________  
**决策者签名**: _______________
"""
    
    summary_file = review_dir / "summary_template.md"
    summary_file.write_text(summary)
    
    print(f"✅ 审查包已生成: {review_dir}")
    print(f"   - review_package.md: 发送给各AI的审查请求")
    print(f"   - summary_template.md: 汇总各AI意见的模板")
    print(f"\n下一步:")
    print(f"   1. 复制 review_package.md 内容，发送给各AI")
    print(f"   2. 收集反馈，填写 summary_template.md")
    print(f"   3. 根据反馈修改代码")
    print(f"   4. 推送GitHub")
    
    return review_dir


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="生成代码审查包")
    parser.add_argument("--type", required=True, 
                       choices=["feature", "bugfix", "refactor", "security", "performance"],
                       help="改动类型")
    parser.add_argument("--desc", required=True, help="改动描述")
    
    args = parser.parse_args()
    
    generate_review_package(args.type, args.desc)
