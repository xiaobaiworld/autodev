# AutoDev (`v0.3.3`)

AutoDev 是本机运行的需求驱动开发流程。确定性程序控制阶段、轮次和状态，Agent（Claude、Codex、agy）分别负责需求分析、设计、编码、审查和验收。

## 当前状态（版本 `v0.3.3`）

以 [agent-autoloop](https://github.com/KKKKhazix/agent-autoloop) 为地基（`docs/DECISIONS.md` D014）：它负责派活、排队、重试、租约、事实日志，Agent 以无界面进程运行；我们的流水线驱动放在它外面，管阶段、审查策略、轮次上限和产物校验。Herdr 桌面应用只做显示和管理窗口。

审查最新原则见 [D019](docs/DECISIONS.md#d019-设计审查分级优先独立审核允许降级与简单复用免审)：大部分任务优先独立模型、争取跨厂商，允许单模型降级和简单复用免审；与旧强制跨厂商/双模型规则冲突时以此为准。该原则先用于当前设计机器人方案，现有运行代码仍有旧硬校验，尚未实现分级放行。

- **已跑通 S1 到 S9 全流程**：真实 Agent 完整跑通 S1 需求分析、S2 设计、S3 设计审查、S4 编码、S5 检查、S6 代码审查、S7 发布候选、S7U 使用验证、S8 验收与 S9 正式发布（见 [`next.md`](next.md)）。
- **独立需求澄清模块与飞书机器人（`src/requirements/`）**：常驻守护（`com.autodev.req-bot`），支持从模糊到清晰的 4 步拼图澄清、9 章节 SRS 标准产出与 `validator.py` 自动验真、独立完整模型 ID 调用层（`llm_provider.py`）、双端共享对话与耗时审计服务（`service.py`），并支持通过 `handoff.py` 跳过重复 S1、一键直通 `S2 架构设计`。
- **全系统统一网页客户端（`src/web/`，`v0.3.3`）**：把「源头需求澄清工作台」与前面分析设计的「S1~S9 系统流水线管理网站」完整连接成一体（需求规格见 [`docs/requirements/REQ-WEB-UNIFIED_CLIENT-20261107.md`](docs/requirements/REQ-WEB-UNIFIED_CLIENT-20261107.md)），相比飞书新增 **9 章节 SRS 实时生长预览、RULE-01~09 校验红绿灯、需求规模与关联网络图谱、每轮耗时审计**，并可一键直通切入 **S1~S9 流水线驾驶舱、在线产物阅读器、待你决定人工回复与 Agent 角色模型配置**。
- **命令行看板**：`src/dashboard/` 实时显示各需求阶段与日志，布局放在 Herdr 的 `pro2` 空间。

当前步骤和下一步见 [`next.md`](next.md)，方案见 [`docs/design/2026-11-05-autoloop-foundation.md`](docs/design/2026-11-05-autoloop-foundation.md)。

Agent/模型统一登记在 [`config/agents.toml`](config/agents.toml)，包含厂商、完整 ID、调用方式、能力限制与角色默认值；本机覆盖及环境变量凭证见[注册表使用说明](docs/design/2026-11-08-agent-model-registry.md)。可用 `PYTHONPATH=src python3 -m cockpit.registry --role designer` 检查选择，不调用模型。

## 运行服务与测试

```sh
PYTHONPATH=src python3 -m web.server --port 8765              # 启动全系统统一本机网页客户端 (http://127.0.0.1:8765)
PYTHONPATH=src python3 -m unittest discover -s tests          # 单元测试，不联网 (297 项测试)
python3 -I tests/smoke_autoloop.py                            # 联机冒烟，假 Agent，不花额度
```

`tests/f1_agents.py` 和 `tests/f2_pipeline.py` 会调用真实 Agent，花额度。需要先把 agent-autoloop 检出到 `~/code/agent-autoloop` 并切到提交 `8f8e2ee`。

## 文档

入口是 [`docs/INDEX.md`](docs/INDEX.md)。最常用的：

- [`next.md`](next.md)：当前状态与下一步
- [`docs/specs/REQUIREMENT_SPEC_STANDARD.md`](docs/specs/REQUIREMENT_SPEC_STANDARD.md)：软件需求规格说明书产出规范与校验标准（SRS Standard v1.0 / `v0.3.3`）
- [`docs/modules/requirements/README.md`](docs/modules/requirements/README.md)：需求澄清模块与飞书机器人入口（`v0.3.3`）
- [`docs/design/2026-11-05-autoloop-foundation.md`](docs/design/2026-11-05-autoloop-foundation.md)：当前主线方案
- [`docs/design/2026-11-02-autodev-design.md`](docs/design/2026-11-02-autodev-design.md)：九阶段流水线设计
- [`docs/DECISIONS.md`](docs/DECISIONS.md)：决策记录
- [`docs/lessons.md`](docs/lessons.md)：踩过的坑
- [`docs/MODELS.md`](docs/MODELS.md)：模型名规则（只写完整 ID）
- [`config.yaml`](config.yaml)：项目、Agent、角色和轮次上限配置
- [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)：换机器时用

已被取代的文档在 `docs/archive/`，只供追溯。

## 版本化需求工作台兼容入口

默认需求入口继续使用统一网页 `python3 -m web.server` 和独立飞书守护。另保留 `PYTHONPATH=src python3 -m requirements --demo serve --port 8765` 与同模块 CLI，用于双模型审核、版本哈希确认与固定版导出。该入口使用独立版本化会话，不与默认聊天会话自动同步，其 JSON 草稿不是九章节 SRS 定稿。详见 [兼容工作台指南](docs/modules/requirements/usage.md) 和 [整合边界](docs/design/2026-11-08-requirements-merge.md)。
