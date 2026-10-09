# 情报收集分析评估预测多Agent系统

## 系统概述

基于四层架构的情报分析预测系统，集成验收闸门、红队验证、智能路由、持久化检查点。

**版本**: 0.2.0  
**架构**: v2_四层架构 + 验收闸门 + 红队验证

## 核心特性

### 🏗️ 四层架构
- **L1 交互与任务编排层**: M13报告、M19工作流、主控Agent
- **L2 情报与分析能力层**: M1-M7, M9-M12, M16-M18
- **L3 确定性治理层**: M8预测、M14权限、M20健康、M21承诺
- **L4 数据与基础设施层**: 数据库、缓存、检索、检查点

### 🚪 统一验收闸门
每个模块输出必须通过验收闸门：
- 检查执行状态（成功/失败/超时）
- 验证证据引用完整性
- 关键模块失败自动阻断
- 非关键模块失败可降级

### 🔴 独立红队验证
不由原分析Agent控制的复核路径：
- 来源独立性检查
- 反证充分性检查
- 方法适当性检查
- 预测基线比较
- 证伪锚点检查

### 🎯 智能路由
根据任务类型自动选择最佳模型：
- **研究采集** → Perplexity/Gemini（搜索+长上下文）
- **数据分析** → o1（深度推理）
- **报告生成** → Claude Opus（写作）
- **NER抽取** → Claude Sonnet（快速）
- **代码生成** → DeepSeek（数学代码强）

### 💾 持久化检查点
- 任务状态持久化
- 断点恢复
- 支持任意步骤重新运行
- 保留新旧运行差异

## 快速开始

### 安装
```bash
cd intel_system
pip install -r requirements.txt
```

### 启动API服务
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

### 访问API文档
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API端点（V2）

### 任务管理
```bash
POST /api/v2/tasks                    # 创建任务
GET  /api/v2/tasks/{task_id}          # 获取任务
POST /api/v2/tasks/{task_id}/resume   # 恢复任务
GET  /api/v2/tasks/{task_id}/recovery # 恢复信息
GET  /api/v2/tasks/{task_id}/diffs    # 步骤差异
```

### 智能路由
```bash
POST /api/v2/routing/recommend        # 推荐模型
GET  /api/v2/routing/models           # 列出模型
```

### 红队验证
```bash
POST /api/v2/red-team/verify          # 独立验证
```

### RAG检索
```bash
POST /api/v2/rag/search               # 语义搜索
POST /api/v2/rag/add                  # 添加文档
```

### 记忆系统
```bash
POST /api/v2/memory/short-term        # 添加短期记忆
GET  /api/v2/memory/short-term/{id}   # 获取短期记忆
GET  /api/v2/memory/stats             # 记忆统计
```

### 系统健康
```bash
GET /api/v2/health                    # 健康检查
GET /api/v2/metrics                   # 系统指标
```

## 技术栈分层

| 层级 | 技术栈 | 用途 |
|------|--------|------|
| **后端工程** | FastAPI + Pydantic + pytest | API、数据模型、测试 |
| **数据工程** | httpx + BeautifulSoup + pandas | 采集、清洗、治理 |
| **数据库** | SQLite → PostgreSQL | 任务、证据、预测、审计 |
| **Agent开发** | LiteLLM + 工具调用 | 任务分解、检索、分析 |
| **RAG/搜索** | BM25 + 向量数据库 | 证据召回、语义搜索 |
| **统计ML** | SciPy + scikit-learn | 统计检验、模型评估 |
| **运筹学** | SciPy.optimize | 资源分配、约束优化 |
| **可视化** | Next.js + React + ECharts | 仪表盘、证据链、报告 |
| **工作流** | asyncio + 检查点 + 事件日志 | 任务恢复、重试、熔断 |
| **部署** | Docker + GitHub Actions | 自动测试、部署 |

## 模块清单

### L2 · 情报与分析能力层
- **M1 采集**: 多源检索、反向检索、Robots协议
- **M2 治理**: 清洗去重、异常值净化、口径检查
- **M3 EDA**: 描述统计、异常检测、分布检验
- **M4 特征**: 特征提取、特征选择、降维
- **M5 因果**: 因果识别、方法选择、假设检验
- **M6 模型**: 模型选择、交叉验证、超参优化
- **M7 评估**: 性能指标、诊断分析、过拟合检测
- **M9 优化**: 线性规划、多目标优化、资源分配
- **M10 告警**: 阈值告警、前提失灵、证据冲突
- **M11 知识图谱**: 实体识别、关系抽取、图查询
- **M12 证据链**: 三角验证、冲突检测、强度评估
- **M16 回测**: 历史回测、策略评估、基准比较
- **M17 运筹**: AHP层次分析、Pareto最优、多准则决策
- **M18 仿真**: 蒙特卡洛仿真、情景推演、敏感性分析

