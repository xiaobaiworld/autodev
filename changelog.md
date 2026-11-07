# changelog

## 2026-11-07：独立大模型与调用方式层（B1）及直通 S2 架构设计阶段交接器（A1）落地
- **独立大模型注册表与多调用方式层（`src/requirements/llm_provider.py`）**：统一从 `config.yaml` 读取完整模型 ID（遵循 `docs/MODELS.md`，严禁 `sonnet`/`opus` 等短别名）；支持 `cli_session`（CLI 原生 `--resume` 续接 + 本地历史兜底）与 `cli_stateless`（无状态单次调用 + 自动注入前序问答历史，支持跨模型/跨厂商无缝切换）两种调用方式；飞书端新增 `/model` 与 `/mode` 查看和切换指令；
- **直通 S2 架构设计阶段交接器（`src/requirements/handoff.py`）**：定稿的 `REQ-xxx.md` 经 `validator.py`（RULE-01~09）校验通过后，支持在飞书发送 `启动设计` / `/handoff` 或通过 CLI 命令一键转化为主流水线的 `workspace/requests/active/{rid}.md` 与 `S1-analysis/round-1/{analysis.md, done.json}` 基线，并将 `state.json` 直接初始化为 `stage: "S2"`（跳过重复 S1 分析，直通 S2 架构设计）；
- **测试与文档同步**：新增 `tests/test_requirements_llm_and_handoff.py`（含假 Agent 从 S2 直通推进至 S3 完成的端到端集成测试），全量 239 项单元测试全部通过；同步更新 `REQUIREMENT_SPEC_STANDARD.md`、`feishu-requirement-bot.md`、`README.md`、`INDEX.md` 与 `next.md`。

## 2026-11-07：交叉审计与修复需求规范、实现说明书及索引契约一致性
- **修复黄金范本与校验器标题偏差**：修正 [`docs/modules/requirements/feishu-requirement-bot.md`](docs/modules/requirements/feishu-requirement-bot.md) 第 9 节标题为标准 `## 9. 下游架构设计关注点`，并统一第 1 节元数据字段（`定稿时间`、`req-guided-v5`），使黄金范本 100% 通过 `validator.py`；
- **强化定稿 Prompt 二级标题约束**：在 [`src/requirements/flow.py`](src/requirements/flow.py) 定稿分支中显式要求原样输出 `## 1.` ~ `## 9.` 固定二级标题与必填字段字样，杜绝模型输出标题微调导致程序误拦；
- **修复规范文档相对死链与代码对齐**：修正 [`docs/specs/REQUIREMENT_SPEC_STANDARD.md`](docs/specs/REQUIREMENT_SPEC_STANDARD.md) 指向实现说明书的相对路径、RULE-09 字符阈值与第六节真实 `validator.py` 接口示例；
- **补全模块入口与契约回归测试**：在 [`docs/modules/requirements/README.md`](docs/modules/requirements/README.md) 补齐同目录早期草案索引；在 `tests/test_requirements_validator.py` 新增黄金范本直验与本地相对链接存在性测试，全量 234 项测试通过。

## 2026-11-07：完善需求规格标准与模块说明书，同步全量权威索引
- **模块总览入口重构**：更新 [`docs/modules/requirements/README.md`](docs/modules/requirements/README.md)，全面反映当前已落地常驻的架构、代码拓扑与两份核心文档索引；
- **同步更新权威索引与进展**：更新 [`docs/INDEX.md`](docs/INDEX.md) 和 [`next.md`](next.md)，将需求澄清模块（232 项单元测试）纳入主线全景视图，严格遵循项目与全局开发规范。

## 2026-11-07：确立从模糊到清晰的渐进式需求演进流程规范
- **四阶段演进生命周期标准化**：在 [`docs/specs/REQUIREMENT_SPEC_STANDARD.md`](docs/specs/REQUIREMENT_SPEC_STANDARD.md) 扩充第三节，正式确立“阶段 1 模糊摄入与上下文对齐 -> 阶段 2 后台自动吸收与草案整理 -> 阶段 3 关键分歧点人机确认 -> 阶段 4 标准收口与程序化验真”的标准流程；
- **抓大放小交互契约**：明确日常细节由大模型结合工程上下文主动推断补齐，仅在关键规模边界（大需求拆解）与流程走向时向人类发起 1、2 选项确认，兼顾极简体验与确定性标准。

