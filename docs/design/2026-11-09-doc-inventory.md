# 文档清点、迁移结果与后续缺口

日期：2026-11-09。状态：本轮文档组织已执行；替代此前的 53 文件清点快照。依据：[提案](2026-11-09-document-organization-proposal.md)与[执行记录](2026-11-09-doc-organization-review.md)。本清单不批准流水线接入、产品开发或服务变更。

## 1. 覆盖范围与判定方法

当前共 85 份资料：根目录 Markdown、docs 全部文件、reference 全部文件，以及 templates/design-system 的 Markdown 入口或文档模板。可执行 JSON/TOML 与源代码另在第 3 节登记路径依赖，不当普通文档搬迁。每份资料只有一个归属；索引、阶段与模块可引用同一正文。

优先按内容职责和生命周期判断，再核对来源、替代关系及完整路径/分段拼接依赖。代码注释、配置证据、测试读取和运行时存取分别记录，不能统称“程序在读”。同名的运行 design.md/README.md 不等于文档同名文件。

| 类别 | 份数 |
| --- | --- |
| 优化记录 | 1 |
| 兼容文档模板 | 2 |
| 原位历史 | 2 |
| 固定需求基线 | 2 |
| 外部参考 | 5 |
| 平台入口与公共记录 | 12 |
| 平台历史设计 | 1 |
| 平台方案与取舍 | 12 |
| 执行资产入口 | 1 |
| 操作指南 | 1 |
| 文档历史 | 13 |
| 模块与黄金示例 | 1 |
| 模块历史计划 | 1 |
| 模块历史设计 | 1 |
| 模块文档 | 3 |
| 正式 SRS | 2 |
| 跨阶段规范 | 1 |
| 配置教学样例 | 1 |
| 阶段主规范 | 1 |
| 阶段工作契约 | 15 |
| 验证与过程证据 | 7 |

## 2. 逐项归属与处理

表中路径即本轮保留或新建的位置；除第 4 节说明的内容拆分外，没有重命名现有完整文件。提案、固定副本、历史证据与运行实现的状态不可互换。

