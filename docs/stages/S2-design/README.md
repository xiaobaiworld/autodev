# S2 设计

状态：入口说明，2026-11-09 建立；事实来自 `templates/pipeline/*.json`、`config/agents.toml` 与源码，**不是新规则**。所属工作区：设计。返回 [阶段总览](../README.md)。

## 基本信息

| 项 | 内容 |
| --- | --- |
| 运行目录名 | `S2-design` |
| 执行角色 | designer（设计者） |
| 执行方式 | Agent |
| 注册表默认的 Agent 与模型 | claude / claude-opus |
| 可能的结论 | DONE、BLOCK |
| 结论去向 | DONE → S3（同一轮）；BLOCK → 阻塞（资料缺失、需求歧义或重大冲突） |

## 读取什么（输入）

- 需求原文（`request`）
- 上游分析（`analysis`）
- 项目说明快照（`project_context`，由目标项目 README 与 `config.yaml` 中该项目的 `context` 清单生成，S2 与 S3 共用同一份）
- 上一轮的审查意见（`review_prev`，返修时）
- 人工意见（`human`）

## 产出什么（输出）

- `design.md`（架构与数据流、资产复用及证据、完整接口契约、界面与交互）
- `dev-plan.md`（可执行任务列表，含依赖、输入输出、接口、测试与验收映射）
- `prototype.md`（有界面时为可评审原型说明；无界面时写“不适用”及理由）

## 交接

- 上游：S1 的 `analysis.md`，或需求澄清定稿后由 handoff 生成的基线
- 下游：S3 审查；通过后 S4、S6、S8 读取设计包
- 人工介入：BLOCK 或审核超限时转人工

## 证据与追溯

- `workspace/runs/<运行号>/S2-design/round-N/`；项目快照在 `context/project-context/round-N/`

## 需要特别说明的

- **当前运行的契约是上面三份 Markdown 产物**（旧模板）。设计阶段的目标规范是 [Agent 自动化设计阶段规范 V2.1](../../Agent自动化设计阶段规范_V2.1.md)（D026）：设计等级 D0–D3、产物注册表 A01–A08、工程规则库、四层验证。**两者尚未衔接**，V2.1 按 MVP 1/2/3 逐步落地，新旧并存期间以新的流水线类型区分。
- V2.1 的可执行资产（规则数据、产物 Schema、分类与校验器）在仓库根的 [`design-system/`](../../../design-system/) 与 [`src/designsys/`](../../../src/designsys/)。本目录只链接，不复制其正文。
- 采用 V2.1 的对照、融合方案、需求类型与人工确认的位置见 [采用对照](../../design/2026-11-09-v21-mapping.md)。

## 尚未实现或未验证

- D0–D3 分类、五个产物的 Schema 与最小校验器已实现（MVP 1 第一部分），但**尚未接入流水线**。
- 规则选择器、完整性/引用/规则覆盖的验证、D0 一页文档尚未做。
- 设计 Agent 写原型页面与结构化文件的权限范围尚未确定。

## 阅读清单

| 资料 | 说明 |
| --- | --- |
| [V2.1 主规范](../../Agent自动化设计阶段规范_V2.1.md) | |
| [采用对照](../../design/2026-11-09-v21-mapping.md) | |
| [阶段机器人设计第 8 节](../../design/2026-11-08-stage-bots-design.md) | |
| [流水线模板](../../../templates/pipeline/design.json) | |
| [规则与 Schema](../../../design-system/) | |

此目录目前只有这份入口；内容多了再拆出 `contract.md`、`standard.md`，需要时再建 `templates/`、`examples/`，不预建空目录。