## 2026-11-07：引入需求规模类别 (Epic/Feature/Sub-feature) 与网状关系矩阵表示法
- **需求规模与粒度分类体系确立**：在 [`docs/specs/REQUIREMENT_SPEC_STANDARD.md`](docs/specs/REQUIREMENT_SPEC_STANDARD.md) 扩充第 2 节为【需求规模分类与需求关联网络】，明确支持 `史诗级大需求(Epic)`、`标准功能(Feature)`、`子功能小需求(Sub-feature)` 和 `改动增强(Enhancement)` 四大标准粒度；
- **网状关系矩阵标准化**：确立与其他需求的标准化关系前缀（`Parent` 所属父需求、`Depends-on` 前置依赖、`Relates-to` 业务协同、`Blocks` 后置阻塞、`Supersedes` 演进替代）；
- **提示词与程序校验器联动**：升级至 `req-guided-v5`；`validator.py` 增强 RULE-03 断言，严格校验规模声明与关系网络，全量 232 项测试全部通过。

## 2026-11-07：需求规格标准 (SRS v1.0) 确立与程序化校验器落地
- **需求产出标准规范落盘**：制定 [`docs/specs/REQUIREMENT_SPEC_STANDARD.md`](docs/specs/REQUIREMENT_SPEC_STANDARD.md)，确立“输入可发散、输出必收敛、人机可共读、程序可自检”的核心契约，明确九大章节与 RULE-01~09 校验规则；
- **程序化检查器实现（validator.py）**：落地确定性检查逻辑，毫秒级断言章节完整性、架构拓扑双维度、非目标边界、低保真原型线框图以及防技术越权规则；
- **飞书定稿落盘自动验真**：在 `feishu_daemon.py` 定稿时无缝执行程序化校验，自动追加 `<!-- SPEC-VALIDATED: PASS -->` 合规元数据；
- **测试套件扩增**：新增 `tests/test_requirements_validator.py`，全量测试套件扩增至 231 项持续全绿。

## 2026-11-07：飞书端需求模块全流程沉淀与九大类别规范确立
- **Session 演进说明书落盘**：沉淀 [`docs/modules/requirements/feishu-requirement-bot.md`](docs/modules/requirements/feishu-requirement-bot.md)，完整记录从飞书长连接、多渠道呈现抽象、引导式拼图、场景举例、外部界面原型到全局架构拓扑判断的 6 大演进阶段；
- **确立需求规格说明九大标准类别**：定义标识元数据、架构拓扑与近期关联、背景与目标、范围用例、非目标边界、界面原型草图、业务约束、验收标准、下游设计关注点等九大核心分类体系；
- **同步文档索引**：更新 `docs/INDEX.md` 权威索引，全量 226 项测试验证通过。

## 2026-11-07：功能模块层级归属与近期功能关联判断（req-guided-v4）
- **项目上下文自动感知（context_detector.py）**：实现轻量探测器，实时抽取目标项目的业务域大模块（`src/`）、最近 Git 提交记录与近期已落盘需求文档，为大模型提供真实确切的上下文基准；
- **功能层级归属判断（Feature Hierarchy）**：提示词升级为 `req-guided-v4`，强制大模型在每轮响应（尤其是新需求开启时）首先明确指出：当前功能是属于项目哪个已有大功能/主模块下的细分子功能，还是属于全新的独立顶级模块；
- **近期功能关联度判断（Recent Feature Affinity）**：基于项目最近几项 Git 变更和需求规格，准确判断当前功能与近期做的几个功能是否存在关联（属于同一业务链路延伸、实体与能力复用、前后依赖、还是彼此独立）；
- **全量测试与服务无缝热更**：新增 `tests/test_requirements_context.py`，全量测试套件扩增至 226 项全部通过，LaunchAgent 守护服务重启生效。

## 2026-11-07：外部界面原型图生成与立体感知（req-guided-v3）
- **外部界面原型（UI Wireframe）引入**：提示词升级为 `req-guided-v3`，支持生成立体、直观的低保真文本线框图（ASCII/Unicode Mockup），直观展现页面标题、输入控件、操作按钮与数据展示区；
- **主动原型提议**：在业务流程探讨时主动询问“需要为这一块做个界面原型示例吗？随时告诉我【看原型】”，降低认知负担；
- **原型指令标准化**：输入层支持 `看原型`、`做个原型`、`需要原型`、`界面长什么样` 等口语化输入，自动标准化为原型生成意图；
- **定稿文档沉淀原型草图**：在导出的《软件需求规格说明》中沉淀【外部界面原型草图】章节；
- **全量测试与服务重启**：测试套件新增 2 项断言扩展至 223 项全部通过，`com.autodev.req-bot` 平滑重启上线。

