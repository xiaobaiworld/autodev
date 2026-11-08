# next.md

更新：2026-11-08 ｜ 当前版本：`v0.3.3` ｜ 阶段：流水线 S1 到 S9、飞书与全系统统一 Web 客户端已全部连通；需求模块升级支持「软件研发 (`SOFTWARE`) / 环境部署 (`DEPLOYMENT`) / 硬件接入 (`HARDWARE`) / 跨类复合 (`HYBRID`)」自动分辨与双轨分类、按分类模板吸收内容及同构异核 9 章节模板；接下来一遍遍雕细节

## 恢复上下文时先读

1. 本文件（尤其是下面的“换窗口接手时要知道”）
2. `docs/OPTIMIZATIONS.md`：每次流程优化改了什么、效果量到多少（O001 到 O008）和“待定”事项
3. `docs/design/2026-11-05-autoloop-foundation.md`：地基方案（F0 到 F6、结构、待决）
4. `docs/DECISIONS.md`：D001 到 D015（D014 用 autoloop 做地基，D015 验收者先绑 Claude）
5. `docs/lessons.md`：L001 到 L012，开始新功能前先扫一遍
6. `docs/MODELS.md`：模型名只写完整 ID
7. `docs/design/2026-11-02-autodev-design.md`：流程设计（第 3.2、3.3、5 节已被地基方案部分取代，见各节顶部说明）
8. `docs/DATA_SPEC.md`、`config.yaml`
9. 全局规范：`~/Library/Mobile Documents/com~apple~CloudDocs/agent/coding/AI编程全局规范/GLOBAL_DEV_WORKFLOW.md`
10. 换机器时另读 `AGENT_HANDOFF.md`

## 当前状态

**流水线 S1 到 S9 已全部连通，真实 Agent 第一次完整跑通（R20261106-010，2026-11-06 到 07）。** 类型 `pipeline/build`，模板在 `templates/pipeline/build.json`（继承 `design.json`）。

| 阶段 | 谁做 | 说明 |
| --- | --- | --- |
| S1 分析 / S2 设计 / S3 设计审查 | Claude / Claude / Codex | 审查必须有“原文对照”小节（O007） |
| S4 编码 | Codex | 在 `workspace/projects/<项目>/<需求号>/` 里写代码，git 全由程序做（`src/cockpit/workdir.py`） |
| S5 检查 | **程序** | 运行 `python3 -m unittest discover -s tests`，不信 Agent 自述；失败退回 S4 |
| S6 代码审查 | Claude | 看完整改动 `full.patch`；审查者只读，程序比对代码指纹，改了就作废 |
| S7 发布候选 | **程序** | 本地 git 打 `v0.1.0-rc.N` |
| S7U 使用验证（O009） | **程序** | 按模板里**人写的使用脚本**，在隔离环境（临时 HOME 和数据文件）把做出来的东西真的用一遍，原始输出写 `usage.log`；用不了（命令不存在、没有可执行位、结果不符）退回 S4。**脚本现在是演示项目 `todo` 的，写死在 `build.json` 的 S7U 里，换项目要换一份** |
| S8 验收 | Claude（D015，原定 agy） | 以使用者身份对照原文；自己不能运行命令，优先引用 S7U 的使用记录 |
| S9 正式发布 | **程序，前面有人工关口** | 停在进入前等你批准；本地 git 打 `v0.1.0` 并写 `CHANGELOG.md`；**不推送、不部署** |

