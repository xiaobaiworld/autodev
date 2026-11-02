# next.md

更新：2026-11-02 ｜ 阶段：设计（尚无可运行代码）

## 恢复上下文时先读

1. 本文件
2. `docs/design/2026-11-02-autodev-design.md`：流程设计 v2（13 节）
3. `docs/DATA_SPEC.md`：数据结构规范
4. `docs/DECISIONS.md`：D001–D012
5. `config.yaml`：项目、Agent、角色绑定、轮次上限
6. 全局规范：`~/Library/Mobile Documents/com~apple~CloudDocs/agent/coding/AI编程全局规范/GLOBAL_DEV_WORKFLOW.md`（末尾标识词「你好老板03」；2026-11-02 已可正常读取）

## 当前状态

- Git：`main` 与 `origin/main`（github.com/xiaobaiworld/autodev）一致，最后提交 `325b119`。
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
- 本机已核实：herdr 0.9.5、codex、claude、agy 1.4.12 都已安装；herdr `agent start --kind` 支持 claude、codex、agy。只看过帮助文本，没有实际跑过任务。

## 下一步（按顺序）

1. 读 personagent（`~/code/personagent`）的结构：技术栈、运行形态、测试与构建命令、`AGENTS.md`、`docs/`。
   - 注意：personagent 的 `docs/DECISIONS.md`、`docs/PROJECT_STATE.md` 有未提交改动（2026-11-02 观察到）。从 `master` 建 worktree 时不会带上这些改动，第一次跑流水线前需要用户处理。
2. 根据第 1 步，定下设计文档第 13 节的待定问题：
   - S7 发布候选：只打候选标签，还是部署到可运行环境
   - S8 验收手段：computer use、浏览器自动化或 CLI 测试
   - `config.yaml` 中 personagent 的 `checks` 命令
3. 写 `rules/` 条文（设计文档第 11.2 节）：requirement-splitting、module-design（含模块大小软阈值）、coding、checks、review。全局规范已覆盖的只写引用。
4. 定实现语言与 Web 技术栈（第 13 节第 3、4 项），然后写 `docs/DEV_PLAN.md`。按全局规范，要写明小步骤和大阶段的划分，以及何时需要用户确认合并。
5. 第一个实现里程碑建议：流程程序骨架（锁、`state.json`、`events.jsonl`、原子写、主循环）+ 用一个只改文档的需求跑通 S1 → S9。

## 未决问题

- 第 13 节第 5 项：「需求变更」视图按段落对比文本，还是对比 `analysis.md` 中的结构化字段。
- herdr 各命令需要实际运行验证，特别是 `agent start`、`agent wait` 以及 pane 丢失后的检测。