## 2026-11-07：提示词升级为启发式引导与具象业务场景举例（req-guided-v2）
- **引导式拼图法落地**：系统提示词全面升级为 `req-guided-v2`，将长篇大论收敛为 4 块核心需求拼图（目标与场景 -> 核心流程 -> 非目标/边界 -> 验收标准），严格限制字数 < 250 字；
- **具象业务场景举例约束**：彻底剔除技术架构黑话（严禁谈数据库、API、框架），强制单点推进，并将每个选择题都赋予确切、生动的业务场景例子（例如具体操作行为），降低用户理解门槛，用户可直接回复数字 `1` 或 `2` 快速决策；
- **测试与服务同步**：同步更新 `tests/test_requirements_flow.py`，全量 221 个单测持续通过；平滑重启 LaunchAgent 守护进程 `com.autodev.req-bot`，新提示词立即在飞书生效。

## 2026-11-07：需求澄清模块与专属飞书机器人落地（v0.2.0）
- **独立模块实现**：在 AutoDev 项目内落地独立的专属需求澄清模块（`src/requirements/`），完全自包含与解耦，不依赖外部项目；
- **专属飞书机器人常驻**：基于官方 WebSocket 长连接实现 `feishu_daemon.py`，点开即聊需求；强制只读安全模式（Plan Mode），杜绝误改代码；支持 `/new` 开始新需求、`/project` 切换目录、回复 `定稿` 生成《需求规格说明草案》并自动落盘；
- **多渠道呈现层抽象（Presentation Adapter）**：创建 `presentation/` 抽象层，提炼渠道无关的领域语义模型（`RequirementResponse`、`RequirementChoice`）；实现 `FeishuCardPresenter`（飞书高颜值交互卡片）与 `PlainTextPresenter`（微信/控制台纯文本），后续拓展 Web 或微信只需新增 Presenter；
- **问答选项列表化与极简数字决策**：强化提示词将方案抉择收敛为精简编号的 1、2 选项；输入层实现 `normalize_user_input`，支持手机端直接回复 `1`、`2` 自动规范化为清晰决策意图；
- **系统守护脚本**：新增 `deploy/install-req-bot.sh` 与 `uninstall-req-bot.sh`，将服务注册为 macOS LaunchAgent（`com.autodev.req-bot`，开机自启、崩溃自愈）；
- **全量测试通过**：新增 9 个单元测试，测试套件扩增至 221 项全量通过（`Ran 221 tests OK`）。

## 2026-11-07：需求澄清模块设计
- 细化第一版程序协议：CLI/Python 调用、初始通用清单、需求 JSON 与原始输入输出、逐次调用开始/结束/耗时；明确用户等待不计入、失败重试分别计时、中断未知不伪造数值。补 R11 验收、更新设计与 next.md；仅设计，文档链接及差异检查通过，尚未实现。
- 按用户进一步限定，原始交流记录收窄为外部输入与大模型输出，撤回此前向工具调用、内部过程等底层审计的设计扩展；需求版本、人工确认和必要运行状态保留。仅文档调整，差异格式检查通过。
- 补充用户明确要求的原始交互审计：原文、实际输入快照、可取得的原始输出、失败重试、人工确认关联留存；区分原始资料、需求版本与后续分析，明确本地隐私边界和补充验收。仍为设计，未实现；将拟用的 `workspace/requirements/` 加入 gitignore，并验证忽略规则，防止后续原始交流被误提交。
- 新增 `docs/modules/requirements/`：记录已明确的模块需求、验收场景，以及待评审的状态循环、经验清单、版本确认、接口和分步实现方案；同步索引与 next.md。仅文档草案，未实现模块；文档相对链接和差异格式检查通过，未运行代码测试或真实 Agent。