- 地基：agent-autoloop 检出在 `~/code/agent-autoloop`，锁定提交 `8f8e2ee`，不改它的内核。中台管派活、排队、租约、事实日志；Agent 以无界面进程运行。
- 我们的部分在中台外面：`src/driver/`（`run.py` 启动、`reply.py` 回复、`runner.py` 发事件等结束、`record.py` 每步记录、`compare.py` 两次运行比对）；`src/cockpit/`（`pipeline.py` 模板与转移、`controller.py` 主循环与 `resume`、`tools.py` 程序步骤 `check` 与 `release`、`workdir.py`、`store.py`、`kinds.py`）；`src/dashboard/` 命令行看板与日志窗格。
- **模板驱动**：阶段顺序、角色、产物、可选结论、结论去向（`on`）、每步读哪些文件（`inputs`）、必须有的小节（`required_sections`）、人工关口（`gate: human`）、工作目录模式（`workdir`: write / use / readonly）都在 `templates/pipeline/*.json`，改模板不改代码。
- **人工回复**：流水线停在“等你”后，用 `PYTHONPATH=src python3 -m driver.reply <需求号> continue|rework|reject --note ... --home <中台目录>`（`rework` 加 `--stage S4` 等）。`continue` 在人工关口上就是批准。看板“待你决定”会写清在等什么，并给出这条命令。
- **每步记录**：`done.json` 必填 `summary`；每步写 `record-a<次>.json`（实际模型、归一的 token、中台运行号等）和 `agent-a<次>.log`。字段见 `docs/DATA_SPEC.md` 7.2.1。程序步骤没有中台运行和 Agent 日志，记录里标 `tool`。
- **比对与优化记录**：`python3 -m driver.compare digest|diff` 做确定性比对；每次流程优化记在 `docs/OPTIMIZATIONS.md`（只追加，没量过写“未测”）。
- **崩溃与卡住**（假 Agent、真实中台，`tests/f5_crash.py`）：`hang` 超时重试、`crash` 每次崩溃 4 秒转人工（以前 45 分钟，O006）、`ctrl-kill`、`hub-kill` 都通过。
- **需求澄清独立模块与飞书机器人（已落地运行并直通 S2）**：`src/requirements/` 完全自包含内聚，macOS LaunchAgent 常驻长连接守护（`com.autodev.req-bot`）；发布规范 [`docs/specs/REQUIREMENT_SPEC_STANDARD.md`](docs/specs/REQUIREMENT_SPEC_STANDARD.md)，确立“从模糊到清晰”的渐进式演进生命周期、九大标准章节与网状关系矩阵；配套确定性规则检查器（`src/requirements/validator.py`）在定稿时自动断言验真；抽离独立大模型调用层（`src/requirements/llm_provider.py`，统一 `config.yaml` 完整模型 ID，支持 `cli_session` / `cli_stateless` 与 `/model` 在线切换）与阶段交接器（`src/requirements/handoff.py`，定稿后回复 `启动设计` 或 `/handoff` 自动生成 S1 基线并直通 `S2 架构设计`）。
- **全系统统一网页客户端与全项目代码收敛优化（`src/web/`、`src/requirements/service.py`，`v0.3.2`）**：严格按飞书 9 章节标准沉淀并通过校验的需求文档 [`docs/requirements/REQ-WEB-UNIFIED_CLIENT-20261107.md`](docs/requirements/REQ-WEB-UNIFIED_CLIENT-20261107.md)；实现 `src/web/`（`server.py`、`api.py`、`ui.html`，仅监听 `127.0.0.1`），把「需求澄清三栏工作台」与「S1~S9 系统工作流客户端」连成一体；完成 O1~O4 与 C1~C3 共 7 项跨模块去重与冲突消解。
- 测试：297 个单元测试通过（`PYTHONPATH=src python3 -m unittest discover -s tests`）。联机用假 Agent、不花额度：`python3 tests/f2_pipeline.py --build`（跑完整 S1 到 S9，含真实 git 标签）、`--fake-rework`，`tests/f5_crash.py hang|crash|ctrl-kill|hub-kill`。

### 真实运行的证据（演示需求：命令行待办 `todo`）

| 需求号 | 到哪 | 结果 |
| --- | --- | --- |
| R20261106-002 | S1 到 S3 | Codex 两次 REWORK 后 PASS，817 秒 |
| R20261106-005 | S1 到 S4 | S4 因 setuptools 被 BLOCK（促成 O002） |
| R20261106-006 | S1 到 S4 | S4 DONE |
| R20261106-007 | S1 到 S5 | S5 PASS（程序运行 4 个测试） |
| R20261106-008 | S1 到 S6 | 一次通过，但审查没抓到“需求要 `todo` 命令、设计只有 `python src/todo.py`”（促成 O007） |
| R20261106-009 | S1 到 S4 | S3 第 1 轮抓到了命令入口缺失；S4 因我写的红线措辞把 `chmod +x` 当成改权限而 BLOCK（已修） |
| **R20261106-010** | **S1 到 S9** | 523 秒到 S9 前，你批准后 `v0.1.0-rc.1`、`v0.1.0` 两个标签和 `CHANGELOG.md` 都在 |

