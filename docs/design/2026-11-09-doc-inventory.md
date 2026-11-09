# 文档清点清单（文档整理第 2 步）

日期：2026-11-09。状态：**待用户逐项审核**。本清单只读生成，**没有移动、改名或删除任何文件**。依据：[审核意见](2026-11-09-doc-organization-review.md)第 5 节第 2 步。

## 1. 怎么看这份清单

共 53 个文件（`docs/` 下除归档外全部，加根目录 Markdown 与 `reference/` 两份）。每行给出类别、判定理由和建议处理。你只需要对**有异议的行**说“不同意，应该是 X”，其余视为同意。

“被代码引用”一栏只在**程序、测试或配置按完整路径读取该文件**时标注；同名但含义不同的不算，见第 4 节。

## 2. 类别说明

| 类别 | 含义 | 文件数 |
| --- | --- | --- |
| A | 平台入口与总账（保持原位） | 10 |
| B | 平台设计与规范（AutoDev 自身如何工作） | 13 |
| C | 阶段契约候选（将来可迁入 docs/stages/） | 1 |
| D | 程序读写的运行产物或程序引用的文件（不得迁移，或迁移须同步改代码） | 8 |
| E | 已被取代或早期草案（建议移入归档，保留指向替代者的链接） | 5 |
| F | 验证与过程记录（历史证据，保留，可按主题归并） | 14 |
| G | 外部参考（保留） | 2 |

## 3. 逐项清单

