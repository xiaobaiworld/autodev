# next.md

更新：2026-11-06 ｜ 阶段：以 agent-autoloop 为地基的集成（F0 到 F2、F4 到 F6 完成，F3 的 Web 界面未做）

## 恢复上下文时先读

1. 本文件（尤其是下面的“换窗口接手时要知道”）
2. `docs/design/2026-11-05-autoloop-foundation.md`：当前主线方案（F0 到 F6 步骤、结构、待决）
3. `docs/DECISIONS.md`：D001 到 D014（D014 是用 autoloop 做地基）
4. `docs/lessons.md`：L001 到 L012，开始新功能前先扫一遍
5. `docs/MODELS.md`：模型名只写完整 ID
6. `docs/design/2026-11-02-autodev-design.md`：流程设计（第 3.2、3.3、5 节已被地基方案部分取代，见各节顶部说明）
7. `docs/DATA_SPEC.md`、`config.yaml`
8. 全局规范：`~/Library/Mobile Documents/com~apple~CloudDocs/agent/coding/AI编程全局规范/GLOBAL_DEV_WORKFLOW.md`
9. 换机器时另读 `AGENT_HANDOFF.md`

## 当前状态

- 地基：agent-autoloop 检出在 `~/code/agent-autoloop`，锁定提交 `8f8e2ee`。中台管派活、排队、重试、租约、事实日志、卡片；Agent 以无界面进程运行（Claude `-p`、Codex `exec`、agy `-p`）。
- 我们的部分放在中台外面：`src/driver/` 向中台发事件、读事实流；`src/cockpit/pipeline.py`、`controller.py`、`store.py` 管阶段、轮次上限、厂商不同检查、产物校验与状态落盘。
- 已验证：F0 冒烟（`tests/smoke_autoloop.py`）；F1 三个 Agent 各跑一轮；F2 真实 Agent 跑通 S1 到 S3（Opus、Opus、Codex，约 157 秒），REWORK 轮次上限在真实中台上验证。
- F3 界面：`src/dashboard/` 命令行看板读中台 `/v1/state` 与 `state.json`；在 Herdr 桌面应用的 `pro2` 空间里用 `herdr-app` 建了三格布局（左主窗格、右上看板、右下日志）。看板还没接真实流水线。
- F3 已用真实 Agent 验证：三格里实时显示（`docs/spikes/2026-11-06-f3-real-run-report.md`）。入口 `python3 -m driver.run`。
- 看板列出全部需求（进行中、等你、已完成、已拒绝），进行中和等你的不折叠，较早的已结束需求折成一个数；“待你决定”把等待人工的需求和中台卡片加在一起。
- 需求有了 `kind` 字段（路径写法，大类/子类），目前只登记 `pipeline/design`，在 `src/cockpit/kinds.py`；看板每个需求显示它，老记录显示“未分类”。
- F4：阶段表在 `templates/pipeline/design.json`，`pipeline.py` 和规则生成都从它读。
- F5（假 Agent、真实中台）：Agent 卡住被超时取消并重试；驱动被 kill -9 重启不重复发同一轮；中台被 kill -9 重启后在途一轮自行完成。入口 `python3 tests/f5_crash.py hang|ctrl-kill|hub-kill`。
- F6：窗格驱动旧代码已删，Controller 没有 `hc` 和 `panes`。
- 真实演示：R20261106-002（命令行待办 `todo`）S1 到 S3 跑了 3 轮，Codex 两次 REWORK 后 PASS，共 817 秒；没触发轮次上限。
- 每步记录：`done.json` 必填 `summary`，每步写 `record-a<次>.json` 和 `agent-a<次>.log`（`src/driver/record.py`，字段见 `docs/DATA_SPEC.md` 7.2.1）。真实演示 R20261106-003：5 步记录齐全，实际模型与配置一致。
- 测试：115 个单元测试通过（`PYTHONPATH=src python3 -m unittest discover -s tests`）。

## 下一步

