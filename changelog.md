# changelog

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

## 2026-11-07
- F5：覆盖 Agent 挂起、进程崩溃、驱动强杀和中台强杀恢复；Agent 进程失败由步骤重试立即接手
- F6：移除旧的 Herdr 窗格调度代码；流水线阶段、角色和任务由模板驱动
- 完成 pipeline/build 的 S4–S9：代码工作区、程序检查、代码审查、候选发布、S7U 使用验证、验收和人工批准后的本地正式发布
- 新增每步模型、token、输入哈希和日志记录，以及运行摘要和可比性对照工具
- 修复人工批准入口：`driver.reply continue` 现在会继续推进到终态；F2 假 Agent 流程覆盖实际 CLI
- 单测 130 项通过；假 Agent 的完整 S1–S9、返工上限和四种 F5 场景通过
- Luna 真实 Agent 在隔离演示项目跑完 S1–S9；生成与 Sonnet 对照报告，记录阶段报告差异、S7U 证据及运行比较器的局限
