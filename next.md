# next.md

## 2026-11-07 Luna 驾驶员复测

- 起点：`5f6d270236bbde987ce890a704eee3132f00f8bf`，F4 完成后；在独立 worktree 分支 `codex-luna-rerun` 重做后续工作。
- 中台锁定 `/Users/bai/code/agent-autoloop` 的 `8f8e2eef3cfaa8f7a418818adc442450fe6bd884`；运行数据使用全新独立目录，保留旧运行数据。
- 真实需求原文：`requests/demo-todo-cli.md`（SHA-256 `9df8bf7d6e2ef78eeece1ae4af10d12a1450c378996313da3d640d4480f0fad1`）；B/C 层配置与 Sonnet 终点 `6b66cd7` 一致，真实运行 effort 为 `low`。两份当前工作树里的模板哈希相同，但 Sonnet R010 当时没有 S7U；当前模板哈希不能证明历史运行使用的版本。
- 仅在隔离演示项目 `todo` 中运行；不触碰 `personagent`，不推送、不部署，不动 Herdr `pro1`。用户已授权按默认值完成 S9 的本次本地发布。
- 当前 worktree：单测 **130 项通过**；F2 完整假 Agent S1–S9、设计返工上限，以及 F5 hang/crash/ctrl-kill/hub-kill 均通过。`driver.reply continue` 现会实际继续推进；F2 已调用真实 CLI 验证 S9 发布。
- 已完成：真实 Luna 运行 `R20261107-001` 到 S9 并本地结束发布；复核 S1–S9 全部产物；对照 Sonnet R010 的应用代码、各阶段报告与 A 层会话报告；将结果写入 `docs/reports/2026-11-07-session-report-luna.md`。
- 后续建议：修复运行比较器的阶段/输入差异识别，保存运行时配置和模板快照，记录有效 effort，统一验证 Claude/Codex 的模型与 token 口径，并把 S7U 文件断言结果传给 S8。当前比较报告已明确这些数据不能用于模型胜负或 token 成本结论。

---

历史进度：2026-11-06 ｜ 以 agent-autoloop 为地基的集成（供追溯；当前状态以本文顶部为准）

## 恢复上下文时先读

1. 本文件（尤其是下面的“换窗口接手时要知道”）
2. `docs/design/2026-11-05-autoloop-foundation.md`：当前主线方案（F0 到 F6 步骤、结构、待决）
3. `docs/DECISIONS.md`：D001 到 D015（D014 是用 autoloop 做地基）
4. `docs/lessons.md`：L001 到 L013，开始新功能前先扫一遍
5. `docs/MODELS.md`：模型名只写完整 ID
6. `docs/design/2026-11-02-autodev-design.md`：流程设计（第 3.2、3.3、5 节已被地基方案部分取代，见各节顶部说明）
7. `docs/DATA_SPEC.md`、`config.yaml`
8. 全局规范：`~/Library/Mobile Documents/com~apple~CloudDocs/agent/coding/AI编程全局规范/GLOBAL_DEV_WORKFLOW.md`
9. 换机器时另读 `AGENT_HANDOFF.md`

## 历史状态（2026-11-06）