单次样本，只能当线索，不能当结论。

## 待你定

- ~~S8 验收者没法亲手运行代码~~：你选了 A，已做（S7U，O009）。**真实 Agent 跑 S7U 还没做**，使用脚本也没有拆成项目配置。
- `docs/design/2026-11-06-ticket-model.md` 第 5 节的 6 个待讨论问题；Agent 做分类和拆解与 D004 的协调方式（我的提议是 Agent 只提方案文件，程序校验后才执行，没确认过）。
- D015（验收者先绑 Claude 而不是 agy）是我按“自动往下走”的授权选的默认，没单独确认过。

## 当前新增工作：需求澄清模块与专属飞书机器人落地（2026-11-07，已落地）

需求澄清模块已在 AutoDev 内部完全独立落地，并打通到 `S2 架构设计` 的阶段交接：
- 代码模块：`src/requirements/`（`feishu_daemon.py`、`flow.py`、`validator.py`、`handoff.py`、`llm_provider.py`、`context_detector.py`、`agent_runner.py`、`session.py`、`presentation/`）；
- 核心特性：只读安全模式、提示词方案选项 1/2 列表化与具象场景举例、低保真文本线框图、需求规模与关联矩阵、9 章节 SRS 程序化校验（RULE-01~09）、独立完整模型 ID 与双调用方式层（`cli_session`/`cli_stateless`）、一键直通 `S2 架构设计`；
- 系统守护：`deploy/install-req-bot.sh` 已将服务注册为 macOS launchd 守护进程 `com.autodev.req-bot` 并常驻运行；
- 测试验证：全量 239 个单元测试全部通过。

## 下一步

1. 按你的说法：流程已经全部走通，接下来一遍遍雕细节。细节清单：
   - 真实 Agent 跑一遍 S7U，看 Codex 写的 `bin/todo` 能不能过；把使用脚本从 `build.json` 拆成每个项目一份的配置。
   - 每个阶段的任务说明用真实运行的数据打磨，每次改动记一条 O 编号并和上一次比。
   - 设计审查返工偏多（多次要 2 到 3 轮才过），看是不是说明写得不够清楚。
2. F3 剩余：Web 界面；`pro2` 布局重建脚本（桌面应用没有保存命令）。
3. 没验证的：权限弹窗卡住、真实 Agent 进程崩溃；`/v1/stream` 从 0 重放在历史很大时的开销；agy 的实际模型名与用量（换回 agy 前要先验证）；S7、S9 只在演示项目的本地 git 里测过，**没碰过真实项目，也没有推送到远端**，接 personagent 前必须先问你。
4. S5 执行的是 Agent 刚写的代码，在 Agent 沙箱之外：做了最小环境变量、`HOME` 指向草稿目录、不经过 shell、超时杀进程组，**挡不住网络和对其他绝对路径的写入**（O004）。接真实项目前要换容器或 `sandbox-exec`。


## 换窗口接手时要知道（仓库里没有的东西）