1. 接 S4 以后的阶段（编码、检查、代码审查、发布候选、验收、发布）：先在 `templates/pipeline/` 加模板、在 `kinds.py` 登记类型，再扩 `next_move`。目标项目 personagent 还没有可运行代码，检查命令（`config.yaml` 的 `checks`）待定。
2. F3 剩余：Web 界面；`pro2` 布局重建脚本（桌面应用没有保存命令）。
3. F5 没验证的：权限弹窗卡住、真实 Agent 进程崩溃、`/v1/stream` 从 0 重放在历史很大时的开销。
4. 未验证项：agy 的实际模型名与用量；强度参数在 Claude 启动参数里的写法。

## 换窗口接手时要知道（仓库里没有的东西）

- 演示用中台在 `/tmp/autodev-demo`（`home/` 是 autoloop 数据目录，`al` 是带环境变量的包装脚本）。它跑在 Herdr `pro2` 空间右下窗格（`hc` 地址 `t1n`，标签 `autodev-log`），端口 3399。`/tmp` 重启后会没，丢了就重建：`init --command '<假 Agent> {prompt}' --no-service --port 3399`，再 `up`。
- `pro2` 空间三格：左 `t1k`（日志窗格 `python3 -m dashboard.logpane --home /tmp/autodev-demo/home`）、右上 `t1m`（看板 `python3 -m dashboard --home /tmp/autodev-demo/home --root ~/code/autodev`，都要加 `PYTHONPATH=src`）、右下 `t1n`（中台）。窗格丢了用 `herdr-app` 重建，见 `docs/TOOLS.md` 第 2 节；布局重建脚本还没写。
- `pro1` 是用户自己的空间，不要动。
- 跑真实流水线：`PYTHONPATH=src python3 -m driver.run --home /tmp/autodev-demo/home --root ~/code/autodev --request <需求.md> --effort low`（花额度）。
- `workspace/runs/` 在 gitignore 里：`R20261105-001` 是 P4 调试留下的旧失败记录（看板里显示“等你”），`R20261106-001` 是 F3 真实跑通的那次，两条都没有 `kind`，显示“未分类”。
- 线上 autoloop 的最新只读副本在 `/tmp/aal-latest`（`d3e6d26`），本机锁定的 `~/code/agent-autoloop` 仍是 `8f8e2ee`，没升级。

## 刚做完 / 马上做

- 刚做完：F4、F5、F6（见上）；真实 Agent 上第一次看到 REWORK 回路（两次）。
- 马上做：S4 以后的阶段需要用户先定的东西很多（见下面“仍然开放的问题”），建议先和用户确认范围。
- 等用户：`docs/design/2026-11-06-ticket-model.md` 第 5 节的 6 个待讨论问题；Agent 做分类和拆解与 D004 的协调方式（我的提议是 Agent 只提方案文件，程序校验后才执行，没确认过）。

## 仍然开放的问题（来自早期设计，与地基无关）

- 目标项目 personagent 目前没有可运行的产品代码，S7 发布候选和 S8 验收的具体做法、`config.yaml` 的 `checks` 都还定不了。
- AutoDev 暂不含 GitHub PR，与 personagent 要求 Issue、TASK、PR 的规则需先协调。
- 设计文档第 8 节与第 13 节对 S7 “只打标签还是部署”表述不一致。
- “需求变更”视图对比原文、结构化字段还是两者，未定。
- 需求分析的审核角色、结论协议和轮次上限待设计（D013）。
- 跨机器 `hc --on homemac` 与 `keep` 丢失检测未测；autoloop 的 G4 提问续接、G7 外部文字隔离、熔断也未在我们的集成里测过。

## 待讨论：工单分类、拆解与成熟工具（用户 2026-11-06 提出，尚未定）

完整记录见 `docs/design/2026-11-06-ticket-model.md`：用户的 7 条要求、一张工单要回答的问题、提议的流程、现状对照、6 个待讨论问题。要点：先判断是否已知类型；已知则走原流程并尽量落实为程序；未知则让 Agent 提拆解方案、程序校验后执行；重要任务重复跑 3 到 5 遍比对；同类做满 3 次提炼成熟工具，人工审核后归档。

需要用户先定的：类型粒度怎么划、“同一套逻辑”谁来判断、第一步是否先给事件和 `done.json` 加“步骤类型”字段，以及它与 D004 的协调方式。讨论前不写进 `AGENTS.md`。

## 已归档（不再维护，保留追溯）

`docs/archive/`：驾驶舱设计与开发计划、autoloop 测试计划 v1 与 v2、空的 `goal.md` 模板。
