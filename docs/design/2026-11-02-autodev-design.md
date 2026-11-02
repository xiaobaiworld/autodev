---
title: AutoDev 流程设计（2026-11-02）
created: 2026-11-02
updated: 2026-11-02
status: 草稿 v2
summary: AutoDev 是一个本地的需求驱动开发流水线。用户提交需求后，系统依次完成需求分析、设计、设计审查、编码、检查、代码审查、发布候选、验收和正式发布。每个阶段由可插拔的 Agent 承担，经 herdr 调度；每个关口都有审查和轮次上限，超限后通知用户介入。流程由确定性程序驱动，所有状态落盘，崩溃后可从文件恢复。
---

# AutoDev 流程设计（2026-11-02）

## 1. 目标与范围

AutoDev 在本机运行。用户提出功能修改类需求，系统把它变成经过审查的设计、代码和发布版本，只在需要人决定时打扰用户。

需求特点（与参考资料不同）：

- 需求全部由用户本人通过 AutoDev 的入口提交，不来自群聊、邮件或告警，不需要噪音过滤。
- 需求以功能修改为主，对系统理解的深度要求高。因此需求分析是核心环节，由能力最强的模型承担。

第一阶段只接一个目标项目 `personagent`。多项目结构保留在配置里，不作为本阶段验收内容。

不在范围内：GitHub PR、CI 平台、Webhook、飞书通知、云端运行。

## 2. 流水线

| 阶段 | 角色 | 默认 Agent | 产物 | 出口 |
| --- | --- | --- | --- | --- |
| S1 需求分析 | analyst | Claude Opus | `analysis.md` | ACCEPT 进 S2；REJECT 或 CLARIFY 交用户 |
| S2 设计 | designer | Claude Opus | `design.md`、`dev-plan.md` | 进 S3 |
| S3 设计审查 | design_reviewer | Codex | `review.md` | PASS 进 S4；REWORK 回 S2 |
| S4 编码 | coder | Codex | 分支上的提交、`exec-report.md` | 进 S5 |
| S5 确定性检查 | 程序 | 无 | `check.log` | 通过进 S6；失败回 S4 |
| S6 代码审查 | code_reviewer | Claude Opus | `review.md` | PASS 进 S7；REWORK 回 S4 |
| S7 发布候选 | 程序 | 无 | 候选版本、`release.log` | 进 S8 |
| S8 验收 | acceptor | agy（Gemini，可用 computer use 等手段） | `acceptance.md` | PASS 进 S9；REWORK 回 S4 或 S2 |
| S9 正式发布 | 程序 | 无 | 版本标签、CHANGELOG 条目 | 终态 done |

说明：

- S3 是设计者与审查者的多轮往返。审查者提出异议，设计者修改或在 `response.md` 中逐条回应，直到 PASS 或达到轮次上限。采用「一写一审」而非两个模型共写，理由与暂缓的「独立双稿」方案见 `docs/DECISIONS.md` D006。
- 编码模型按够用、性价比选择，由 S5、S6 兜底，见 D007。
- S5、S7、S9 是确定性步骤，由程序执行项目配置的命令，不调用 LLM。
- S8 的审查者在 REWORK 时须写明退回目标：实现问题回 S4，设计问题回 S2。
- 每个阶段的产物都是可审查的独立文件，见第 6 节。

## 3. 角色、Agent 与调度

### 3.1 角色与 Agent 解耦

流程只认角色（analyst、designer、design_reviewer、coder、code_reviewer、acceptor），不认具体 Agent。每个角色绑定哪个 Agent、哪个模型、哪个推理深度，都写在 `config.yaml`，改一行就能替换。

```yaml
agents:
  claude-opus:
    cli: claude
    model: opus
  codex:
    cli: codex
    model: null        # 具体模型待定
  agy:
    cli: agy           # Antigravity CLI
    model: gemini-4-argon-high

roles:
  analyst:         { agent: claude-opus }
  designer:        { agent: claude-opus }
  design_reviewer: { agent: codex }
  coder:           { agent: codex }
  code_reviewer:   { agent: claude-opus }
  acceptor:        { agent: agy }
```

约束：每个审查角色所用模型的厂商，必须与它所审产物作者的模型厂商不同。按厂商而不按 CLI 判断，因为同一个 CLI 可以运行不同厂商的模型（例如 agy 既能跑 Gemini 也能跑 Claude）。程序启动时校验，不满足则拒绝运行。