| 文件 | 类别 | 标题 | 最后提交 | 被代码引用 | 判定理由 | 建议处理 |
| --- | --- | --- | --- | --- | --- | --- |
| `README.md` | A | AutoDev (`v0.3.3`) | 2026-11-08 | 否 | 项目入口，被 pipeline 测试按名使用的是目标项目的 README，不是本文件 | 保持 |
| `AGENTS.md` | A | AutoDev：给 Agent 的项目说明 | 2026-11-08 | 否 | Agent 项目说明，CLAUDE.md 引用它 | 保持 |
| `CLAUDE.md` | A | — | 2026-11-06 | 否 | 仅一行引用 AGENTS.md | 保持 |
| `next.md` | A | next.md | 2026-11-09 | 否 | 当前工作入口，已在第 1 步整理 | 保持 |
| `changelog.md` | A | changelog | 2026-11-09 | 否 | 变更记录，全局规范要求每次提交同步 | 保持 |
| `AGENT_HANDOFF.md` | A | AutoDev 跨机器 Agent 交接（2026-11-03 起草，2026-11-06 精简） | 2026-11-06 | 否 | 仅换机器时读，2026-11-06 后未更新，内容可能过时 | 保持，核对后更新 |
| `docs/INDEX.md` | A | 文档与关键文件索引 | 2026-11-09 | 否 | 总索引 | 保持，随迁移同步 |
| `docs/DECISIONS.md` | A | AutoDev 决策记录 | 2026-11-09 | 是 | 决策事实源；被 config/agents.toml 引用 | 保持原位 |
| `docs/lessons.md` | A | lessons.md | 2026-11-09 | 否 | 经验库；全局规范要求先读 | 保持原位 |
| `docs/TOOLS.md` | A | 工具手册（已确定的工具和用法） | 2026-11-09 | 否 | 工具手册；AGENTS.md 要求第一步先查 | 保持原位 |
| `docs/DATA_SPEC.md` | D | AutoDev 数据规范 | 2026-11-09 | 是 | 数据规范；被 src/cockpit/kinds.py 的注释引用，新增类型要写进它 | 保持原位 |
| `docs/MODELS.md` | D | 模型名规则（2026-11-05） | 2026-11-08 | 是 | 模型名规则；被 config/agents.toml、cockpit/agents.py、llm_provider.py、web/ui.html 引用 | 保持原位 |
| `docs/OPTIMIZATIONS.md` | F | 流程优化记录 | 2026-11-07 | 否 | 流程优化记录，只追加 | 保持 |
| `docs/Agent自动化设计阶段规范_V2.1.md` | B | Agent 自动化设计阶段规范 V2.1 | 2026-11-09 | 否 | 设计阶段当前主规范（D026） | 保持；第 3 步试点时由 stages/S2-design 引用 |
| `docs/design/2026-11-02-autodev-design.md` | B | AutoDev 流程设计（2026-11-02） | 2026-11-08 | 否 | 九阶段流水线总设计，README 与 INDEX 都当基线；部分章节已被地基方案取代，各节顶部有说明 | 保持 |
| `docs/design/2026-11-05-autoloop-foundation.md` | B | 以 agent-autoloop 为地基：融合方案（2026-11-05） | 2026-11-08 | 否 | 地基方案（D014），AGENTS.md 指定为当前主线 | 保持 |
| `docs/design/2026-11-06-s4-code-stage.md` | C | S4 编码阶段设计（2026-11-06） | 2026-11-08 | 否 | S4 编码阶段设计，状态“提议，未实现”，没有任何文档引用它 | 候选迁入 stages/S4-code，先确认是否仍有效 |
| `docs/design/2026-11-06-ticket-model.md` | D | 工单模型：分类、拆解、确定化、成熟工具（2026-11-06） | 2026-11-06 | 是 | 工单模型讨论，被 src/cockpit/kinds.py 的注释引用 | 保持原位，或迁移时同步改代码注释 |
| `docs/design/2026-11-08-agent-model-registry.md` | B | 本机 Agent 与模型能力注册表 | 2026-11-08 | 否 | D021 注册表契约，已实现 | 保持 |
| `docs/design/2026-11-08-requirements-merge.md` | B | 需求工作台分支整合 | 2026-11-09 | 否 | D018 整合范围 | 保持 |
| `docs/design/2026-11-08-stage-bots-design.md` | B | 阶段机器人与协作展示：设计草案 | 2026-11-09 | 否 | 阶段机器人设计；第 8 节含设计机器人工作说明，与阶段契约交织（提案指出的问题） | 保持，第 3 步试点时把 S2/S3 细节拆到 stages，平台关系留在这里 |
| `docs/design/2026-11-08-stage-bots-requirements.md` | B | 阶段机器人：需求讨论稿 | 2026-11-08 | 否 | 阶段机器人需求讨论稿 | 保持 |
| `docs/design/2026-11-09-v21-mapping.md` | B | 设计阶段：采用 V2.1 的对照与补充 | 2026-11-09 | 是 | 采用 V2.1 的对照，D026 详细说明；被 design-system 规则文件引用 | 保持原位 |
| `docs/design/2026-11-09-doc-organization-review.md` | B | 文档组织提案的审核意见与分步执行 | 2026-11-09 | 否 | 本次文档整理的审核与步骤 | 保持 |
| `docs/design/2026-11-09-document-organization-proposal.md` | B | AutoDev 文档组织检查与阶段目录提案 | 2026-11-09 | 否 | 外部 Agent 的提案 | 保持 |
| `docs/archive/2026-11-09-design-exit-and-grading.md` | E | 设计阶段的出口、复杂度分级与按类型的完成条件 | 2026-11-09 | 否 | 已被 D026 取代（三档复杂度、五个事实、已定稿出口） | **已移入 docs/archive/（2026-11-09）**，INDEX 已同步 |
| `docs/archive/2026-11-09-design-cases-and-templates.md` | E | 设计阶段：典型需求、判定标准、结果与模板 | 2026-11-09 | 否 | 按已取代的三档规则生成 | **已移入 docs/archive/（2026-11-09）** |
| `docs/design/autodev-workflow-prototype.html` | D | — | 2026-11-04 | 否 | 静态原型，被 src/web/ui.html 引用 | 保持原位 |
| `docs/specs/REQUIREMENT_SPEC_STANDARD.md` | D | 软件与部署需求规格说明书产出规范与校验标准 (SRS Standard v1.1) | 2026-11-08 | 是 | SRS 规范；tests/test_requirements_validator.py:117 按路径读取其内容，迁移会让测试失败 | 保持原位 |
| `docs/requirements/REQ-WEB-UNIFIED_CLIENT-20261107.md` | D | 软件需求规格说明书：AutoDev 全系统统一网页客户端（需求澄清工作台 + S1~S9 流水线驾驶舱） | 2026-11-07 | 是 | AutoDev 统一网页客户端的 SRS。**docs/requirements/ 是程序读写的目录**（service.py:263、web/api.py:51），测试 test_web_client.py 按路径读取 | 不得迁移 |
| `docs/requirements/REQ-DEPLOY-WEB_DAEMON-20261108.md` | D | 软件需求规格说明书（部署工程规范）：AutoDev 统一网页客户端本机守护部署与健康自检工程 | 2026-11-08 | 是 | 同上，部署类 SRS | 不得迁移 |
| `docs/config/agent-registry.example.toml` | D | 教学样例，可用 cockpit.registry --file 校验，不是本机运行清单。 | 2026-11-08 | 否 | 注册表教学样例，被 INDEX 与 MODELS 引用，可用 cockpit.registry 校验 | 保持原位 |
| `docs/guides/rerun-with-another-agent.md` | F | 换一个 Agent 再跑一遍，并比较差别 | 2026-11-08 | 否 | 操作指南 | 保持 |
| `docs/modules/requirements/README.md` | B | 需求澄清模块 (Requirements Clarification Module) | 2026-11-09 | 否 | 需求澄清模块入口；代码里出现的 README.md 指目标项目的 README，不是本文件 | 保持 |
| `docs/modules/requirements/feishu-requirement-bot.md` | B | 需求澄清模块与飞书端沉淀说明书 | 2026-11-09 | 是 | 飞书需求机器人说明书；tests/test_requirements_validator.py:104、119 按路径读取其中的黄金范本，迁移会让测试失败 | 保持原位 |
| `docs/modules/requirements/usage.md` | B | 需求工作台使用 | 2026-11-09 | 否 | 版本化兼容工作台的使用（D018 兼容入口） | 保持 |
| `docs/modules/requirements/dev-plan.md` | F | 需求澄清模块 v0.9 开发计划 | 2026-11-08 | 否 | v0.9 开发计划，M1–M5 已执行，是历史计划 | 保持，可后移入归档 |
| `docs/modules/requirements/verification.md` | F | 需求工作台验证记录 | 2026-11-09 | 否 | 兼容工作台验证记录，已加移除说明 | 保持 |
| `docs/modules/requirements/web-design.md` | F | 网页工作台设计与本轮范围 | 2026-11-09 | 否 | 旧网页设计，已加移除说明 | 保持，可后移入归档 |
| `docs/modules/requirements/baselines/v0.8.md` | F | 需求澄清模块：需求与验收 | 2026-11-07 | 否 | 固定需求基线副本（历史确认版本） | 保持，固定副本不改 |
| `docs/modules/requirements/baselines/v0.9.md` | F | 需求澄清模块：需求与验收 | 2026-11-07 | 否 | 同上 | 保持，固定副本不改 |
| `docs/modules/requirements/design.md` | E | 需求澄清模块：设计与实现计划（早期草案，已被现行架构取代） | 2026-11-08 | 否 | 标题自称“早期草案，已被现行架构取代”；README 仍列为参考；baselines 里有指向它的相对链接 ../design.md | 移入归档须同步改 v0.8、v0.9 的链接，且基线是固定副本——先决定是否允许改链接 |
| `docs/archive/2026-11-08-requirements-protocol-early-draft.md` | E | 第一版程序协议（早期草案，已被 `SPEC-REQ-STANDARD-v1.0` 取代） | 2026-11-08 | 否 | 标题自称“已被 SPEC-REQ-STANDARD-v1.0 取代” | **已移入 docs/archive/（2026-11-09）**，README、design.md、dev-plan.md 的引用已同步 |
| `docs/modules/requirements/requirements.md` | E | 需求澄清模块：需求与验收（早期草案，已被 v0.3.2 标准规范吸收与取代） | 2026-11-08 | 否 | 标题自称“已被 v0.3.2 标准规范吸收与取代”；REQ-WEB-UNIFIED_CLIENT 仍引用它 | 移入归档须同步改 SRS 里的引用，而 SRS 是程序校验过的文档——谨慎 |
| `docs/reports/2026-11-07-session-report-luna.md` | F | Luna 驾驶员复测报告：真实跑完 S1–S9 并与 Sonnet 对照 | 2026-11-08 | 否 | Luna 复跑报告 | 保持 |
| `docs/reports/2026-11-07-session-report-sonnet-5-5.md` | F | 一次完整会话的报告：Claude Sonnet 5.5 驾驶，把流水线从 S3 接到 S9 | 2026-11-07 | 否 | Sonnet 会话报告 | 保持 |
| `docs/spikes/2026-11-04-autoloop-test-report.md` | F | agent-autoloop 验证报告 | 2026-11-05 | 否 | autoloop 验证报告 v1 | 保持 |
| `docs/spikes/2026-11-05-autoloop-test-report-v2.md` | F | agent-autoloop 补测报告 v2（2026-11-05） | 2026-11-05 | 否 | autoloop 补测 v2 | 保持 |
| `docs/spikes/2026-11-05-f1-agents-report.md` | F | F1 报告：agent-autoloop 上真实 Agent 无界面各跑一轮（2026-11-05） | 2026-11-05 | 否 | F1 报告 | 保持 |
| `docs/spikes/2026-11-05-f2-pipeline-report.md` | F | F2 报告：我们的流水线驱动跑在 autoloop 上（2026-11-05） | 2026-11-05 | 否 | F2 报告 | 保持 |
| `docs/spikes/2026-11-06-f3-real-run-report.md` | F | F3 报告：真实流水线在 Herdr 三格里实时跑（2026-11-06） | 2026-11-06 | 否 | F3 报告 | 保持 |
| `reference/INDEX.md` | G | 参考资料索引 | 2026-11-09 | 否 | 参考资料索引 | 保持 |
| `reference/agent-autoloop-classification.md` | G | agent-autoloop 作者自己怎么分类任务（2026-11-06） | 2026-11-06 | 否 | autoloop 作者的分类方法 | 保持 |
## 4. 关于“被代码引用”的说明