| 文件 | 类别 | 处理理由与状态边界 |
| --- | --- | --- |
| [AGENTS.md](../../AGENTS.md) | 平台入口与公共记录 | 保持固定入口；现行目标在 next，决定/经验分别维护 |
| [AGENT_HANDOFF.md](../../AGENT_HANDOFF.md) | 平台入口与公共记录 | 保持固定入口；现行目标在 next，决定/经验分别维护 |
| [CLAUDE.md](../../CLAUDE.md) | 平台入口与公共记录 | 保持固定入口；现行目标在 next，决定/经验分别维护 |
| [README.md](../../README.md) | 平台入口与公共记录 | 保持固定入口；现行目标在 next，决定/经验分别维护 |
| [changelog.md](../../changelog.md) | 平台入口与公共记录 | 保持固定入口；现行目标在 next，决定/经验分别维护 |
| [design-system/README.md](../../design-system/README.md) | 执行资产入口 | 新增导航；规则/Schema 原位，和 docs/stages 互引 |
| [docs/Agent自动化设计阶段规范_V2.1.md](../Agent自动化设计阶段规范_V2.1.md) | 阶段主规范 | D026 已采用；唯一正文保留现有路径，由 S2/S3 引用 |
| [docs/DATA_SPEC.md](../DATA_SPEC.md) | 平台入口与公共记录 | 保持固定入口；现行目标在 next，决定/经验分别维护 |
| [docs/DECISIONS.md](../DECISIONS.md) | 平台入口与公共记录 | 保持固定入口；现行目标在 next，决定/经验分别维护 |
| [docs/INDEX.md](../INDEX.md) | 平台入口与公共记录 | 保持固定入口；现行目标在 next，决定/经验分别维护 |
| [docs/MODELS.md](../MODELS.md) | 平台入口与公共记录 | 保持固定入口；现行目标在 next，决定/经验分别维护 |
| [docs/OPTIMIZATIONS.md](../OPTIMIZATIONS.md) | 优化记录 | 只追加；优化未对应独立执行阶段，不新增阶段目录 |
| [docs/TOOLS.md](../TOOLS.md) | 平台入口与公共记录 | 保持固定入口；现行目标在 next，决定/经验分别维护 |
| [docs/archive/2026-11-04-autoloop-test-plan.md](../archive/2026-11-04-autoloop-test-plan.md) | 文档历史 | 归档与历史快照；当前替代入口见 archive/README，不当现行规则 |
| [docs/archive/2026-11-05-autoloop-test-plan-v2.md](../archive/2026-11-05-autoloop-test-plan-v2.md) | 文档历史 | 归档与历史快照；当前替代入口见 archive/README，不当现行规则 |
| [docs/archive/2026-11-05-cockpit-dev-plan.md](../archive/2026-11-05-cockpit-dev-plan.md) | 文档历史 | 归档与历史快照；当前替代入口见 archive/README，不当现行规则 |
| [docs/archive/2026-11-05-cockpit.md](../archive/2026-11-05-cockpit.md) | 文档历史 | 归档与历史快照；当前替代入口见 archive/README，不当现行规则 |
| [docs/archive/2026-11-08-requirements-protocol-early-draft.md](../archive/2026-11-08-requirements-protocol-early-draft.md) | 文档历史 | 归档与历史快照；当前替代入口见 archive/README，不当现行规则 |
| [docs/archive/2026-11-09-design-bot-work-instructions-v01.md](../archive/2026-11-09-design-bot-work-instructions-v01.md) | 文档历史 | 归档与历史快照；当前替代入口见 archive/README，不当现行规则 |
| [docs/archive/2026-11-09-design-cases-and-templates.md](../archive/2026-11-09-design-cases-and-templates.md) | 文档历史 | 归档与历史快照；当前替代入口见 archive/README，不当现行规则 |
| [docs/archive/2026-11-09-design-exit-and-grading.md](../archive/2026-11-09-design-exit-and-grading.md) | 文档历史 | 归档与历史快照；当前替代入口见 archive/README，不当现行规则 |
| [docs/archive/2026-11-09-design-review-uncommitted.patch](../archive/2026-11-09-design-review-uncommitted.patch) | 文档历史 | 归档与历史快照；当前替代入口见 archive/README，不当现行规则 |
| [docs/archive/2026-11-09-next-before-reorg.md](../archive/2026-11-09-next-before-reorg.md) | 文档历史 | 归档与历史快照；当前替代入口见 archive/README，不当现行规则 |
| [docs/archive/2026-11-09-next-before-stage-docs.md](../archive/2026-11-09-next-before-stage-docs.md) | 文档历史 | 归档与历史快照；当前替代入口见 archive/README，不当现行规则 |
| [docs/archive/README.md](../archive/README.md) | 文档历史 | 归档与历史快照；当前替代入口见 archive/README，不当现行规则 |
| [docs/archive/goal.md](../archive/goal.md) | 文档历史 | 归档与历史快照；当前替代入口见 archive/README，不当现行规则 |
| [docs/config/agent-registry.example.toml](../config/agent-registry.example.toml) | 配置教学样例 | 不是本机配置或密钥；保持原位 |
| [docs/design/2026-11-02-autodev-design.md](2026-11-02-autodev-design.md) | 平台方案与取舍 | 平台设计或提案，状态以文首为准；阶段细节链接到 stages |
| [docs/design/2026-11-05-autoloop-foundation.md](2026-11-05-autoloop-foundation.md) | 平台方案与取舍 | 平台设计或提案，状态以文首为准；阶段细节链接到 stages |
| [docs/design/2026-11-06-s4-code-stage.md](2026-11-06-s4-code-stage.md) | 平台历史设计 | 已核对核心内容已实现；原观察保留，不再列为当前待办 |
| [docs/design/2026-11-06-ticket-model.md](2026-11-06-ticket-model.md) | 平台方案与取舍 | 平台设计或提案，状态以文首为准；阶段细节链接到 stages |
| [docs/design/2026-11-08-agent-model-registry.md](2026-11-08-agent-model-registry.md) | 平台方案与取舍 | 平台设计或提案，状态以文首为准；阶段细节链接到 stages |
| [docs/design/2026-11-08-requirements-merge.md](2026-11-08-requirements-merge.md) | 平台方案与取舍 | 平台设计或提案，状态以文首为准；阶段细节链接到 stages |
| [docs/design/2026-11-08-stage-bots-design.md](2026-11-08-stage-bots-design.md) | 平台方案与取舍 | 平台设计或提案，状态以文首为准；阶段细节链接到 stages |
| [docs/design/2026-11-08-stage-bots-requirements.md](2026-11-08-stage-bots-requirements.md) | 平台方案与取舍 | 平台设计或提案，状态以文首为准；阶段细节链接到 stages |
| [docs/design/2026-11-09-doc-inventory.md](2026-11-09-doc-inventory.md) | 平台方案与取舍 | 平台设计或提案，状态以文首为准；阶段细节链接到 stages |
| [docs/design/2026-11-09-doc-organization-review.md](2026-11-09-doc-organization-review.md) | 平台方案与取舍 | 平台设计或提案，状态以文首为准；阶段细节链接到 stages |
| [docs/design/2026-11-09-document-organization-proposal.md](2026-11-09-document-organization-proposal.md) | 平台方案与取舍 | 平台设计或提案，状态以文首为准；阶段细节链接到 stages |
| [docs/design/2026-11-09-v21-mapping.md](2026-11-09-v21-mapping.md) | 平台方案与取舍 | 平台设计或提案，状态以文首为准；阶段细节链接到 stages |
| [docs/design/autodev-workflow-prototype.html](autodev-workflow-prototype.html) | 平台方案与取舍 | 平台设计或提案，状态以文首为准；阶段细节链接到 stages |
| [docs/guides/rerun-with-another-agent.md](../guides/rerun-with-another-agent.md) | 操作指南 | 按具体任务读取，保留原位 |
| [docs/lessons.md](../lessons.md) | 平台入口与公共记录 | 保持固定入口；现行目标在 next，决定/经验分别维护 |
| [docs/modules/requirements/README.md](../modules/requirements/README.md) | 模块文档 | 描述软件实现、使用或兼容入口；不重复阶段工作规范 |
| [docs/modules/requirements/baselines/v0.8.md](../modules/requirements/baselines/v0.8.md) | 固定需求基线 | 原样保留，不能用当前新规则重写旧验收 |
| [docs/modules/requirements/baselines/v0.9.md](../modules/requirements/baselines/v0.9.md) | 固定需求基线 | 原样保留，不能用当前新规则重写旧验收 |
| [docs/modules/requirements/design.md](../modules/requirements/design.md) | 原位历史 | 早期草案；固定基线通过 ../design.md 引用，保留路径 |
| [docs/modules/requirements/dev-plan.md](../modules/requirements/dev-plan.md) | 模块历史计划 | 兼容入口 v0.9 已执行计划，留模块内追溯，不当当前待办 |
| [docs/modules/requirements/feishu-requirement-bot.md](../modules/requirements/feishu-requirement-bot.md) | 模块与黄金示例 | 测试按路径提取范本，原位保留 |
| [docs/modules/requirements/requirements.md](../modules/requirements/requirements.md) | 原位历史 | 已被取代；已校验 SRS 仍引用，保留路径和替代说明 |
| [docs/modules/requirements/usage.md](../modules/requirements/usage.md) | 模块文档 | 描述软件实现、使用或兼容入口；不重复阶段工作规范 |
| [docs/modules/requirements/verification.md](../modules/requirements/verification.md) | 模块文档 | 描述软件实现、使用或兼容入口；不重复阶段工作规范 |
| [docs/modules/requirements/web-design.md](../modules/requirements/web-design.md) | 模块历史设计 | 兼容网页设计与移除记录，保留原位 |
| [docs/reports/2026-11-07-session-report-luna.md](../reports/2026-11-07-session-report-luna.md) | 验证与过程证据 | 保持历史结论与限制；按索引访问，不改写成当前实测 |
| [docs/reports/2026-11-07-session-report-sonnet-5-5.md](../reports/2026-11-07-session-report-sonnet-5-5.md) | 验证与过程证据 | 保持历史结论与限制；按索引访问，不改写成当前实测 |
| [docs/requirements/REQ-DEPLOY-WEB_DAEMON-20261108.md](../requirements/REQ-DEPLOY-WEB_DAEMON-20261108.md) | 正式 SRS | AutoDev 自身需求；程序读写目录及测试依赖，保留路径与内容 |
| [docs/requirements/REQ-WEB-UNIFIED_CLIENT-20261107.md](../requirements/REQ-WEB-UNIFIED_CLIENT-20261107.md) | 正式 SRS | AutoDev 自身需求；程序读写目录及测试依赖，保留路径与内容 |
| [docs/specs/REQUIREMENT_SPEC_STANDARD.md](../specs/REQUIREMENT_SPEC_STANDARD.md) | 跨阶段规范 | SRS v1.1；测试按路径读取，原位保留 |
| [docs/spikes/2026-11-04-autoloop-test-report.md](../spikes/2026-11-04-autoloop-test-report.md) | 验证与过程证据 | 保持历史结论与限制；按索引访问，不改写成当前实测 |
| [docs/spikes/2026-11-05-autoloop-test-report-v2.md](../spikes/2026-11-05-autoloop-test-report-v2.md) | 验证与过程证据 | 保持历史结论与限制；按索引访问，不改写成当前实测 |
| [docs/spikes/2026-11-05-f1-agents-report.md](../spikes/2026-11-05-f1-agents-report.md) | 验证与过程证据 | 保持历史结论与限制；按索引访问，不改写成当前实测 |
| [docs/spikes/2026-11-05-f2-pipeline-report.md](../spikes/2026-11-05-f2-pipeline-report.md) | 验证与过程证据 | 保持历史结论与限制；按索引访问，不改写成当前实测 |
| [docs/spikes/2026-11-06-f3-real-run-report.md](../spikes/2026-11-06-f3-real-run-report.md) | 验证与过程证据 | 保持历史结论与限制；按索引访问，不改写成当前实测 |
| [docs/stages/README.md](../stages/README.md) | 阶段工作契约 | S2/S3 分 README/contract/standard；其余阶段单一 README，不放运行产物 |
| [docs/stages/S1-analysis/README.md](../stages/S1-analysis/README.md) | 阶段工作契约 | S2/S3 分 README/contract/standard；其余阶段单一 README，不放运行产物 |
| [docs/stages/S2-design/README.md](../stages/S2-design/README.md) | 阶段工作契约 | S2/S3 分 README/contract/standard；其余阶段单一 README，不放运行产物 |
| [docs/stages/S2-design/contract.md](../stages/S2-design/contract.md) | 阶段工作契约 | S2/S3 分 README/contract/standard；其余阶段单一 README，不放运行产物 |
| [docs/stages/S2-design/standard.md](../stages/S2-design/standard.md) | 阶段工作契约 | S2/S3 分 README/contract/standard；其余阶段单一 README，不放运行产物 |
| [docs/stages/S3-design-review/README.md](../stages/S3-design-review/README.md) | 阶段工作契约 | S2/S3 分 README/contract/standard；其余阶段单一 README，不放运行产物 |
| [docs/stages/S3-design-review/contract.md](../stages/S3-design-review/contract.md) | 阶段工作契约 | S2/S3 分 README/contract/standard；其余阶段单一 README，不放运行产物 |
| [docs/stages/S3-design-review/standard.md](../stages/S3-design-review/standard.md) | 阶段工作契约 | S2/S3 分 README/contract/standard；其余阶段单一 README，不放运行产物 |
| [docs/stages/S4-code/README.md](../stages/S4-code/README.md) | 阶段工作契约 | S2/S3 分 README/contract/standard；其余阶段单一 README，不放运行产物 |
| [docs/stages/S5-check/README.md](../stages/S5-check/README.md) | 阶段工作契约 | S2/S3 分 README/contract/standard；其余阶段单一 README，不放运行产物 |
| [docs/stages/S6-code-review/README.md](../stages/S6-code-review/README.md) | 阶段工作契约 | S2/S3 分 README/contract/standard；其余阶段单一 README，不放运行产物 |
| [docs/stages/S7-release/README.md](../stages/S7-release/README.md) | 阶段工作契约 | S2/S3 分 README/contract/standard；其余阶段单一 README，不放运行产物 |
| [docs/stages/S7U-usage/README.md](../stages/S7U-usage/README.md) | 阶段工作契约 | S2/S3 分 README/contract/standard；其余阶段单一 README，不放运行产物 |
| [docs/stages/S8-acceptance/README.md](../stages/S8-acceptance/README.md) | 阶段工作契约 | S2/S3 分 README/contract/standard；其余阶段单一 README，不放运行产物 |
| [docs/stages/S9-publish/README.md](../stages/S9-publish/README.md) | 阶段工作契约 | S2/S3 分 README/contract/standard；其余阶段单一 README，不放运行产物 |
| [next.md](../../next.md) | 平台入口与公共记录 | 保持固定入口；现行目标在 next，决定/经验分别维护 |
| [reference/INDEX.md](../../reference/INDEX.md) | 外部参考 | 来源与边界见 reference/INDEX，不覆盖项目决策 |
| [reference/Super-agent设计探索-离线存档.html](../../reference/Super-agent设计探索-离线存档.html) | 外部参考 | 来源与边界见 reference/INDEX，不覆盖项目决策 |
| [reference/agent-autoloop/README.md](../../reference/agent-autoloop/README.md) | 外部参考 | 来源与边界见 reference/INDEX，不覆盖项目决策 |
| [reference/agent-autoloop-classification.md](../../reference/agent-autoloop-classification.md) | 外部参考 | 来源与边界见 reference/INDEX，不覆盖项目决策 |
| [reference/帖子离线存档.html](../../reference/帖子离线存档.html) | 外部参考 | 来源与边界见 reference/INDEX，不覆盖项目决策 |
| [templates/requirements/clarify.md](../../templates/requirements/clarify.md) | 兼容文档模板 | 仅适用版本化兼容入口；不得冒充默认 SRS 或 V2.1 模板 |
| [templates/requirements/review.md](../../templates/requirements/review.md) | 兼容文档模板 | 仅适用版本化兼容入口；不得冒充默认 SRS 或 V2.1 模板 |