当前可用 Agent：Claude Code（Anthropic）、Codex（OpenAI）、agy（Antigravity，默认 Gemini）。三者都是 herdr 原生支持的 kind。

新增 Agent 只需在 `agents` 下加一项，并提供 adapter（如何启动、如何发送提示、如何判断完成）。

### 3.2 herdr 的作用

herdr 只负责 Agent 进程的生命周期：在 pane 中启动 Agent、发送提示、等待状态、读取输出、关闭 pane。流程状态不存放在 herdr 中，herdr 重启或 pane 丢失不影响流程状态的正确性。

本机 herdr 0.9.5 提供 `agent start / prompt / wait / read`、`pane close`、`worktree create / remove`、`notification show`，覆盖上述需求。这些命令只核对过帮助文本，未实际运行验证。

### 3.3 一次 Agent 调用的约定

每次调用都是一次性任务，不复用对话：

1. 程序把该次调用所需的全部输入写进 `runs/<id>/<stage>/round-N/input.md`。
2. 通过 herdr 在新 pane 中启动 Agent，提示只有一句：读取 input.md，按要求把产物写到指定路径，完成后写 `done.json`。
3. 程序以 `done.json` 是否存在、内容是否合法判断完成，不解析终端输出。终端输出仅保存为日志。
4. 关闭 pane。

这样，Agent 之间不共享对话，下一阶段只能看到上一阶段写下的文件。

## 4. 需求分析的上下文

需求分析决定后续所有阶段的质量。analyst 的 `input.md` 由程序按固定清单组装，不靠 Agent 自己去找：

| 内容 | 来源 | 方式 |
| --- | --- | --- |
| 需求原文 | `requests/<id>.md` | 全文内联 |
| 项目规则 | 目标项目的 `AGENTS.md`、`CLAUDE.md` | 全文内联 |
| 项目状态 | `docs/PROJECT_STATE.md`、`next.md` | 全文内联 |
| 历史决策 | `docs/DECISIONS.md` | 全文内联；过长时内联索引，正文留路径 |
| 代码结构 | 目录树与关键文件列表 | 内联摘要，正文留路径供按需读取 |
| 最近变更 | `git log` 最近若干条 | 内联 |
| 相关历史需求 | 本系统 `requests/done/`、`rejected/` 中同项目的需求 | 内联标题与结论，正文留路径 |

清单写在项目配置中，可按项目调整。超出长度预算的内容只放路径和摘要，由 Agent 按需读取。

analyst 的产物 `analysis.md` 必须包含：结论（ACCEPT、REJECT、CLARIFY）、理由、影响范围、与已有决策的关系、风险、验收标准。CLARIFY 时列出要问用户的问题。

## 5. 流程控制程序

### 5.1 原则

- 程序不在内存中保存任何权威状态。每次循环都从文件重新读取状态，决定下一步。
- 所有状态变更先写文件，再执行动作；动作完成后再写结果。
- 写文件一律先写临时文件、fsync、再原子 rename，避免崩溃时留下半写的文件。
- 程序是单实例的，启动时获取 `workspace/.lock`，拿不到就退出。

### 5.2 状态记录

每个需求的权威状态是 `runs/<id>/state.json`，记录当前阶段、轮次、当前步骤和步骤状态。`events.jsonl` 是只追加的历史日志，用于审计和排查，状态以 `state.json` 为准。

每一步的状态只有四种：

| 状态 | 含义 |
| --- | --- |
| pending | 输入已写好，尚未启动 |
| running | 已启动 Agent 或命令，记录了 pane id 和启动时间 |
| finished | 产物和 `done.json` 已校验通过 |
| failed | 超时、产物不合法或命令失败，附原因 |

### 5.3 主循环

```
loop:
  获取锁
  for each 未终结的需求:
    读 state.json
    按当前步骤状态推进一步：
      pending  -> 启动，写 running
      running  -> 检查 done.json / 超时 / pane 是否存活
      finished -> 根据产物结论计算下一步，写新的 pending
      failed   -> 按重试与轮次规则处理
  扫描 inbox，领取新需求
  sleep 间隔
```

每次推进只做一件事并立即落盘，因此任意时刻崩溃，最多重做一步。

### 5.4 重启与恢复

程序启动时不做特殊恢复流程，直接进入主循环。对 running 状态的步骤：

- `done.json` 已存在且合法：视为 finished。
- pane 仍存活且未超时：继续等待。
- pane 已不存在或已超时：标记 failed，按重试规则重新启动该步骤。