## 2026-11-05
- 驾驶舱 P0：`hc` 标签、发命令、退出、清屏、三个 Agent 启动实验，记入 `docs/lessons.md` L004、L005
- 模型名一律写完整 ID：`config.yaml`、`docs/MODELS.md`
- 驾驶舱 P1：窗格认领（标签为主、手填地址为备用）、`cockpit` 配置段、缺块或重复拒绝启动（`src/cockpit/`，`tests/`）
- 驾驶舱 P2：状态区（窗格状态映射为运行中、等待、已结束、丢失、空闲，文字渲染，每 `refresh_seconds` 重绘，`hc` 或 `state.json` 出错只显示错误并继续）
- 驾驶舱 P3（假 Agent 部分）：一次 Agent 调用（启动、发提示、等 done.json、退出并确认回到 shell），用 pid 判断是否回到 shell
- 驾驶舱 P3：真实 Codex 一轮通过（25.4 秒），记入 L007
- 驾驶舱 P4（代码部分）：store（原子写、锁、事件先于状态）、pipeline（S1 到 S3）、controller（单步推进、重试、崩溃恢复）、入口 --start/--resume
- 驾驶舱 P4：真实跑 S1 通过；修复读取权限（--add-dir）、退出逐档升级不 kill、pane_lost 不重试；记入 L008，设计加 2.6 巡检
- 决定以 agent-autoloop 为地基；隔离冒烟通过（假 Agent、新数据目录、重复 id 去重）；写融合方案 docs/design/2026-11-05-autoloop-foundation.md
- F0：agent-autoloop 检出锁定在 ~/code/agent-autoloop（8f8e2ee），冒烟脚本 tests/smoke_autoloop.py（10 项，正反向都验证过）；融合文档补 F0、F1 通过标准
- F1：真实 Claude/Codex/agy 无界面各跑一轮并通过（实际模型名：Claude 通过，Codex、agy 未验证）；权限探针被拒绝而非挂起；记入 L009 与 F1 报告
- F2（进行中）：src/driver/hub.py（发事件、读事实流、RunTracker）、runner.py（把一次 Agent 调用换成发事件等中台那一轮结束）；write_input 与 check_vendors 提到 pipeline.py
- F2：流水线驱动跑在 autoloop 上，真实 Agent 跑通 S1 到 S3（约 157 秒），REWORK 轮次上限在真实中台上验证；报告与 L010
- F3（进行中）：在 Herdr 桌面应用里用 herdr-app 新建“autodev 看板”标签页并分出两个窗格（t1g 看板、t1h 日志）；src/dashboard/ 命令行看板读中台 /v1/state 与 state.json，真实窗格里验证通过
- 文档清理：归档被取代的驾驶舱设计与计划、autoloop 测试计划 v1/v2、空 goal.md 模板到 docs/archive/；重写 README、next.md、docs/INDEX.md；精简 AGENT_HANDOFF；设计文档 3.2/3.3/5 节加过时说明；新增 D014
- 新增 docs/TOOLS.md（工具手册）、AGENTS.md 与 CLAUDE.md（第一步先查工具手册）、L012
- AGENTS.md 补充项目目的、原则、与全局规范的关系；TOOLS.md 查找顺序与之对齐
- F3：主窗格日志视图 src/dashboard/logview.py、logpane.py（按真实 Claude、Codex 日志格式解析），假 Agent 在 pro2 左窗格验证；真实 Agent 实时滚动未验证
- F3：driver.setup（规则生成与安装）、driver.run（正式入口）；真实 S1 到 S3 在 pro2 三格里实时跑通；日志窗格与看板按窗格宽高适配
- 新增 docs/design/2026-11-06-ticket-model.md：记录工单分类、拆解、成熟工具的要求与待讨论问题（提议，未实现）
- 看板列出全部需求并带状态，等待人工的需求计入“待你决定”（原来漏算 human.waiting）；较早的已结束需求折叠
- 新增 reference/agent-autoloop-classification.md：autoloop 作者自己怎么给任务分类（读线上 main d3e6d26）
- state.json 加 kind 字段（路径写法 大类/子类，现仅 pipeline/design），未登记的类型在写文件前被拒绝；看板显示 kind 并按窗格宽度截断每行
- next.md 补“换窗口接手时要知道”；INDEX 补 kinds.py
- F4：阶段表、角色、产物、结论、任务说明移到 templates/pipeline/design.json，pipeline.py 与规则生成都从它读；新增 tests/test_templates.py
- F5：新增 tests/f5_crash.py（假 Agent、真实中台）：Agent 卡住被超时取消并重试且无残留进程；驱动 kill -9 后重启不重复发同一轮；中台 kill -9 重启后在途一轮自行完成。假 Agent 支持前 N 次卡住
- F6：移除窗格驱动的 claim/config/main/invoke/status 及其测试，Controller 不再有 hc 与 panes，agents.py 去掉 launch_cmd，config.yaml 去掉 scheduler 与 cockpit 段，新记录不再写 pane_id；显示宽度函数挪到 src/dashboard/width.py
- 每步记录：done.json 新增必填 summary（做了什么、为什么）；新增 src/driver/record.py，每步完成后写 record-a<次>.json 并留存 Agent 原始日志；记录写失败只记 record.failed 事件。真实 Agent 跑通（R20261106-003，221 秒，2 轮）
- 记录里新增归一的 tokens（总输入/缓存/输出，Claude 与 Codex 同口径）；新增 python3 -m driver.record <需求目录> 汇总 token
- 新增 src/driver/compare.py（摘要 digest.json 与两次运行的确定性比对）；模板加 scope，输入加“范围”说明；新增 docs/OPTIMIZATIONS.md 记录每次流程优化（O001）
- S4 编码阶段：转移规则与各步输入改由模板驱动（on、inputs、extends）；新增类型 pipeline/build（driver.run --kind）；新增 src/cockpit/workdir.py（代码目录的起点提交、重做前回到起点、diff.patch，git 全由程序做）；S4 报 DONE 但没有改动判为无效。修了一个 bug：失败重试时旧的 done.json 被当成已完成。假 Agent 联机跑通编码阶段（f2_pipeline.py --build）；真实 Agent（R20261106-006）S4 DONE，代码和测试经手工核对
- S7U 使用验证（O009）：S7 与 S8 之间新增程序步骤，工具 usage（src/cockpit/tools.py run_usage）按模板里人写的使用脚本，在隔离环境（最小环境变量、HOME 与数据文件指向草稿目录、不经 shell、超时杀进程组）把做出来的东西真的用一遍，原始输出写 usage.log 交给 S8；命令不存在或没有可执行位判 FAIL 退回 S4（usage_rounds 上限 3）；S8 任务说明改为优先引用使用记录。假 Agent 联机验证它抓到了 S5、S6 都放过的“bin/todo 没有可执行位”；11 个新单元测试
- 真实 Agent 第一次把需求从 S1 跑到 S9（R20261106-010，523 秒到 S9 前的人工关口，批准后发布）。新增 src/driver/reply.py（人工回复命令，批准或退回或拒绝，拿单实例锁）及 6 个测试；看板的“待你决定”写清在等什么并给出回复命令（wait_reason）；文档同步：next.md、docs/INDEX.md、设计第 8 节、DATA_SPEC 第 7.4 和第 8 节加“实现状态”说明；OPTIMIZATIONS 记下“S8 验收者没法亲手运行代码”待定事项
- 流水线接完 S7 到 S9：新工具 release（src/cockpit/tools.py，本地 git 打候选标签 v0.1.0-rc.N、正式标签 v0.1.0 并写 CHANGELOG.md，同名正式标签拒绝覆盖，不推送）；模板 gate: human（S9 前停下等批准，resume continue 放行）；S8 验收者先绑 Claude（D015）；D008 检查扩到 coder 与 acceptor；“修改权限”红线收窄；两个审查产物加必须有“原文对照”小节（required_sections）；删掉 pipeline.py 里 return 之后的旧代码。假 Agent 联机跑完整 S1 到 S9
- 修“Agent 进程崩溃要等 45 分钟才转人工”：make_invoke 默认不允许中台自己重试（hub_retries=0），中台第一次失败就取消并报 command_failed，由 Controller 的步骤重试接手；新增联机场景 f5_crash.py crash（3 次崩溃 4 秒转人工）；假 Agent 支持每次崩溃
- S6 代码审查：pipeline/build 新增 S6（code_reviewer，厂商与编码者不同，D008 检查扩到每一对）；审查者看完整改动 full.patch；只读步骤前后比对代码目录指纹（src/cockpit/workdir.py 的 fingerprint），审查者改了代码就作废、恢复、重试；workdir 模板字段分 write / use / readonly；S6 退回 S4 时不把通过的检查结果当失败塞给编码者。假 Agent 联机验证 S5 失败一次、S6 打回一次的全回路；真实 Agent 跑 S6 未做
- S5 检查：pipeline/build 新增 S5，第一个程序步骤（src/cockpit/tools.py 的 check：不经 shell、最小环境变量、HOME 指向草稿目录、超时杀进程组、“跑了 0 个测试”不算通过）；失败退回 S4（check_rounds 上限），每个编码轮开始前把上一轮代码提交成检查点，退回时在已有代码上修；resume 入口、归档重用的步骤目录；记录工具和比对工具认得程序步骤。假 Agent 联机验证 S4 -> S5 失败 -> 退回 -> 修好 -> 通过；真实 Agent 跑 S5 未做
