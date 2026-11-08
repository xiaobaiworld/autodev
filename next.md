# next.md

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

更新：2026-11-07 ｜ 阶段：流水线 S1 到 S9 已全部连通，真实 Agent 第一次完整跑通；接下来一遍遍雕细节

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
- 测试：212 个单元测试通过（`PYTHONPATH=src python3 -m unittest discover -s tests`）。联机用假 Agent、不花额度：`python3 tests/f2_pipeline.py --build`（跑完整 S1 到 S9，含真实 git 标签）、`--fake-rework`，`tests/f5_crash.py hang|crash|ctrl-kill|hub-kill`。

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

## 当前目标：需求澄清模块 v0.9 已实现（2026-11-07）

用户确认 v0.8 后补入本期 CLI + 网页，保留两个固定基线。已按 M1～M5 实现，M6 用真实双模型匿名案例走到人工确认前。

- 入口：`docs/modules/requirements/README.md`、usage.md、verification.md；计划 dev-plan.md；范围与取舍 D016/D017。
- 后端 `src/requirements/`：文档校验、版本/哈希、原文、逐次计时、双模型审核修订、人工确认、固定版导出与恢复。CLI 与本机网页共用后端，接口供上层项目复用。
- 启动演示：`PYTHONPATH=src python3 -m requirements --demo serve --port 8765`，访问本机 127.0.0.1:8765。真实模式用 --home 指向已启动中台，模型取现有配置，真实调用花额度。
- 验证：250 项 unittest 通过，隔离中台假 Agent 集成通过，原 pipeline/build 假 Agent 回归通过；实际浏览器创建/补充/模拟审核/确认/下载通过，查看桌面与手机布局。
- 真实案例 Q9c3406e4f917：两模型 low 调用 13345ms/7240ms，审核 PASS，停在等人确认；证据 `/tmp/requirements-real-20261107-v1`，中台已停。模型信息为请求配置，未独立解析响应模型。
- 手机补充：通用 `src/channels/` 与 requirements.messaging 已实现授权/去重/应用路由及会话绑定；先读 channels.md。飞书现有 autosys 可复用，但未修改或启动它；首个渠道待用户选择，真实平台未接通。
- 下一步：用户试用需求迭代；确定飞书/企业微信/个人微信及授权账号后完成平台适配。网页只监听本机，不公开部署。
- 旧流水线待办继续保留，不表示已完成所有真实项目集成。

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

## 当前执行：飞书需求客户端

飞书平台命令、短期一次性配对和 autosys 可选调用器已完成；已有机器人 /需求 分流已启用、重载后连上飞书。独立中台 home=~/.local/state/autodev/requirements-hub，launchd=com.autodev.requirements-hub。AutoDev 全量 257 项、桥接器 589 项（1 skip）；本地端到端通过。下一步由用户在现有飞书机器人发 /需求 做真实手机验收；未主动发测试消息。使用和完整证据见模块 channels.md。

## 当前执行：网页版工作台优化

已完成新版三栏工作台、章节文档、审核/调用页签、搜索、中文待办、网页飞书配对及过期轮询处理。全量 258 项通过，演示浏览器新建/补充/审核/确认及手机布局验证完成。真实入口 http://127.0.0.1:8766 已用 launchd=com.autodev.requirements-web 启动，共用现有根和独立中台；演示在 8767，不混用。下一步用户在真实网页试用并反馈布局/流程。