为保证重做安全，每一步必须可重入：

- Agent 步骤：重做前清空本轮输出目录，重新从 `input.md` 开始。
- 编码步骤：在 worktree 中先回到本轮开始时记录的提交（`state.json` 中保存），再重做。
- 发布步骤：命令需幂等，例如打标签前先检查标签是否已存在。

### 5.5 守护

主循环之外由系统的进程守护（launchd）负责拉起崩溃的程序。程序本身另有卡住检测：步骤超过配置的时限即判 failed，同一步骤连续失败超过次数则转 needs-human。

## 6. 目录结构

```
autodev/
├── config.yaml
├── workspace/
│   ├── .lock
│   ├── requests/
│   │   ├── inbox/          # 用户提交
│   │   ├── active/         # 流水线中
│   │   ├── needs-human/    # 等待用户
│   │   ├── done/
│   │   └── rejected/
│   └── runs/<id>/
│       ├── state.json      # 权威状态
│       ├── events.jsonl    # 只追加的历史
│       ├── S1-analysis/round-1/{input.md, analysis.md, done.json, pane.log}
│       ├── S2-design/round-N/{input.md, design.md, dev-plan.md, response.md, done.json}
│       ├── S3-design-review/round-N/{input.md, review.md, done.json}
│       ├── S4-code/round-N/{input.md, exec-report.md, diff.patch, done.json}
│       ├── S5-check/round-N/check.log
│       ├── S6-code-review/round-N/{input.md, review.md, done.json}
│       ├── S7-release/release.log
│       ├── S8-acceptance/round-N/{input.md, acceptance.md, evidence/, done.json}
│       └── S9-publish/publish.log
└── docs/
```

需求目录只保留五个状态。流水线内部阶段记录在 `state.json`，不再用目录表示，避免目录状态与 `state.json` 出现两个事实源。需求文件只在进入或离开流水线时移动。

## 7. 轮次与人工介入

| 关口 | 默认上限 |
| --- | --- |
| S3 设计审查往返 | 3 |
| S5 检查失败回修 | 3 |
| S6 代码审查往返 | 3 |
| S8 验收退回 | 2 |
| 单个步骤失败重试 | 2 |

上限写在 `config.yaml`。超限、任意 Agent 报告 BLOCK、或 analyst 给出 CLARIFY，需求移到 `needs-human/`，并通过 herdr 通知用户。

用户在 `needs-human/<id>.md` 末尾写处理意见，可选：

- `continue`：附指示，回到指定阶段继续，轮次计数清零；
- `reject`：移到 `rejected/`；
- `takeover`：用户直接指挥 Agent 处理，完成后再交回流水线。

以下事项无论流水线是否通过，都必须先问用户：删除数据、修改密钥或凭证、修改权限、对外发送消息、花钱、改变产品方向。执行 Agent 遇到时写 BLOCK 并停止。

## 8. 版本与记录

- 每次通过 S5 检查的编码轮次在需求分支上形成一个提交。
- S7 产出发布候选（候选标签，如 `v0.3.0-rc.1`），S8 验收通过后，S9 打正式标签并写入目标项目的 `docs/CHANGELOG.md`。
- 合并到目标项目主分支须用户确认。第一阶段 S9 之前加一道用户确认。
- 每个阶段的每一轮产物都保留，不覆盖。

## 9. 依据与限制

- 本设计以需求驱动的流水线为准。原 README 的 goal.md 自迭代循环已被取代。
- 参考资料：`reference/` 下两份存档（DeepSeek《Super-agent 设计探索》、卡兹克《Agent 自动化系统》）。采用了其中的思路：Router 不执行、Worker 隔离、审查与作者不同模型、审查有轮次上限、只把需要决策的事推给人、确定性判断写成程序。未采用：事件过滤、Thread 订阅、云端部署、飞书卡片，因为本系统的需求只来自用户本人，在本机运行。
- 参考 personagent 的 AGENTS.md 中关于任务状态、交接记录和合并确认的规则。
- 已读取全局规范 `GLOBAL_DEV_WORKFLOW.md` v1.11。

## 10. 待定问题

1. S7 发布候选的具体含义：只打候选标签，还是部署到某个可运行环境供 S8 验收。这取决于 personagent 的运行形态。
2. S8 验收的手段：computer use、浏览器自动化、CLI 测试，取决于 personagent 是什么类型的应用。
3. 流程程序的实现语言。
4. 用户入口：直接在 `inbox/` 建文件，还是提供一个命令。