清点时我先用“文件名”搜代码，得到 16 个，其中大部分是误报；改用“完整路径”后只剩 6 个；再补上“路径被分段拼接”的写法（如 `os.path.join(root, "docs", "specs", "X.md")`）才得到真实的 9 个。**迁移前必须按这 9 个核对，用文件名或单一路径搜索都会漏。**

真实被程序按路径读取的文档：

| 文档 | 谁读它 | 迁移的后果 |
| --- | --- | --- |
| `docs/DATA_SPEC.md` | `src/cockpit/kinds.py` 的注释指向它 | 只是注释，迁移后注释失效，不影响运行 |
| `docs/DECISIONS.md`、`docs/MODELS.md` | `config/agents.toml` 的 `evidence` 字段和注释 | 配置里的证据路径失效 |
| `docs/design/2026-11-06-ticket-model.md` | `src/cockpit/kinds.py` 的注释 | 注释失效 |
| `docs/design/2026-11-09-v21-mapping.md` | `design-system/rules/classification.toml` 的注释 | 注释失效 |
| `docs/specs/REQUIREMENT_SPEC_STANDARD.md` | `tests/test_requirements_validator.py:117` 读取内容 | **测试失败** |
| `docs/modules/requirements/feishu-requirement-bot.md` | `tests/test_requirements_validator.py:104、119` 读取其中的黄金范本 | **测试失败** |
| `docs/requirements/REQ-WEB-UNIFIED_CLIENT-20261107.md`、`REQ-DEPLOY-WEB_DAEMON-20261108.md` | `tests/test_web_client.py` 多处；且 `docs/requirements/` 本身是 `service.py:263`、`web/api.py:51` 读写需求文档的目录 | **测试失败，运行时需求文档存取失效** |

