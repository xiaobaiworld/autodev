# S8 验收

状态：入口说明，2026-11-09 建立；事实来自 `templates/pipeline/*.json`、`config/agents.toml` 与源码，**不是新规则**。所属工作区：测试。返回 [阶段总览](../README.md)。

## 基本信息

| 项 | 内容 |
| --- | --- |
| 运行目录名 | `S8-acceptance` |
| 执行角色 | acceptor（验收者） |
| 执行方式 | Agent |
| 注册表默认的 Agent 与模型 | claude / claude-opus（D015，原定 agy） |
| 可能的结论 | PASS、REWORK、BLOCK |
| 结论去向 | PASS → S9；REWORK → 回 S4，轮次加一，受 `acceptance_rounds` 上限约束；BLOCK → 阻塞 |

## 读取什么（输入）

- 需求、分析、设计、计划、原型
- 完整差异、本轮检查结果、本轮使用记录（`usage_now`）
- 代码目录（只读）
- 人工意见

## 产出什么（输出）

- `acceptance.md`，**必须有“原文对照”小节**

## 交接

- 上游：S7U 通过的使用验证
- 下游：S9 正式发布
- 人工介入：验收轮次超限时转人工

## 证据与追溯

- `acceptance.md`、`done.json`；验收者自己不能运行命令，优先引用 S7U 的使用记录

## 需要特别说明的

- 以使用者身份对照原文验收。
- 对代码目录只读（`workdir: readonly`）：验收前记录代码指纹，验收后比对，期间代码被改动则本次验收作废。

## 尚未实现或未验证

- D019 的降级与免审放行尚未实现。

## 阅读清单

| 资料 | 说明 |
| --- | --- |
| [流水线模板](../../../templates/pipeline/build.json) | |
| [D015](../../DECISIONS.md) | |

此目录目前只有这份入口；内容多了再拆出 `contract.md`、`standard.md`，需要时再建 `templates/`、`examples/`，不预建空目录。
