# S6 代码审查

状态：入口说明，2026-11-09 建立；事实来自 `templates/pipeline/*.json`、`config/agents.toml` 与源码，**不是新规则**。所属工作区：开发。返回 [阶段总览](../README.md)。

## 基本信息

| 项 | 内容 |
| --- | --- |
| 运行目录名 | `S6-code-review` |
| 执行角色 | code_reviewer（代码审查者） |
| 执行方式 | Agent |
| 注册表默认的 Agent 与模型 | claude / claude-opus |
| 可能的结论 | PASS、REWORK、BLOCK |
| 结论去向 | PASS → S7；REWORK → 回 S4，轮次加一，受 `code_review_rounds` 上限约束；BLOCK → 阻塞 |

## 读取什么（输入）

- 需求、分析、设计、计划、原型
- 完整差异（`full_diff`）
- 本轮检查结果（`check_now`）
- 代码目录（`workdir_ro`，只读）
- 人工意见（`human`）

## 产出什么（输出）

- `review.md`，**必须有“原文对照”小节**

## 交接

- 上游：S5 通过的检查
- 下游：S7 发布候选
- 人工介入：审核轮次超限时转人工

## 证据与追溯

- `review.md`、`done.json`；程序比对代码指纹，审查期间代码被改动则审查作废

## 需要特别说明的

- 审查者只读：若审查过程中代码指纹变化，本次审查作废。
- 与 S3 一样，现有 `check_vendors` 强制作者与审查者厂商不同，D019 的降级与免审尚未适配。

## 尚未实现或未验证

- D019 的降级与免审放行尚未实现。

## 阅读清单

| 资料 | 说明 |
| --- | --- |
| [流水线模板](../../../templates/pipeline/build.json) | |
| [D019](../../DECISIONS.md) | |

此目录目前只有这份入口；内容多了再拆出 `contract.md`、`standard.md`，需要时再建 `templates/`、`examples/`，不预建空目录。
