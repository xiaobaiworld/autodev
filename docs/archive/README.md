# 历史资料与归档

日期：2026-11-09。状态：历史入口，正文不作为当前规范。返回 [项目索引](../INDEX.md)。

| 资料 | 历史用途 | 当前入口 |
| --- | --- | --- |
| [驾驶舱设计](2026-11-05-cockpit.md)、[开发计划](2026-11-05-cockpit-dev-plan.md) | 早期窗格驱动方案 | [地基方案](../design/2026-11-05-autoloop-foundation.md) |
| [autoloop 测试计划 v1](2026-11-04-autoloop-test-plan.md)、[v2](2026-11-05-autoloop-test-plan-v2.md) | 已执行或调整的实验计划 | [验证记录索引](../INDEX.md#验证记录) |
| [设计出口与分级](2026-11-09-design-exit-and-grading.md)、[案例与模板](2026-11-09-design-cases-and-templates.md) | D025 的三档设计规则 | [V2.1 采用对照](../design/2026-11-09-v21-mapping.md) |
| [早期需求协议](2026-11-08-requirements-protocol-early-draft.md) | 被标准取代的第一版协议 | [SRS 规范](../specs/REQUIREMENT_SPEC_STANDARD.md) |
| [设计机器人 v0.1 原文](2026-11-09-design-bot-work-instructions-v01.md) | 本轮拆分前第 8 节，保留旧要求与演进证据 | [S2](../stages/S2-design/README.md)、[S3](../stages/S3-design-review/README.md) |
| [早期 next 快照](2026-11-09-next-before-reorg.md)、[本轮整理前 next](2026-11-09-next-before-stage-docs.md) | 旧目标、服务描述、运行证据与遗留事项 | [当前 next](../../next.md) |
| [未提交审阅补丁](2026-11-09-design-review-uncommitted.patch) | 原设计逐项审阅记录 | 只作追溯，不能直接应用到当前规则 |
| [goal.md](goal.md) | 旧空白目标模板 | 不属于待执行目标 |

两份 next 快照均在代码块中保留完整原文，避免把原根目录相对链接当成本目录导航；内容可逐字核对，展示外壳不作为快照正文。

归档不代表所有条目都“已实现”：有的被取代，有的只是旧草稿或状态快照，以每份说明和替代关系为准。`docs/modules/requirements/baselines/` 的固定副本及 `spikes/`、`reports/` 的实验报告仍留原位，可通过总索引访问，不为了目录整齐改写历史。

运行数据归档在 `workspace/archive/`，不在本目录，也不入 Git；见 [DATA_SPEC](../DATA_SPEC.md)。不可将它与文档历史或当前运行合并。