## 3. 程序路径依赖与不迁移边界

| 文件或目录 | 依赖种类与证据 | 本轮处理 |
| --- | --- | --- |
| `templates/pipeline/*.json` | pipeline.load_template 读取，build 继承 design | 内容/位置不变 |
| `templates/requirements/*.md` | 版本化兼容需求模板，由 requirements.agent 读取 | 内容/位置不变，不迁入默认 SRS 阶段 |
| `design-system/rules/`、`schemas/` | designsys.classify/rules/validate 按路径读取 | 资产内容不变，仅新增 README |
| `docs/requirements/` | service/context_detector/web.api/web.server 读写；test_web_client 读两份固定 SRS | 两份内容与位置不变 |
| `docs/specs/REQUIREMENT_SPEC_STANDARD.md`、`docs/modules/requirements/feishu-requirement-bot.md` | test_requirements_validator 按路径读取规范与黄金范本 | 内容/位置不变 |
| `docs/modules/requirements/baselines/` 及其 `../design.md` | 固定基线有相对链接；SRS 也引用早期 requirements.md | 全部原位保留，不改固定副本或已校验 SRS |
| `docs/MODELS.md`、`docs/DECISIONS.md` | config/agents.toml 的 evidence/注释，及源码/界面说明 | 保留固定入口；不是全部运行时读取 |
| `docs/DATA_SPEC.md`、工单模型、V2.1 采用对照 | kinds.py 和 classification.toml 的说明引用 | 保留路径；属于注释证据依赖 |
| `docs/design/autodev-workflow-prototype.html` | web.ui.html 中的引用 | 原位保留，不当运行设计包 |
| `workspace/`、目标项目自身文档 | 运行状态/产物、兼容会话、归档、正式项目输入 | 本轮不处理，不合并、不迁移 |