- 演示用中台在 `/tmp/autodev-demo`（`home/` 是 autoloop 数据目录，`al` 是带环境变量的包装脚本）。它跑在 Herdr `pro2` 空间右下窗格（`hc` 地址 `t1n`，标签 `autodev-log`），端口 3399。`/tmp` 重启后会没，丢了就重建：`init --command '<假 Agent> {prompt}' --no-service --port 3399`，再 `up`。
- `pro2` 空间三格：左 `t1k`（日志窗格 `python3 -m dashboard.logpane --home /tmp/autodev-demo/home`）、右上 `t1m`（看板 `python3 -m dashboard --home /tmp/autodev-demo/home --root ~/code/autodev`，都要加 `PYTHONPATH=src`）、右下 `t1n`（中台）。窗格丢了用 `herdr-app` 重建，见 `docs/TOOLS.md` 第 2 节；布局重建脚本还没写。
- `pro1` 是用户自己的空间，不要动。
- 跑真实流水线（花额度）：`PYTHONPATH=src python3 -m driver.run --home /tmp/autodev-demo/home --root ~/code/autodev --request requests/demo-todo-cli.md --kind pipeline/build --effort low`。不加 `--kind` 默认是 `pipeline/design`（只到设计审查）。流水线跑到 S9 前会停下，之后用 `driver.reply` 批准。命令必须带 `PYTHONPATH=src`，否则找不到模块。`requests/demo-todo-cli.md` 是演示需求，不在 git 里。
- **Bash 工具经常被拦**（自动模式的安全分类器依赖的模型时好时坏）：`.claude/settings.local.json` 里有一份白名单，命中的命令不依赖分类器，但复合命令（`&&`、管道、`cd ... &&`）和临时的 `python3 -c` 不命中，要拆成单条命令。这个文件不在 git 里（`settings.local.json`）。
- `workspace/runs/` 在 gitignore 里：`R20261105-001` 是 P4 调试留下的旧失败记录（看板里显示“等你”），`R20261106-001` 是 F3 真实跑通的那次，两条都没有 `kind`，显示“未分类”；`R20261106-002` 以后是真实演示（见上表）。`workspace/projects/` 也在 gitignore 里，是 Agent 写的演示代码和本地 git 标签。
- 线上 autoloop 的最新只读副本在 `/tmp/aal-latest`（`d3e6d26`），本机锁定的 `~/code/agent-autoloop` 仍是 `8f8e2ee`，没升级。

## 仍然开放的问题（来自早期设计）

- 目标项目 personagent 目前没有可运行的产品代码。S7、S8、S9 现在在演示项目的本地 git 里跑通了，但**接 personagent 时 S7 是否要部署、S8 用什么手段验收、`checks` 写什么命令，都还定不了**（设计第 13 节第 1、2 条）。
- AutoDev 暂不含 GitHub PR，与 personagent 要求 Issue、TASK、PR 的规则需先协调；S9 现在只在本地 git 打标签，不推送。
- “需求变更”视图对比原文、结构化字段还是两者，未定。
- 需求分析的审核角色、结论协议和轮次上限待设计（D013）；现在 S1 没有独立审核。
- 跨机器 `hc --on homemac` 与 `keep` 丢失检测未测；autoloop 的 G4 提问续接、G7 外部文字隔离、熔断也未在我们的集成里测过。

## 待讨论：工单分类、拆解与成熟工具（用户 2026-11-06 提出，尚未定）

完整记录见 `docs/design/2026-11-06-ticket-model.md`：用户的 7 条要求、一张工单要回答的问题、提议的流程、现状对照、6 个待讨论问题。要点：先判断是否已知类型；已知则走原流程并尽量落实为程序；未知则让 Agent 提拆解方案、程序校验后执行；重要任务重复跑 3 到 5 遍比对；同类做满 3 次提炼成熟工具，人工审核后归档。

需要用户先定的：类型粒度怎么划、“同一套逻辑”谁来判断、第一步是否先给事件和 `done.json` 加“步骤类型”字段，以及它与 D004 的协调方式。讨论前不写进 `AGENTS.md`。

## 已归档（不再维护，保留追溯）

`docs/archive/`：驾驶舱设计与开发计划、autoloop 测试计划 v1 与 v2、空的 `goal.md` 模板。

## 当前整合步骤（2026-11-08）

已按用户授权，以 main v0.3.3 为准整合旧需求工作台；297 项 unittest、隔离中台与 S1～S9 假 Agent 回归通过。默认入口保持现行 SRS 流程，版本化能力独立兼容；范围与数据边界见 [整合设计](docs/design/2026-11-08-requirements-merge.md)。下一步按用户试用决定是否单列统一 UI 的审核/确认与格式迁移需求。原工作区并行的阶段机器人文档不在本次提交内。