- 地基：agent-autoloop 检出在 `~/code/agent-autoloop`，锁定提交 `8f8e2ee`。中台管派活、排队、重试、租约、事实日志、卡片；Agent 以无界面进程运行（Claude `-p`、Codex `exec`、agy `-p`）。
- 我们的部分放在中台外面：`src/driver/` 向中台发事件、读事实流；`src/cockpit/pipeline.py`、`controller.py`、`store.py` 管阶段、轮次上限、厂商不同检查、产物校验与状态落盘。
- 已验证：F0 冒烟（`tests/smoke_autoloop.py`）；F1 三个 Agent 各跑一轮；F2 真实 Agent 跑通 S1 到 S3（Opus、Opus、Codex，约 157 秒），REWORK 轮次上限在真实中台上验证。
- F3 界面：`src/dashboard/` 命令行看板读中台 `/v1/state` 与 `state.json`；在 Herdr 桌面应用的 `pro2` 空间里用 `herdr-app` 建了三格布局（左主窗格、右上看板、右下日志）。看板还没接真实流水线。
- F3 已用真实 Agent 验证：三格里实时显示（`docs/spikes/2026-11-06-f3-real-run-report.md`）。入口 `python3 -m driver.run`。
- 看板列出全部需求（进行中、等你、已完成、已拒绝），进行中和等你的不折叠，较早的已结束需求折成一个数；“待你决定”把等待人工的需求和中台卡片加在一起。
- 需求有了 `kind` 字段（路径写法，大类/子类），目前只登记 `pipeline/design`，在 `src/cockpit/kinds.py`；看板每个需求显示它，老记录显示“未分类”。
- 测试：144 个单元测试通过（`PYTHONPATH=src python3 -m unittest discover -s tests`）。

## 当时计划（2026-11-06，已由顶部的复测目标替代）

1. F3 剩余：Web 界面后做；真实审查者给出 REWORK 时看板和日志是否好用，还没见过。
2. 写 `pro2` 布局重建脚本（用户问过“能否保存”，桌面应用没有保存命令，建议用脚本重建）。
3. F4 模板：角色模板与规则从一处生成。
4. F5 崩溃与卡住：强杀中台、强杀 worker、Agent 超时、中台重试在真实环境触发。
5. F6 清理：移除不再需要的窗格驱动代码（`src/cockpit/` 的 `claim.py`、`invoke.py`、`config.py`、`main.py`、`status.py` 中不再用的部分），回写设计文档第 3、5、9 节。
6. 未验证项：agy 的实际模型名与用量；真实审查者给出 REWORK 并回应意见；强度参数在 Claude 启动参数里的写法；`/v1/stream` 从序号 0 重放在历史很大时的开销。

## Sonnet 基线环境（不用于 Luna 复跑）

- 演示用中台在 `/tmp/autodev-demo`（`home/` 是 autoloop 数据目录，`al` 是带环境变量的包装脚本）。它跑在 Herdr `pro2` 空间右下窗格（`hc` 地址 `t1n`，标签 `autodev-log`），端口 3399。`/tmp` 重启后会没，丢了就重建：`init --command '<假 Agent> {prompt}' --no-service --port 3399`，再 `up`。
- `pro2` 空间三格：左 `t1k`（日志窗格 `python3 -m dashboard.logpane --home /tmp/autodev-demo/home`）、右上 `t1m`（看板 `python3 -m dashboard --home /tmp/autodev-demo/home --root ~/code/autodev`，都要加 `PYTHONPATH=src`）、右下 `t1n`（中台）。窗格丢了用 `herdr-app` 重建，见 `docs/TOOLS.md` 第 2 节；布局重建脚本还没写。
- `pro1` 是用户自己的空间，不要动。
- 跑真实流水线：`PYTHONPATH=src python3 -m driver.run --home /tmp/autodev-demo/home --root ~/code/autodev --request <需求.md> --effort low`（花额度）。
- `workspace/runs/` 在 gitignore 里：`R20261105-001` 是 P4 调试留下的旧失败记录（看板里显示“等你”），`R20261106-001` 是 F3 真实跑通的那次，两条都没有 `kind`，显示“未分类”。
- 线上 autoloop 的最新只读副本在 `/tmp/aal-latest`（`d3e6d26`），本机锁定的 `~/code/agent-autoloop` 仍是 `8f8e2ee`，没升级。
- 已知小问题：`docs/INDEX.md` 里 `src/cockpit/` 一行没提 `kinds.py`；窗格驱动的旧代码还没清（F6）。

## F4 阶段的记录（历史）

- 刚做完：需求加了 `kind` 字段（`src/cockpit/kinds.py`，现只登记 `pipeline/design`，路径写法，以后分子类只多登记一行）。
- 马上做：F4 模板（角色模板与规则从一处生成，模板里要有“适用于哪个 kind”的字段）。
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