### L3 · 确定性治理层
- **M8 预测**: 预测登记、证伪锚点、到期结算
- **M14 权限**: 权限检查、RPN风险量化、单向收紧
- **M15 指标**: 系统监控、性能指标、健康检查
- **M20 健康**: 漂移检测、版本管理、健康检查
- **M21 承诺**: 承诺等级评估、规则引擎、审计记录

### L1 · 交互与任务编排层
- **M13 报告**: 报告生成、逻辑谬误检查、利益链检查
- **M19 工作流V2**: 验收闸门 + 红队 + 检查点 + 步骤差异

### L4 · 数据与基础设施层
- **缓存**: Redis（内存回退）
- **向量**: 嵌入服务 + 向量存储 + RAG检索
- **记忆**: 短期记忆 + 长期记忆 + 工作记忆
- **反思**: 自我修正引擎
- **检查点**: 持久化检查点服务

## 测试

运行全部测试：
```bash
python -m pytest tests/ -v
```

运行V2集成测试：
```bash
python -m pytest tests/test_v2_integration.py -v
```

当前测试状态：**43个测试全部通过**

## 项目结构

```
intel_system/
├── src/
│   ├── core/                    # 核心模块
│   │   ├── schemas.py          # 数据模型
│   │   ├── config.py           # 配置管理
│   │   ├── database.py         # 数据库
│   │   └── validation_gate.py  # 验收闸门
│   ├── services/               # 确定性治理层
│   │   ├── commitment_engine.py    # M21 承诺等级
│   │   ├── permission_service.py   # M14 权限治理
│   │   ├── forecast_service.py     # M8 预测登记
│   │   ├── orchestrator_v2.py      # M19 工作流V2
│   │   ├── red_team.py             # 独立验证器
│   │   └── checkpoint.py           # 检查点服务
│   ├── modules/                # 业务模块
│   │   ├── m1_collection/      # 采集
│   │   ├── m2_governance/      # 治理
│   │   ├── ...
│   │   └── m21_commitment/     # 承诺等级
│   ├── agents/                 # Agent层
│   │   ├── base_agent.py
│   │   ├── research_agent.py
│   │   ├── analysis_agent.py
│   │   └── router/             # 智能路由
│   │       ├── model_registry.py   # 模型注册表
│   │       ├── smart_router.py     # 路由器
│   │       └── llm_client.py       # 统一LLM客户端
│   ├── infra/                  # 基础设施
│   │   ├── cache/              # 缓存
│   │   ├── vector/             # 向量检索
│   │   ├── memory/             # 记忆系统
│   │   ├── reflection/         # 反思引擎
│   │   └── websocket/          # WebSocket
│   └── api/                    # API层
│       ├── main.py             # FastAPI主应用
│       └── websocket_handler.py
├── tests/                      # 测试
│   ├── test_core.py
│   ├── test_services.py
│   ├── test_modules.py
│   └── test_v2_integration.py
├── deploy/                     # 部署配置
│   ├── docker/
│   │   ├── Dockerfile
│   │   └── docker-compose.yml
│   ├── k8s/
│   │   └── deployment.yaml
│   └── scripts/
└── frontend/                   # 前端（规划中）
    └── package.json

共90+个Python文件，43个测试用例
```

## 关键设计决策

### 1. 技术栈不盲目堆砌
- SQLite保存结构化业务状态
- Redis用于低延迟缓存（内存回退）
- 向量数据库用于语义检索
- 三者是否需要由真实工作负载决定

### 2. 不是所有模块都是Agent
- 特征工程、模型评估、运筹算法等实现为算法服务
- 只有需要独立规划、选择工具或持续迭代的任务才用Agent
- 确定性规则由普通代码执行

### 3. 验收闸门 + 红队
- 每步输出必须通过验收闸门
- 关键步骤后触发独立红队验证
- 验证器不自动拥有否决权，输出作为可审计结果

### 4. 持久化检查点
- 任何环节中断可恢复
- 支持任意步骤重新运行
- 保留新旧运行之间的差异

## 下一步

- [ ] 接入真实搜索引擎API
- [ ] 实现前端交互式工作台
- [ ] 集成LiteLLM调用真实模型
- [ ] 添加更多端到端测试
- [ ] 部署到云服务器

## 许可证

MIT