## 4. 内容迁移与保留清单

| 原位置 | 当前维护位置 | 信息保留与兼容方式 |
| --- | --- | --- |
| stage-bots-design 第 8.2/8.3 节 | [S2 contract](../stages/S2-design/contract.md) | 输入清单、版本/快照与读取范围；原章节保留标题和链接 |
| 同文第 8.4/8.5 节 | [S2 standard](../stages/S2-design/standard.md)及 contract | 工具分工、工作步骤、完成与交付；依 D026 标出原型旧规则被替代 |
| 同文第 8.6 节 | [S3 standard](../stages/S3-design-review/standard.md) | D019 分级审核表及证据要求集中维护；当前结果协议另在 contract |
| 原第 8 节的完整文本 | [历史原文](../archive/2026-11-09-design-bot-work-instructions-v01.md) | 保留独有历史和旧规则；仅修正移动后的相对链接，不成为第二份当前规范 |
| next.md 的历史目标与追溯 | [整理前快照](../archive/2026-11-09-next-before-stage-docs.md) | 代码块内原文逐字保留；当前 next 只留有效状态、目标与未决事项 |
| S4 早期设计稿 | 原位，链接到 S4 README | 基于源码标为历史，不把旧“未实现”当成当前事实，也不宣称所有旧实验通过 |
| 两份旧设计、早期需求协议 | 既有 archive 路径 | 前轮已完成，本轮补归档导航，不重复搬迁 |

