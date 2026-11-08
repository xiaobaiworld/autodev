# 文档与关键文件索引

更新日期：2026-11-07

本索引按用途列出当前有效的入口、设计与参考资料。状态描述的是 AutoDev 自身资料的权威性；外部参考不能覆盖项目决策。已被取代的文档在 `docs/archive/`，只供追溯。

## 项目入口与状态

| 路径 | 职责 | 状态与权威性 |
| --- | --- | --- |
| `README.md` | 项目简介与入口 | 当前项目入口 |
| `AGENTS.md`、`CLAUDE.md` | 给 Agent 的项目说明；第一步是先查 `docs/TOOLS.md`（`CLAUDE.md` 只引用 `AGENTS.md`） | 每次开始任务先读 |
| `docs/TOOLS.md` | 已确定的工具、在线文档链接、跑通过的命令、环境坑 | 找任何功能之前先查这里；查到新用法要补回 |
| `next.md` | 当前阶段、已验证事项、下一步、仍然开放的问题 | 当前工作状态，每个阶段结束后更新 |
| `AGENT_HANDOFF.md` | 换机器时的仓库获取方式、personagent 本地补丁的转移方法 | 只在换机器时读；其中的“当前状态”以 `next.md` 为准 |
| `config.yaml` | 项目、Agent（CLI、厂商、完整模型 ID、强度）、角色绑定、各关口轮次上限 | 配置；模型名规则见 `docs/MODELS.md` |
| `docs/guides/rerun-with-another-agent.md` | 想用别的 Agent 或模型再跑一遍并比较：分清驾驶员、流水线里的 Agent、模型三层；怎么换、先跑哪些不花额度的验证、怎么比较、已知的坑 | 操作指南 |
| `docs/reports/2026-11-07-session-report-sonnet-5-5.md` | 一次完整会话的报告：完成了什么、能证明什么、不能证明什么、驾驶员犯过的错。以后换驾驶员重做时的比较底稿 | 报告，只追加新报告，不改旧的 |

## 设计与决策

| 路径 | 职责 | 状态与权威性 |
| --- | --- | --- |
| `docs/design/2026-11-05-autoloop-foundation.md` | 以 agent-autoloop 为地基的方案：结构、F0 到 F6、界面共用数据、待决事项 | 当前主线 |
| `docs/modules/requirements/README.md` | 需求澄清独立模块入口：需求、状态循环、协议与开发计划 | v0.8 需求已确认，已实现；独立后端供 CLI、网页及上层项目复用，验证见模块 verification.md |
| `docs/modules/requirements/baselines/v0.8.md` | 包含可选模型、双模型审核及人工确认的固定需求副本 | 用户确认的 v0.8 基线，后续变更另建版本 |
| `docs/modules/requirements/web-design.md` | 网页工作台分区、页签、待办与真实入口 | 已实现并做浏览器验证 |
| `docs/modules/requirements/usage.md` | CLI/网页启动、演示与真实模型、恢复和测试 | 当前使用入口 |
| `docs/modules/requirements/verification.md` | 250 项自动测试、浏览器及真实双模型证据与限制 | 验证记录 |
| `docs/modules/requirements/channels.md` | 手机端通用组件与飞书/微信接线边界 | 通用组件及飞书已接，手机验收待用户发命令 |
| `docs/modules/requirements/dev-plan.md` | M1～M6 的文件范围、测试、验收、复用边界及提交收口 | 当前实施计划，执行证据见 verification.md |
| `docs/design/2026-11-06-ticket-model.md` | 工单分类、拆解、确定化、成熟工具：用户的要求与待讨论问题 | 提议，只记录，未实现未验证 |
| `docs/design/2026-11-08-stage-bots-requirements.md` | 需求、开发、测试、优化阶段机器人的用户目标与建议验收 | 讨论稿，范围细节待确认 |
| `docs/design/2026-11-08-stage-bots-design.md` | 五工作区、角色上下文、交接与协作展示；第 8 节为渠道独立的设计机器人工作说明 v0.1 | 三层划分已接受，具体契约待讨论，未实现 |
| `docs/design/2026-11-02-autodev-design.md` | 九阶段流水线、角色、产物、人工参与、Web 界面、复盘、规则 | 当前设计基线；第 3.2、3.3、5 节的执行与调度部分已被地基方案部分取代，各节顶部有说明 |
| `docs/OPTIMIZATIONS.md` | 流程优化记录：每次小优化改了什么、为什么、怎么回退、效果量到多少；只追加，回退和反复都如实记 | 只记优化这一件事；没量过写“未测” |
| `docs/DECISIONS.md` | 重要方向及决策依据，D001 到 D019 | 决策事实源；D020 分层及 D019 分级审查原则已接受，实施细节待定 |
| `docs/DATA_SPEC.md` | 数据目录、实体与文件格式 | 设计规范；`state.json`、`done.json` 已在代码里使用 |
| `docs/MODELS.md` | 模型名规则：只写完整 ID、magpie 映射原因、各 CLI 的指定方式 | 规则；改 `config.yaml` 的 `agents` 或写启动命令前必读 |
| `docs/lessons.md` | 已踩的坑与验证过的做法，L001 到 L012 | 开始新功能前先读 |
| `docs/design/autodev-workflow-prototype.html` | 工作流界面原型 | 静态讨论稿，示例数据，不代表可运行系统 |

