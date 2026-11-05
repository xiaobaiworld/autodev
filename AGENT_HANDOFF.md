# AutoDev 跨机器 Agent 交接（2026-11-03）

## 用途

供另一台机器或新的 Agent session 恢复 AutoDev 工作。记录仓库位置、当前设计、已定事项、未决问题，以及不会随克隆自动转移的本地改动。

## 获取仓库

### AutoDev

- 仓库：`https://github.com/xiaobaiworld/autodev.git`，公开仓库（2026-11-03 已核实）。
- 原机器路径：`/Users/bai/code/autodev`
- 分支：`main`
- 创建交接前，工作区干净，`main` 与 `origin/main` 同为 `4840d5b`。交接文件会产生新提交；新机器以 `git status --short --branch` 和 `git log -1 --oneline` 为准。
- 不要把 personagent 的私有文档补丁或其他私有项目内容存入这个公开仓库。

若新机器没有 AutoDev 目录：

```sh
mkdir -p ~/code
git clone https://github.com/xiaobaiworld/autodev.git ~/code/autodev
cd ~/code/autodev
```

若目录已存在，先检查分支和工作区，不覆盖本地改动。只有在工作区干净且分支为 `main` 时，才执行 `git pull --ff-only`。

### 目标项目 personagent

- 私有仓库：`https://github.com/xiaobaiworld/personagent.git`
- 原机器路径：`/Users/bai/code/personagent`
- 分支：`master`
- 最近检查的提交：`1d39d5f`，与 `origin/master` 一致。
- 原机器工作区的 `docs/DECISIONS.md` 和 `docs/PROJECT_STATE.md` 有未提交改动。它们没有进入远程仓库，新机器克隆后不会出现；不要误认为已转移，也不要在原机器丢弃。
- 保留这两份改动的补丁位于原机器 `/Users/bai/Downloads/personagent-local-docs-2026-11-03.patch`，SHA-256 为 `d490a0878dc2713e524f9340900c72ad003f99039e5f2fc4c59454330fb2e7e0`。补丁没有放进公开 AutoDev 仓库。

若新机器没有 personagent 目录：

```sh
git clone https://github.com/xiaobaiworld/personagent.git ~/code/personagent
```

AutoDev 是公开仓库；personagent 是私有仓库，克隆需要 GitHub 登录权限。如果新机器要保留原机器上的两份改动，须通过 AirDrop 或其他私密方式把补丁文件转过去。转移后先核对 SHA-256，再检查目标仓库状态：

```sh
shasum -a 256 /path/to/personagent-local-docs-2026-11-03.patch
cd ~/code/personagent
git status --short --branch
git rev-parse --short HEAD
git apply --check /path/to/personagent-local-docs-2026-11-03.patch
```

仅当工作区干净、分支为 `master`、HEAD 为预期基线 `1d39d5f` 且 `git apply --check` 成功时，才应用补丁。若远程已有新提交或检查失败，先阅读差异并手动协调，不要强制应用。

## AutoDev 当前状态

- 阶段：设计，尚无可运行代码。仓库有设计、数据规范、决策和配置；没有控制程序、CLI、Web 管理界面、schemas、`rules/`、`docs/DEV_PLAN.md` 或测试。
- 设计方向：本机运行的需求驱动九阶段流水线。确定性程序负责状态流转和持久化；Agent 产出可审查文件；人工决定使用 `decision-K.md` / `reply-K.md` 文件对。
- 首期唯一目标项目是 personagent（D002）。
- 角色与 Agent 解耦，在 `config.yaml` 绑定并由 Herdr（`hc`）调度。当前配置为：Claude Opus 负责分析、设计、代码审查和复盘；Codex 负责设计审查、编码和复盘审查；agy 使用 Gemini 负责验收。
- 计划中的 Web 界面只监听 `127.0.0.1`。AutoDev 当前设计明确不包含 GitHub PR 和 CI。
- 原 `goal.md` 自迭代循环已由需求驱动流水线取代。

## 实现前必须协调的冲突

