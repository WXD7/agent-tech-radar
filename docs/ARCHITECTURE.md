# 架构与数据边界

## 目标

当前架构优先保证四件事：本地可运行、源数据可阅读、变更可审查、本地索引可重建。

## 当前组件

| 组件 | 实现 | 责任 |
| --- | --- | --- |
| Web 界面 | FastAPI + Jinja2 + HTMX | 总览、详情、导入、审核和笔记管理 |
| 图谱界面 | Cytoscape.js | 技术路线、候选、结论、证据、实验与学习节点的连接导航 |
| 源数据 | YAML + Git | 保存人可阅读、可比较的知识状态 |
| 查询索引 | SQLite | 从 YAML 重建，为查询和图谱提供派生数据 |
| 采集器 | GitHub API + PyPI API | 收集版本、公开规模信号和发现候选 |
| 研究执行 | Codex 任务交接 | 带上下文查源、实验、复盘并产生待审核变更 |

## 分层数据模型

```mermaid
flowchart TB
    Raw["来源与变化\nconversations / inbox / discovery"]
    Personal["个人学习层\nknowledge/nodes"]
    Evidence["外部证据与实验\nknowledge/evidence / experiments"]
    Proposal["待审核层\nproposals"]
    Accepted["已审核知识\nclaims / decisions / reviews"]
    Index["派生索引\n.radar/radar.db"]

    Raw --> Personal
    Raw --> Evidence
    Personal --> Proposal
    Evidence --> Proposal
    Proposal --> Accepted
    Personal --> Index
    Evidence --> Index
    Accepted --> Index
```

### 一条结论应该如何形成

1. 学习笔记记录从哪段会话产生，并标注待查证项。
2. 调研任务从笔记或技术节点读取相邻上下文，定义具体问题。
3. 官方来源和实验结果独立登记，并与对应断言建立支持或反驳关系。
4. AI 生成 proposal，展示前后差异、证据和不确定性。
5. 用户接受、修改或驳回后，单条提案才能进入已审核层。

## 图谱连通性

技术候选不根据“已审核 / 未审核”划成两张图。它们通过共用的技术路线类别连接，审核状态只影响视觉形式和知识权限。

当前图中主要关系包括：

- 技术 `classified_as` 技术路线。
- 技术 `provides` 能力。
- 证据 `supports / contradicts` 结论。
- 实验 `tests` 结论。
- 学习笔记 `questions / challenges / answers / extends / corrects` 目标节点或上一层笔记。

## 广度发现边界

当前广度来自多个 GitHub 查询族，而不是一个关键词。系统记录：

- 每个查询对应的技术类别和生态范围。
- API 返回数、去重数、新候选数和不完整结果标记。
- 已知、待评估、已排除及其原因。
- 当类别或生态存在空白时，新增查询族而不是仅增加单次返回数。

这些机制可以证明“搜索策略是什么”，不能证明“世界上所有相关项目都已被发现”。

## 执行与安全边界

- Web 应用当前只绑定 `127.0.0.1`，无用户系统。
- CSRF Token 用于本地写操作，但不等于生产级身份验证。
- API Token 只能通过环境变量传入。
- `.radar/`、缓存、本地虚拟环境和导入会话元数据默认不进入 Git。
- 如果未来接入会执行命令的长期调研 Agent，需要另行提供操作系统级隔离、最小权限和资源预算；进程分离不应被描述为安全沙箱。

## 可替换边界

长期上，下列部件都应可替换：

- 研究 Agent Harness：Codex、Prime Agent 或其他可控执行器。
- 发现来源：GitHub、npm、PyPI、arXiv、RSS/Atom 和人工策展列表。
- 查询层：当前 SQLite，未来可根据量级演进。
- 可视化引擎：当前 Cytoscape.js，但源数据不依赖具体图形引擎。

核心不可替换的是数据语义：认知来源、外部证据、AI 推断、实验结果和人工决策必须始终可区分。