## 验证记录

| 路径 | 内容 |
| --- | --- |
| `docs/spikes/2026-11-04-autoloop-test-report.md` | autoloop v1 验证报告：G1、G2、G6 可信，G3、G4、G7 判定不可靠，G5 未跑 |
| `docs/spikes/2026-11-05-autoloop-test-report-v2.md` | v2 补测：只确认 G5 方式 A |
| `docs/spikes/2026-11-05-f1-agents-report.md` | F1：Claude、Codex、agy 无界面各跑一轮 |
| `docs/spikes/2026-11-05-f2-pipeline-report.md` | F2：我们的流水线跑在 autoloop 上，S1 到 S3 跑通 |
| `docs/spikes/2026-11-06-f3-real-run-report.md` | F3：真实流水线在 Herdr 三格里实时跑，日志与看板同步 |

## 代码与测试

| 路径 | 内容 |
| --- | --- |
| `src/driver/` | 向 autoloop 中台发事件、读事实流（`hub.py`、`runner.py`）；每步写记录（`record.py`）；两次运行的确定性比对（`compare.py`）；生成并安装规则（`setup.py`）；启动一个需求 `run.py`；人工回复 `reply.py`（批准、退回、拒绝） |
| `src/cockpit/` | 需求类型登记（`kinds.py`）；阶段表、转移规则、输入清单、产物校验（`pipeline.py`，都读 `templates/pipeline/`）；主循环与人工回复入口 `resume`（`controller.py`）；程序步骤 `check`、`release`（`tools.py`）；代码目录的 git 操作（`workdir.py`）；状态落盘（`store.py`）；`config.yaml` 读取（`agents.py`）。窗格驱动的旧方案已在 F6 移除 |
| `templates/pipeline/` | 流水线模板：每个 `pipeline/*` 类型一个 JSON（`build` 继承 `design`），写阶段顺序、角色、产物、可选结论、结论去向、输入文件、必须有的小节、人工关口和任务说明；改这里即改下一次运行 |
| `src/dashboard/` | 命令行看板与日志窗格 |
| `tests/` | 单元测试；`smoke_autoloop.py`、`f1_agents.py`、`f2_pipeline.py`、`f5_crash.py` 是联机验证脚本。`f1_agents.py` 和不带任何参数的 `f2_pipeline.py` 花额度；`f2_pipeline.py --build`（跑完整 S1 到 S9）、`--fake-rework`、`f5_crash.py` 用假 Agent，不花额度 |

## 参考资料

| 路径 | 职责 | 状态与权威性 |
| --- | --- | --- |
| `reference/INDEX.md` | 外部资料目录、来源与使用边界 | 外部参考索引，不是产品规范 |
| `reference/agent-autoloop-classification.md` | autoloop 作者自己怎么给任务分类（七个场景、权限与问人红线、GitHub 标签） | 基于线上 `main` 的归纳，部分是推断，文中已标明 |
| `reference/agent-autoloop/README.md` | 上游项目结构与流程机制分析 | 基于上游公开资料；已采纳为地基（D014） |
| `reference/帖子离线存档.html`、`reference/Super-agent设计探索-离线存档.html` | 已保存的外部文章 | 外部原始资料 |

## 已归档

`docs/archive/`：驾驶舱设计与开发计划、autoloop 测试计划 v1 与 v2、空的 `goal.md` 模板。每份文件顶部有被谁取代的说明。

## 索引维护

新增或移动重要项目文件时更新本索引。外部参考另在 `reference/INDEX.md` 登记；分析结论若被采纳，须进入项目设计或决策记录。