AutoDev 设计暂不含 GitHub PR；personagent 的 `AGENTS.md` 则要求开发任务建立 GitHub Issue 和 TASK、使用任务分支，并通过 PR 在用户确认后合并。personagent 仅明确允许用户直接指示的纯文档讨论在 `master` 小步提交；这不一定覆盖由 AutoDev 执行的开发任务。开始建 worktree 或运行流水线前，先确定两套规则如何兼容。

首个里程碑也要明确验收路径：AutoDev 设计允许纯文档需求跳过 S7、S8，而旧版 `next.md` 曾写成用文档需求跑 S1→S9。需要确定演示是验证按规则跳过阶段的路径，还是选择必须经过 S7、S8 的需求。

## 已记录的方向

- 固定的需求驱动流程取代旧自迭代循环（D001、D005）。
- 第一阶段只接 personagent（D002）。
- 状态由确定性程序驱动并落盘，以支持中断恢复（D004）。
- 角色与 Agent 分开定义，映射放在 `config.yaml`，进程由 Herdr（`hc`）管理（D003）。
- 审查者与作者所用模型厂商必须不同；当前验收角色绑定 agy/Gemini（D008）。
- 人工参与通过文件对完成；管理界面计划只监听本机（D009、D010）。
- 复盘围绕动作、拆分、信息三个杠杆，改进建议须经审查和用户批准（D011）。
- 规则分为全局规范、AutoDev `rules/`、目标项目规则三层（D012）。

详细内容以 `docs/DECISIONS.md` 和设计文档为准。部分机制仍是设计提议，尚未通过实际运行验证。

## 待办

1. 检查目标项目当前文件、规则、运行形态和实际检查命令。原机器快照显示 personagent 尚无产品代码，因此无法从运行中的应用确定 S7、S8 和 `checks`；`config.yaml` 当前为 `checks: []`。
2. 确定 S7 是只打候选标签，还是部署候选供 S8 验收。设计第 8 节已描述候选标签，第 13 节仍将标签或部署列为未决。
3. 按目标项目将来的运行形态确定 S8 验收证据与方式。
4. 选择流程程序语言、Web 技术栈及进程边界。
5. 决定“需求变更”视图对比原文、结构化分析字段，还是两者都显示。
6. 协调 AutoDev 不做 PR 与 personagent 要求 Issue/TASK/PR 的流程差异。
7. 补写全局规范未覆盖的 AutoDev 规则，再写 `docs/DEV_PLAN.md`，列出小步骤、大阶段和用户确认合并的关口。
8. 明确首个演示是否按设计跳过纯文档需求的 S7、S8。
9. 补测 `hc` 的跨机器 `--on`、`keep` 丢失检测，以及 Claude 与 agy 的启动；本机 Codex 的基本流程已实测（`docs/lessons.md` L001）。

## 原机器环境记录

2026-11-02 记录的工具有 herdr 0.9.5、codex、claude、agy 1.4.12；`herdr agent start --kind` 帮助列出三个 Agent kind。当时没有实际运行任务。新机器需自行检查 `command -v`、版本和帮助信息，不要假定工具或版本相同。

开始实现前，遵守新机器上的全局 `AGENTS.md` 入口：等待 iCloud 主规范同步，读取该文件并核对末尾固定标识。原机器 `next.md` 记录 2026-11-02 读到标识「你好老板03」；新机器要核对当前文件，不要只依赖旧快照。

## 阅读顺序

1. `AGENT_HANDOFF.md`（本文件）
2. `next.md`
3. `docs/design/2026-11-02-autodev-design.md`
4. `docs/DATA_SPEC.md`
5. `docs/DECISIONS.md`
6. `config.yaml`
7. 在 personagent 仓库中，先读 `AGENTS.md`、`CLAUDE.md`、`docs/PROJECT_STATE.md`、`docs/DEV_GUIDE.md`、`docs/INDEX.md`、`docs/DECISIONS.md` 和 `next.md`。

## 交接边界

本文件记录原机器对 AutoDev 仓库和外部目标仓库的观察结果。它不携带 personagent 的未提交改动、补丁文件、本机凭据、工具安装、worktree 或未跟踪数据。换机后先重新检查两个仓库，再开始操作。
