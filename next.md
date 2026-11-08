# next.md

## 已完成：项目登记（网页与飞书共用）及本机分支收敛到 main（2026-11-08）

- 实现范围：`cockpit.projects.register_project` 是唯一写入入口；验证名称、绝对路径、项目名/路径唯一性、Git 初始化确认、配置 expected_hash、原子写和写后回读恢复。
- Web 使用 `POST /api/projects` 和顶栏新增按钮；飞书使用 `/project add <名称> <路径>`，非 Git 目录仅在同会话回复 `/project init yes` 后初始化。
- 测试均使用临时目录；禁止真实飞书发送、服务重启和真实模型调用。完成后运行 `PYTHONPATH=src python3 -m unittest discover -s tests`，记录准确计数并本地提交到 `feat/project-registry`。
- 验证：`src/cockpit/projects.py` AST 检查通过；新增 6 项登记测试通过；全量 unittest 324 项通过；`git diff --check` 通过。
- 未验证：飞书真机交互、网页人工验收。未发送飞书消息、重启服务或调用真实模型。
- 项目登记已提交于 `5f1ecc1`。设计机器人分支、网页选择器、注册表及需求工作台提交已在候选主线历史中；Luna 复跑提交已合并其历史，保留报告并使用已验证的当前主线实现。
- 已试合并的混合树出现 53 个错误、1 个失败；撤销后保留主线实现与 Luna 报告/提交历史。全量测试 324 项通过。
- 整合提交 `7048533` 已快进到本地与远端 `main`。其他本地与远端分支已删除；所有现存 worktree 均指向同一主线提交，原有未跟踪需求/运行资料保留。

## 下一步：继续设计机器人渠道无关交互与修订入口

恢复下方原有设计机器人主线：复用 Web 与飞书呈现，再实现 D019 分级审查放行记录及条件式原型确认；实施前继续核对相应设计稿和待定协议。

## 历史目标：实现设计机器人第一步（2026-11-08）

用户已明确授权按当前设定实施，并将当前功能分支合入主分支；撤销此前对本任务“仅讨论、不编码”的限制。先完成设计与配置基线的 PR 合并，再从 main 建注册表实施分支，依 D021 的三步计划接入；随后推进设计机器人。保留 requests/ 和既有运行服务，不改 autoloop 内核。下方讨论记录作为决策历史保留。

- 设计/注册表基线 PR #2 已合入；Agent/模型注册表 PR #3 已于 2026-11-08 合入，远端 main 合并提交 4090793。
- 本步已完成：复用 S2/S3 与 SRS→S2 handoff；按项目 README/config context 生成同轮固定快照；S2 增加 prototype.md 和接口/开发计划契约，S3 审查并下游 S4/S6/S8 接收。未改 autoloop。
- 验证：311 项 unittest、`python3 tests/f2_pipeline.py --build`、两个模板 JSON 解析、文档链接和 `git diff --check` 通过；未调用真实模型、发送飞书消息或重启服务。
- 后续小步：补上渠道无关的设计任务交互/修订入口并复用 Web 与飞书呈现；再实现 D019 分级审查放行记录、需原型时人工确认的条件门槛及对应测试。当前功能分支 `feat/design-bot-flow`，基于远端 main `4090793`。

## 当前讨论：阶段机器人（2026-11-08）

用户从 autosys 会话转回本项目，要求继续设计需求、开发、测试、优化机器人：Agent 自动交接、展示协作、人可进入每阶段参与。本轮只设计。

