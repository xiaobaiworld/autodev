# AutoDev 跨机器 Agent 交接（2026-11-03 起草，2026-11-06 精简）

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

以 `next.md` 为准。本文件只保留换机器时需要的内容：仓库获取方式、personagent 本地补丁的转移方法、尚未协调的规则冲突。

## 实现前必须协调的冲突

AutoDev 设计暂不含 GitHub PR；personagent 的 `AGENTS.md` 则要求开发任务建立 GitHub Issue 和 TASK、使用任务分支，并通过 PR 在用户确认后合并。personagent 仅明确允许用户直接指示的纯文档讨论在 `master` 小步提交；这不一定覆盖由 AutoDev 执行的开发任务。开始建 worktree 或运行流水线前，先确定两套规则如何兼容。

首个里程碑也要明确验收路径：AutoDev 设计允许纯文档需求跳过 S7、S8，而旧版 `next.md` 曾写成用文档需求跑 S1→S9。需要确定演示是验证按规则跳过阶段的路径，还是选择必须经过 S7、S8 的需求。

## 换机器后要重新核对

工具版本与安装位置不能沿用旧记录：重新检查 `node --version`（要 24 以上）、`claude`、`codex`、`agy`、`hc`、`herdr-app` 是否存在，agent-autoloop 是否检出在 `~/code/agent-autoloop` 并位于提交 `8f8e2ee`，然后跑 `python3 -I tests/smoke_autoloop.py`。模型名要重新核对（`docs/MODELS.md`），不同网关下完整 ID 不同。

开始实现前，遵守新机器上的全局 `AGENTS.md` 入口，等待 iCloud 主规范同步后再读。

## 阅读顺序

1. `next.md`
2. `docs/design/2026-11-05-autoloop-foundation.md`
3. `docs/DECISIONS.md`、`docs/lessons.md`、`docs/MODELS.md`
4. `docs/design/2026-11-02-autodev-design.md`、`docs/DATA_SPEC.md`、`config.yaml`
5. 在 personagent 仓库中，先读 `AGENTS.md`、`CLAUDE.md`、`docs/PROJECT_STATE.md`、`docs/DEV_GUIDE.md`、`docs/INDEX.md`、`docs/DECISIONS.md` 和 `next.md`。

## 交接边界

本文件记录原机器对 AutoDev 仓库和外部目标仓库的观察结果。它不携带 personagent 的未提交改动、补丁文件、本机凭据、工具安装、worktree 或未跟踪数据。换机后先重新检查两个仓库，再开始操作。
