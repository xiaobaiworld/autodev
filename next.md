# next.md

更新：2026-11-03 ｜ 阶段：设计（尚无可运行代码）

## 恢复上下文时先读

1. `AGENT_HANDOFF.md`：跨机器恢复说明、仓库位置、外部项目未提交状态
2. 本文件
3. `docs/design/2026-11-02-autodev-design.md`：流程设计 v2
4. `docs/DATA_SPEC.md`：数据结构规范
5. `docs/DECISIONS.md`：D001–D012
6. `config.yaml`：项目、Agent、角色绑定、轮次上限
7. 全局规范：`~/Library/Mobile Documents/com~apple~CloudDocs/agent/coding/AI编程全局规范/GLOBAL_DEV_WORKFLOW.md`（新机器须等待 iCloud 同步，并核对文件末尾固定标识）

## 当前状态

- AutoDev 仓库：`https://github.com/xiaobaiworld/autodev.git`，公开；当前分支 `main`。2026-11-03 创建交接前，工作区干净且 `main` 与 `origin/main` 一致（`4840d5b`）。交接文档将产生新提交；恢复时以 `git status` 和最新提交为准。
- AutoDev 仍是设计阶段：没有可运行代码、CLI、Web 管理界面、schemas、`rules/`、`docs/DEV_PLAN.md` 或测试。
- `personagent` 是另一个私有仓库：`https://github.com/xiaobaiworld/personagent.git`，当前机器路径 `/Users/bai/code/personagent`，分支 `master`。2026-11-03 检查时 HEAD 与 `origin/master` 同为 `1d39d5f`，但 `docs/DECISIONS.md` 和 `docs/PROJECT_STATE.md` 有未提交改动。新机器克隆不会带上这些本地改动；需要时须从原机器另行转移。补丁保存在原机器的 `/Users/bai/Downloads/personagent-local-docs-2026-11-03.patch`，不能放入公开的 AutoDev 仓库。
- AutoDev 明确暂不做 GitHub PR/CI；personagent 开发规则要求 Issue、TASK、任务分支和 PR。启动首个流水线前要解决两套规则的衔接。
- 当前本机工具版本只在 2026-11-02 做过记录，不能推定新机器相同；herdr 实际生命周期尚未验证。
- 已定：
  - 需求驱动的九阶段流水线，取代原 goal.md 自迭代循环（D001、D005）
  - 第一阶段只接 `personagent`（D002）
  - 角色与 Agent 解耦，绑定写在 `config.yaml`，经 herdr 调度（D003）
  - 三个 Agent：Claude Code、Codex、agy。审查者与作者的模型厂商必须不同（D008）
  - 当前绑定：分析、设计、代码审查、复盘用 Opus；设计审查、编码、复盘审查用 Codex；验收用 agy
  - 流程由确定性程序驱动，状态全部落盘，可崩溃恢复（D004）
  - 人工参与通过 `decision-K.md` / `reply-K.md` 文件对完成（D009）
  - 本地 Web 管理界面，只监听 127.0.0.1（D010）
  - 复盘围绕动作、拆分、信息三个杠杆，改动须审查加用户批准（D011）
  - 规则分三层：全局规范、AutoDev `rules/`、项目规则（D012）
- 原机器于 2026-11-02 核实：herdr 0.9.5、codex、claude、agy 1.4.12 已安装；herdr `agent start --kind` 帮助列出三种 Agent。只看过帮助文本，没有实际跑过任务；新机器须重新核对。

## 下一步（顺序可按新机器实况调整）

1. 按 [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) 获取 AutoDev 公共仓库和 personagent 私有仓库，并核对分支、提交与工作区。先处理 personagent 两份未提交文档的转移或保留方式。
2. 阅读 personagent 项目规则和状态。当前检查显示其处于需求与设计阶段、没有产品代码；确认这在新机器上仍成立。
3. 解决 AutoDev 的 GitHub 协作范围与 personagent 项目规则冲突，之后再决定是否可把 personagent 作为首个自动化目标。
4. 定义首个演示需求的验收路径。纯文档需求按设计可以跳过 S7/S8，所以不要把“跑通 S1→S9”理解为一定要执行这两个阶段。
5. 结合目标项目实际情况，确定 S7（候选标签或部署）、S8 验收方式，以及 `config.yaml` 中的 `checks` 命令。目前 `checks: []`，personagent 尚无可运行应用。
6. 确定流程程序语言和 Web 技术栈/进程边界，并决定“需求变更”视图对比文本、结构化字段或两者。
7. 补写 AutoDev `rules/` 中全局规范未覆盖的条文，再写 `docs/DEV_PLAN.md`；计划要列出小步骤、大阶段及用户确认合并的关口。
8. 之后实现第一个里程碑：流程骨架（锁、`state.json`、`events.jsonl`、原子写、主循环），并按第 4 步定好的跳阶段规则跑通文档需求。
9. 在新机器核对 `herdr agent start`、`agent wait` 和 pane 丢失检测；之前只查过帮助文本，没有真实运行任务。

## 设计文档中的待协调点

- 第 8 节描述 S7 产出候选标签，第 13 节仍在讨论只打标签还是部署，需统一表述。
- 第 13 节第 2 项的 S8 方法取决于 personagent 应用形态；当前仓库还没有产品代码。
- AutoDev 暂不含 GitHub PR，与 personagent 的 Issue/TASK/PR 开发规则需先协调。
- 第 13 节第 5 项仍未决定“需求变更”视图的对比粒度。