- 先读 [需求讨论稿](docs/design/2026-11-08-stage-bots-requirements.md)、[设计草案](docs/design/2026-11-08-stage-bots-design.md)与 D020/D019（三层划分、分级审查与冲突优先级已接受，实施细节待定）。
- 用户明确只做方案设计，已有设计、流程和已验证资产尽量不动，重大冲突才讨论取舍。五工作区优先包装已有能力；运行中暂停只是候选，不能默认改造控制器。现有 resume 不能直接用作暂停接口。
- 待确认：单 App 多入口或多 App、后续执行的启动授权、在途控制边界。用户未确认前不实施、不调整机器人部署。
- 下方保留之前运行状态与待办，不表示本草案已交付。
- 用户进一步明确：设计单列，S2/S3 归设计工作区；输入为需求分析，交付完整设计、定稿开发计划、适用界面原型与下游接口契约，兼顾 GUI 和按需 CLI/API。当前五工作区，原型保真度和确认操作待细化。
- 用户确认工作区／S1～S9／autoloop 三层分工；后续可能增加项目、安全、文档等独立负责人 Agent。阶段、Agent 与人用机器人入口不一一绑定；跨阶段负责人不能绕过程序流转规则。
- 当前优先完成设计机器人的工作契约，见设计草案第 8 节 v0.1：输入输出、项目资料清单、工具分工及交付条件；用户明确飞书只是展现，后端与渠道无关，Web/飞书/未来微信共用。下一步细化原型呈现及条件式确认的操作协议，再形成实施计划。
- 最新确认（D019，取代此前最低双模型硬门槛）：大部分设计优先独立审查，争取不同 Agent/模型及跨厂商；不足时同厂商、单模型也可继续，简单且有适用验证资产可复用免审。不因缺少第二模型强制人工批准，不伪称独立审核通过。现有 check_vendors 与 S3 转移尚未适配。
- 有用户界面且需要原型时人工确认原型；无界面任务不强制人工确认设计，其他既有人工关口保留。条件式原型门槛尚未实现。下一步细化简单复用选择条件与降级结果协议。
- 已按用户要求检查新旧规则冲突，明确项目审查规则以 D019 为准（不限于当前设计文档）；活动入口/设计/需求模块文档已同步优先级。冲突清单见设计草案 8.7。代码、模板、配置和固定基线保持原状，仍存在硬厂商校验与无免审路径的实现差距，后续不能误认为已适配。
- 提交同步：已保留并合入远端 22 个提交，默认 SRS/统一 Web/独立飞书和 S2 交接按 D018 复用；旧版本化兼容 API 保持独立。本轮阶段机器人方案使用 D020，避免覆盖远端 D018。设计稿已校正旧本地版本的“无自动交接”等状态判断；分级审查仍未实现，不重启服务。
- 本轮同步验证：297 项 unittest 全过；本轮相对远端新增改动仅为文档，源码/模板/测试/配置与远端一致；文档本地链接、决策编号唯一性及差异格式检查通过。未启动收费模型、未发真实飞书消息、未部署/重启服务。
- 新增设计要求 D021：本机 Agent/模型能力注册表，说明厂商、完整模型 ID、调用方式、可/不可承担任务、默认值继承及环境变量凭证。见[契约](docs/design/2026-11-08-agent-model-registry.md)和[未接入样例](docs/config/agent-registry.example.toml)。当前只定义方案，运行仍用 config.yaml；后续先定配置与迁移，再统一所有入口的选择器，不能隐式补入未登记模型。

更新：2026-11-08 ｜ 当前版本：`v0.3.5` ｜ 阶段：流水线 S1 到 S9、飞书与全系统统一 Web 客户端已全部连通；确立全链路项目与需求双身份不变量（`D022`），落地交接强核验与分级处置（拒绝交接 / 人工介入）；全系统统一网页客户端与工作台统一支持 `AUTODEV_WEB_PORT` 环境变量覆盖与端口冲突友好拦截；守护进程安装脚本（`deploy/install-req-bot.sh`）支持多检出与多项目实例标签隔离（支持参数与环境变量）；全量 316 个单元测试全部通过

## 恢复上下文时先读

1. 本文件（尤其是下面的“换窗口接手时要知道”）
2. `docs/OPTIMIZATIONS.md`：每次流程优化改了什么、效果量到多少（O001 到 O008）和“待定”事项
3. `docs/design/2026-11-05-autoloop-foundation.md`：地基方案（F0 到 F6、结构、待决）
4. `docs/DECISIONS.md`：D001 到 D020（D014 用 autoloop 做地基，D015 验收者先绑 Claude）
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
- 测试：316 个单元测试通过（`PYTHONPATH=src python3 -m unittest discover -s tests`）。联机用假 Agent、不花额度：`python3 tests/f2_pipeline.py --build`（跑完整 S1 到 S9，含真实 git 标签）、`--fake-rework`，`tests/f5_crash.py hang|crash|ctrl-kill|hub-kill`。

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

已按用户授权，以 main v0.3.3 为准整合旧需求工作台；297 项 unittest、隔离中台与 S1～S9 假 Agent 回归通过。默认入口保持现行 SRS 流程，版本化能力独立兼容；范围与数据边界见 [整合设计](docs/design/2026-11-08-requirements-merge.md)。下一步按用户试用决定是否单列统一 UI 的审核/确认与格式迁移需求。该整合提交未包含并行的阶段机器人文档；本轮提交现已合入并同步这些文档（D019/D020）。
