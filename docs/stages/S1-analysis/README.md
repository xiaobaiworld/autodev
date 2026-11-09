# S1 需求分析

状态：入口说明，2026-11-09 建立；事实来自 `templates/pipeline/*.json`、`config/agents.toml` 与源码，**不是新规则**。所属工作区：需求。返回 [阶段总览](../README.md)。

## 基本信息

| 项 | 内容 |
| --- | --- |
| 运行目录名 | `S1-analysis` |
| 执行角色 | analyst（分析者） |
| 执行方式 | Agent |
| 注册表默认的 Agent 与模型 | claude / claude-opus |
| 可能的结论 | ACCEPT、REJECT、CLARIFY、BLOCK |
| 结论去向 | ACCEPT → S2；REJECT → 需求被拒绝；CLARIFY → 转人工；BLOCK → 阻塞 |

## 读取什么（输入）

- 原始需求（`request`）

## 产出什么（输出）

- `analysis.md`，frontmatter 含 verdict、summary、scope、acceptance_criteria；不明确时 verdict 写 CLARIFY 并列出问题

## 交接

- 上游：用户提交的需求。默认的需求澄清入口会直接生成 S1 基线并从 S2 开始（见 `src/requirements/handoff.py`）
- 下游：S2 读取 `analysis.md`
- 人工介入：CLARIFY 时转人工，由用户回复后继续

## 证据与追溯

- `workspace/runs/<运行号>/S1-analysis/round-N/` 下的 `analysis.md`、`done.json`、`record-aN.json`、`agent-aN.log`

## 需要特别说明的

- 需求澄清有独立模块与飞书、Web 入口，见 [需求澄清模块](../../modules/requirements/README.md) 与 [SRS 规范](../../specs/REQUIREMENT_SPEC_STANDARD.md)。默认入口定稿后**跳过 S1，直通 S2**。
- 从原始需求文件走流水线时才会真正运行 S1。两条路径需分别说明，不能混为一谈。

## 尚未实现或未验证

- 无

## 阅读清单

| 资料 | 说明 |
| --- | --- |
| [流水线模板](../../../templates/pipeline/design.json) | |
| [需求澄清模块](../../modules/requirements/README.md) | |
| [SRS 规范](../../specs/REQUIREMENT_SPEC_STANDARD.md) | |

此目录目前只有这份入口；内容多了再拆出 `contract.md`、`standard.md`，需要时再建 `templates/`、`examples/`，不预建空目录。
