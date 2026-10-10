---
name: security-audit
description: "安全审计：认证/授权/注入/SSRF/敏感信息泄露检查"
version: "1.0"
---

# Security Audit Skill

## 检查维度

### 1. 认证与授权
- API端点是否有认证保护
- 危险操作是否需要高权限
- 对象级授权检查
- Token过期/刷新机制

### 2. 注入攻击
- SQL注入（参数化查询）
- 命令注入（os.system调用）
- 模板注入
- 提示注入（LLM输入过滤）

### 3. 数据安全
- 敏感信息硬编码检查
- 日志中是否泄露密钥
- API Key/Token是否加密存储
- 数据库连接信息是否暴露

### 4. 网络与SSRF
- 外部URL访问是否限制协议
- 内网地址/云元数据地址是否拦截
- CORS配置是否安全
- HTTPS强制

### 5. 资源耗尽
- 请求频率限制
- 请求体大小限制
- 并发连接数限制
- 查询超时设置

## 执行命令

```bash
# 1. 检查硬编码密钥
grep -rn "password\|secret\|key\|token" src/ --include="*.py" | grep -v "test"

# 2. 检查SQL拼接
grep -rn "execute(\"" src/ --include="*.py"

# 3. 检查命令注入
grep -rn "os.system\|subprocess" src/ --include="*.py"

# 4. 检查认证装饰器
grep -rn "@app" src/api/main.py | grep -v "get\|health"

# 5. 生成安全报告
python3 skills/security-audit/run.py
```

## 输出格式

```markdown
# 安全审计报告 - {日期}

## 摘要
- 检查项: X | 问题: Y (高危Z/中危W/低危V)

## 高危问题 (必须立即修复)
| 位置 | 问题 | 风险 | 修复方案 |
|------|------|------|---------|
| ... | ... | ... | ... |

## 中危问题 (尽快修复)
| 位置 | 问题 | 风险 | 建议 |
|------|------|------|------|
| ... | ... | ... | ... |

## 低危问题 (计划修复)
| 位置 | 问题 | 建议 |
|------|------|------|
| ... | ... | ... |
```