误报的来源（名字相同、含义不同，不算依赖）：

- `README.md`：`src/cockpit/pipeline.py:314` 读的是**目标项目**的 README，不是本仓库的。
- `design.md`、`dev-plan.md`、`prototype.md`：`pipeline.py` 与 `design_view.py` 读的是**每次运行产出的文件**，不是 `docs/modules/requirements/design.md` 这几份。
- `requirements.md`：`responder.py:61`、`versioned_session.py:302` 是代码里生成的文件名，与文档无关。

**我清点时的错误，订正如下**：

1. 分类表第一版写“`SRS 规范` 被 `test_requirements_validator.py` 按路径读取”，我当时没有证据，只是推测；复核后确认它确实读取，但读的是 `REQUIREMENT_SPEC_STANDARD.md` 和 `feishu-requirement-bot.md`，不是我最初写的 README。已订正。
2. 第一版把 `docs/modules/requirements/README.md` 也列为“被代码引用”，这是文件名误报，已去掉。

## 5. 建议的处理（供你决定，尚未执行）

按风险从低到高：

| 编号 | 动作 | 涉及文件 | 风险 | 前置条件 |
| --- | --- | --- | --- | --- |
| 1 | 把已被 D026 取代的两份设计文档移入 `docs/archive/` | `design-exit-and-grading.md`、`design-cases-and-templates.md` | 低：没有代码引用，INDEX 已标注“已被取代” | 同步改 INDEX 与 v21-mapping 中指向它们的链接 |
| 2 | `docs/modules/requirements/protocol.md` 移入归档 | 一份 | 低：只被 README 与另两份早期文档引用 | 改 README 第 35 行；`design.md` 第 121 行的链接随 `design.md` 一起处理 |
| 3 | `design.md`、`requirements.md` 移入归档 | 两份 | **中**：`baselines/v0.8.md`、`v0.9.md` 用相对链接指向 `../design.md`，而基线是**固定副本，不应改动**；`REQ-WEB-UNIFIED_CLIENT` 引用了 `requirements.md`，而该文档是程序校验过的 SRS | 先决定：是否允许改固定基线里的链接；是否允许改已校验 SRS 里的引用。**我建议不动这两份**，保留原位并在文件头加“已被取代，见某某”的说明 |
| 4 | `2026-11-06-s4-code-stage.md` 的去向 | 一份 | 低：状态“提议，未实现”，没有任何文档引用 | 先确认 S4 设计是否仍有效；有效则试点后迁入 `stages/S4-code`，无效则归档 |
| 5 | `stage-bots-design.md` 把 S2/S3 细节拆到 `stages/` | 一份 | 中：34863 字节，内容交织 | 第 3 步试点时做，不在这一轮动 |
| 6 | 第 3 步试点 `docs/stages/S2-design/` 与 `S3-design-review/` | 新建 | 中 | 你确认目录方案，以及与 `design-system/` 的关系 |

**不得迁移的**（程序会读）：第 4 节表里那 9 个，以及整个 `docs/requirements/` 目录。

## 6. 需要你决定的

1. 第 5 节 1、2 两项（风险低）可以直接做吗？
2. 第 5 节 3 项：`design.md` 与 `requirements.md` 是否按我的建议**保留原位、只加“已被取代”说明**，而不是移走？
3. `2026-11-06-s4-code-stage.md` 是否仍有效？
4. 提案里“用户反馈阶段分别组织文档的基本方向可以”这一句，我没有直接记录，进入第 3 步试点前需要你再确认目录方案：`docs/stages/` 放契约与说明、`design-system/` 放可执行资产，二者互相引用。