## 5. 还需要什么

| 层次 | 结论 | 后续触发条件 |
| --- | --- | --- |
| 目录与导航 | 本轮已补总目录职责、十阶段入口、S2/S3 契约/标准、执行资产入口与历史入口 | 新增文件时维护所属入口和本索引，不新增重复事实源 |
| 其余八阶段的 contract/standard | 当前 README 已承载完整简要契约，不机械拆文件 | 职责内容变长、有独立输入输出协议时再拆 |
| 阶段 templates/examples | 本轮不建空目录；已有机器模板、兼容模板与结构化 Schema 分别归位 | 用真实设计任务形成稳定需求后，增加匿名案例/反例和必要文档模板 |
| V2.1 接入与产物 | 缺新模板/受控写范围、关键特征核对、程序验证路由、版本与持久化交接；UI/API 产物和原型检查尚不完整 | 下一轮先评估默认能力与影响清单，再定实施范围；不是文档目录任务未完成 |
| D019 与人工决定 | 分级放行记录/执行尚缺；D2 默认、模型建议与冲突规则待确认 | 与接入设计一起定，不借目录整理改变运行语义 |
| 历史与兼容入口 | 固定基线、SRS 仍引用的旧稿有保留理由 | 消费者或协议正式迁移时再处理，不为整齐制造断链 |

通用 docsync 的固定路径提示使用项目等价映射：requirements → 本项目需求稿/正式 SRS；architecture → 当前地基与平台设计；implementation → 阶段、模块、工具说明；changelog/next → 根目录同名文件。它未提供本项目全部链接和路径的证明，最终检查范围与结果见执行记录。
