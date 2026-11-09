# S3 设计审查

状态：入口说明，2026-11-09 建立；事实来自 `templates/pipeline/*.json`、`config/agents.toml` 与源码，**不是新规则**。所属工作区：设计。返回 [阶段总览](../README.md)。

## 基本信息

| 项 | 内容 |
| --- | --- |
| 运行目录名 | `S3-design-review` |
| 执行角色 | design_reviewer（设计审查者） |
| 执行方式 | Agent |
| 注册表默认的 Agent 与模型 | codex / codex |
| 可能的结论 | PASS、REWORK、BLOCK |
| 结论去向 | PASS → 设计阶段结束（`pipeline/design`）或进入 S4（`pipeline/build`）；REWORK → 回 S2，轮次加一，受 `design_review_rounds` 上限约束；BLOCK → 阻塞 |

## 读取什么（输入）

- 需求原文、上游分析、同一份项目说明快照
- 完整设计（`design`）、开发计划（`plan`）、原型（`prototype`）

## 产出什么（输出）

- `review.md`，frontmatter 含 verdict 与 findings（id、severity、location、problem、expected）；**必须有“原文对照”小节**

## 交接

- 上游：S2 的三份产物
- 下游：通过后 S4 读取设计包
- 人工介入：审核轮次超限时转人工

## 证据与追溯

- `workspace/runs/<运行号>/S3-design-review/round-N/review.md` 与 `done.json`

## 需要特别说明的

- **与 D019 的差距**：现有 `check_vendors`（`src/cockpit/pipeline.py:174`）仍强制作者与审查者**厂商不同**（D008），S3 结论只有 PASS/REWORK/BLOCK，没有“免审放行”“降级放行”。D019 已接受分级审查，但**代码尚未适配**，不能把旧硬门槛当作现行规则。
- V2.1 的评审策略（第 6.3 节）与审查模板的方向见 [采用对照](../../design/2026-11-09-v21-mapping.md)，本目录不复制。

## 尚未实现或未验证

- D019 的免审与降级放行结果协议尚未实现。
- V2.1 的四层验证（V1–V4）尚未接入 S3。

## 阅读清单

| 资料 | 说明 |
| --- | --- |
| [D019](../../DECISIONS.md) | |
| [采用对照](../../design/2026-11-09-v21-mapping.md) | |
| [流水线模板](../../../templates/pipeline/design.json) | |

此目录目前只有这份入口；内容多了再拆出 `contract.md`、`standard.md`，需要时再建 `templates/`、`examples/`，不预建空目录。
