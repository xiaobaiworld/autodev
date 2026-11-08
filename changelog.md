# changelog

## 2026-11-08：阶段机器人设计与分级审查规则
- 新增阶段机器人需求与设计草案：需求、设计、开发、测试、优化五工作区复用 S1～S9 与 autoloop；记录角色上下文、渠道独立的设计后端、输入输出、工具分工及交付契约（D020）。
- 明确界面原型须人工确认、无界面设计不强制人工确认；审查以 D019 为准，优先独立模型/跨厂商，允许同厂商、单模型降级与已验证简单复用免审，保留真实检查和放行依据。
- 同步项目规则、索引、主线与需求模块文档，列出旧厂商校验、结果协议与流转待适配位置。本轮仅文档，未实现新机器人或更改运行机制；258 项 unittest 与文档链接/差异检查通过。

## 2026-11-07：需求工作台 v0.9
- 优化网页版：搜索列表、交流与章节文档三栏布局，审核/调用记录页签、明确待办与版本确认、网页飞书配对；修复跨会话轮询覆盖。真实本机网页 8766 常驻并与飞书共享后端，演示单列 8767。258 项测试和浏览器演示交互、桌面/手机布局通过。
- 接入现有飞书机器人：/需求 命令后台调用共享需求后端，支持新建、回答、审核、确认、导出与一次性跨端配对；新增独立中台常驻，现有白名单与 App 复用。AutoDev 257 项测试通过；autosys 589 项通过、1 skip，机器人已重载并连接。真实手机消息验收待用户发起，未主动发测试消息。
- 实现独立需求后端、CLI 与本机网页：多轮澄清、可选双模型审核修订、人工介入、当前版本确认、固定版导出和故障恢复。无费用演示与真实模式隔离。新增通用手机消息路由与需求适配，平台连接待选择。250 项单元测试、隔离中台假 Agent 集成、既有流水线回归、浏览器交互及真实双模型匿名案例通过，细节见模块 verification.md。

## 2026-11-07：需求澄清模块设计
- 按用户确认保存 v0.8 需求基线：补入模型可选、独立模型审核、先模型间修订复核、必要时人介入及最终人工确认；记录 D016。新增 M1～M6 开发计划，落实独立后端、CLI 先行、未来网页及上层项目共用 API；同步设计、协议、索引与 next.md。本轮仅文档，尚未实现或调用真实模型。
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
