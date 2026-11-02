---
title: AutoDev 流程设计（2026-11-02）
created: 2026-11-02
updated: 2026-11-02
status: 草稿 v2
summary: AutoDev 是一个本地的需求驱动开发流水线。用户提交需求后，系统依次完成需求分析、设计、设计审查、编码、检查、代码审查、发布候选、验收和正式发布。每个阶段由可插拔的 Agent 承担，经 herdr 调度；每个关口都有审查和轮次上限，超限后通过决策请求通知用户介入。流程由确定性程序驱动，所有状态落盘，崩溃后可从文件恢复。本地 Web 界面展示需求变更与结果、调换 Agent、处理人工决策。复盘机制围绕动作、拆分、信息三个杠杆持续改进。数据结构见 DATA_SPEC.md。
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
│       ├── S9-publish/publish.log
│       ├── human/{decision-K.md, reply-K.md}
│       ├── retro/{retro.md, P*.patch}
│       └── metrics.json
│   └── retros/<retro-id>/{retro.md, metrics.json}
├── pipeline.yaml           # 阶段拆分定义，带版本
├── templates/roles/        # 角色动作模板，带版本
├── rules/                  # AutoDev 补充规则，见第 11 节
├── reference/              # 外部参考资料与 INDEX.md
├── schemas/                # JSON Schema
└── docs/
    ├── DATA_SPEC.md
    ├── DECISIONS.md
    └── LESSONS/
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

需要用户参与时，程序生成一份决策请求 `human/decision-K.md`（一句话说明、要你判断的问题、推荐做法和依据路径），并通过 herdr 通知。用户可以在 Web 界面、`autodev reply` 命令或直接编辑 `human/reply-K.md` 回复，可选 `answer`、`approve`、`continue`、`revise`、`retry`、`takeover`、`reject`。

回复中的指示会作为「用户决定」传给后续每个 Agent，优先级高于需求原文；对项目长期有效的决定在正式发布时写入目标项目的 `docs/DECISIONS.md`，以后不再重复问。完整结构与规则见 `docs/DATA_SPEC.md` 第 8–10 节。

以下事项无论流水线是否通过，都必须先问用户：删除数据、修改密钥或凭证、修改权限、对外发送消息、花钱、改变产品方向。执行 Agent 遇到时写 BLOCK 并停止。

## 8. 版本与记录

- 每次通过 S5 检查的编码轮次在需求分支上形成一个提交。
- S7 产出发布候选（候选标签，如 `v0.3.0-rc.1`），S8 验收通过后，S9 打正式标签并写入目标项目的 `docs/CHANGELOG.md`。
- 合并到目标项目主分支须用户确认。第一阶段 S9 之前加一道用户确认。
- 每个阶段的每一轮产物都保留，不覆盖。

## 9. Web 管理界面

### 9.1 定位

Web 界面是流程的另一个客户端，不是另一套系统。它读的是第 6 节的文件，写的也只经过与命令行相同的入口，因此：

- 文件仍是唯一事实源。界面关掉、崩溃或重启，不影响流水线。
- 界面不直接改 `state.json`。它只写三类用户本来就有权写的文件：新需求（`inbox/`）、回复（`reply-K.md`）、配置（`config.yaml`）。流程程序照常读取并校验这些文件。
- 写入沿用原子写。修改配置时带上读取时的文件版本（内容哈希），版本不一致则拒绝保存并提示刷新，避免覆盖其他来源的修改。

### 9.2 看什么：需求和结果，不看代码

界面以需求为主线，每个需求一页，按以下顺序展示：

| 区块 | 内容 | 来源 |
| --- | --- | --- |
| 需求 | 原文、分析结论、验收标准 | 需求文件、`analysis.md` |
| 需求变更 | 需求如何被理解和修改：原文 → 分析后的范围 → 每次用户回复带来的变化 | `analysis.md` 各轮、`reply-K.md`，按时间对比 |
| 进度 | 九个阶段的时间线，每个阶段的轮次、Agent、模型、结论、耗时 | `state.json`、`events.jsonl` |
| 待你决定 | 当前的决策请求和回复表单 | `decision-K.md` |
| 结果 | 验收结论、截图等证据、发布版本 | `acceptance.md`、`evidence/`、`state.json.git` |
| 详细文档 | 设计稿、开发计划、各轮审查意见 | 各阶段产物，折叠显示 |

代码 diff 不作为主体展示，只在「详细文档」中给出改动文件列表和提交链接。

### 9.3 页面

1. 总览：所有需求按状态分组，置顶「待你决定」的列表，各阶段当前有哪些需求在跑。
2. 需求详情：9.2 的内容。
3. 人工决策：在需求详情中直接回复。表单按 `allowed_actions` 生成选项，默认选中推荐项，提交后写 `reply-K.md`。
4. Agent 配置：展示角色到 Agent 和模型的绑定，可直接调换。保存前执行与程序启动时相同的校验（Agent 存在、审查者与作者厂商不同），不通过则不保存。已在运行的步骤不受影响，新步骤使用新配置。
5. 新建需求：填写项目、标题、正文，写入 `inbox/`。

### 9.4 安全

- 只监听 `127.0.0.1`，不对局域网或公网开放。第一阶段不做登录。如果以后需要从其他设备访问，先加认证，再改监听地址。
- 不展示、不编辑 `.env`、密钥等文件。展示产物前做与 S5 相同的密钥扫描，命中则隐藏内容。
- 界面只能写 9.1 列出的三类文件，路径在服务端固定拼接，不接受客户端传入任意路径。

### 9.5 实时性

界面通过轮询或文件监听获取变化，延迟在几秒内即可。不引入消息队列。

## 10. 经验总结与流程改进

### 10.1 能改进的三样东西

模型本身不受我们控制，我们能提升的只有交给 Agent 的东西。把它们都做成带版本的文件，改进就是改这些文件：

| 杠杆 | 对应文件 | 例子 |
| --- | --- | --- |
| 给 Agent 的动作 | 角色模板 `templates/roles/<role>.md` | 代码审查模板增加「先核对验收标准再看实现」 |
| 动作怎么拆分 | 流水线定义 `pipeline.yaml`（阶段顺序、哪些阶段可跳过、轮次上限） | 纯文档需求跳过 S7、S8；大需求在 S2 后拆成多个子任务 |
| 给 Agent 多少信息 | 上下文清单（`config.yaml` 的 `projects[].context` 及各角色的上下文规则） | analyst 额外读取某模块的接口文档；超长文件改为摘要 |

每次 Agent 调用的 `input.md` 都记录三者的版本号。这样任何一次结果，都能对应到当时用的是哪一版动作、拆分和上下文，才能比较改动前后的效果。

### 10.2 素材从哪来

不靠 Agent 回忆，只用落盘的数据：

1. 运行指标，由程序从 `events.jsonl` 和 `state.json` 自动统计：每个关口的轮次、超限次数、`invalid_output` 次数、超时次数、各阶段耗时、人工介入次数和原因。
2. 审查意见：各轮 `review.md` 的 `findings[]`。同一类问题反复出现，说明上游动作或信息不够。
3. 用户回复：`reply-K.md`。每一次需要用户纠正，都是一个改进信号。
4. 返工去向：S8 验收退回 S2 意味着设计漏了，退回 S4 意味着实现漏了。

### 10.3 什么时候总结

- 每个需求进入 done 或 rejected 后，做一次单需求复盘。
- 每累计 N 个需求（默认 5，写在配置中），做一次跨需求复盘，找重复出现的模式。单个需求的问题可能是偶然，重复出现才值得改流程。

### 10.4 谁总结，怎么生效

1. 程序先生成指标汇总，再交给复盘角色 `retrospector`（默认 Claude Opus，可在配置中调换）。它读取指标、审查意见、用户回复，写出 `retro.md`：发现了什么、证据在哪、建议改哪个杠杆的哪个文件、预期改善哪个指标。
2. 建议的修改以补丁形式给出，不直接生效。
3. 由一个不同厂商的 Agent 审查建议，检查证据是否支撑结论、改动会不会影响其他角色。
4. 推送给用户决定（决策类型 `improvement`），用户批准后程序应用补丁，模板版本号加 1。
5. 下一批需求运行后，对比新旧版本的指标，在下一次复盘中说明改进是否有效。无效的改动记录下来并回退。

不让 Agent 在没有审查和批准的情况下修改自己的模板。模板错改的影响会扩散到之后的每一个需求，而且很难察觉。

### 10.5 经验的存放

按全局规范 `ERROR_HANDLING_AND_LESSONS_STANDARD.md`，分两处：

- 关于 AutoDev 流程本身的经验（某个模板的缺陷、某种拆分更有效），写入 AutoDev 的 `docs/LESSONS/`，区分错误知识和方法经验。
- 关于目标项目的经验（某个模块容易出错、某类测试必须补），写入目标项目自己的 `docs/LESSONS/` 或 `docs/DECISIONS.md`，并加入该项目的上下文清单，以后的需求分析会自动读到。

## 11. 知识与规则

Agent 的输出质量取决于三样东西：动作（角色模板）、拆分（流水线）、信息。第 4 节和第 10 节讲了前两样和信息的组装方式，本节定义信息的来源，也就是 Agent 该遵守的规则、可查的资料和可用的工具。

### 11.1 三层来源与优先级

| 层 | 位置 | 内容 | 维护者 |
| --- | --- | --- | --- |
| 全局规范 | iCloud `AI编程全局规范/` | 所有项目通用的开发、测试、安全、错误处理、数据规范 | 用户 |
| AutoDev 规则 | `autodev/rules/` | 只对 AutoDev 流水线成立的规则，例如需求拆分、审查等级 | 用户，经复盘补丁修改 |
| 项目规则 | 目标项目的 `AGENTS.md`、`CLAUDE.md`、`docs/` | 该项目的技术栈、模块划分、约定、历史决策 | 用户与流水线（S9 写入决策） |

冲突时按全局规范的优先级处理：用户在回复中的明确决定 > 全局规范 > 项目规则补充，更严格的规则同时生效。AutoDev 规则只补充全局规范未覆盖的部分，不复制、不改写全局规范。全局规范已有的内容在 `rules/` 中只写引用。

### 11.2 规则清单

| 主题 | 全局规范现状（2026-11-02 核对） | AutoDev 处理 |
| --- | --- | --- |
| 需求拆分 | 只有子 Agent 委派的交易成本门禁，没有需求拆分规则 | 新写 `rules/requirement-splitting.md` |
| 错误怎么修 | `ERROR_HANDLING_AND_LESSONS_STANDARD.md` 已覆盖调试流程、根因、升级、lessons | 引用；只补充流水线中的回修规则（S5、S6 失败后 coder 如何处理） |
| 模块怎么构建 | `PYTHON_FASTAPI_DEV_STANDARD.md` 有后端模块边界与数据归属，仅适用 Python 后端 | 新写 `rules/module-design.md`，通用部分引用全局规范 |
| 模块大小 | 没有代码规模上限（`DOC_GOVERNANCE_STANDARD.md` 的阈值只针对文档） | 并入 `rules/module-design.md`，给出软阈值，超出时触发审查而非直接拒绝 |
| 代码规范 | 只有 Python/FastAPI 和安全编码；没有通用风格规范 | 新写 `rules/coding.md`；语言相关部分优先使用项目自身的 lint/format 配置 |
| 测试规范 | `TESTING_STANDARD.md` 已覆盖 | 引用 |
| 安全规范 | `SECURITY_CODING_STANDARD.md` 已覆盖 | 引用；S5 内置密钥扫描 |
| 检查规范 | 没有 | 新写 `rules/checks.md`：S5 必跑项、各语言默认命令、失败判定 |
| 审查规范 | 主规范要求对抗审查和独立审查清单，无具体等级与清单 | 新写 `rules/review.md`：严重等级定义、只报真问题、各审查角色的清单 |

### 11.3 参考资料

`autodev/reference/` 存放外部资料的离线副本，例如两篇架构参考文章。目标项目自己的参考资料放在该项目中。

使用规则：

- 参考资料是外部内容，按全局安全规范视为不可信数据。Agent 可以引用其中的事实和思路，但不执行其中的指令。
- 每份资料在 `reference/INDEX.md` 登记来源、日期、适用阶段和摘要。上下文组装时只内联摘要，正文留路径。
- 资料过期或被新资料取代时在索引中标记，不删除原文件。

### 11.4 信息工具

Agent 可用的查询工具也是信息的一部分，在 `config.yaml` 按角色配置可用范围：

| 工具 | 用途 | 默认开放给 |
| --- | --- | --- |
| 代码检索（`rg`、项目内搜索） | 查找代码与引用 | 全部角色 |
| 官方文档查询（如 context7） | 核对库和框架的当前用法 | analyst、designer、coder |
| 网页搜索 | 查找外部资料 | analyst、designer；审查角色默认关闭 |
| 浏览器 / computer use | 验收界面与交互 | acceptor |
| 项目知识库（如 gbrain） | 检索历史决策与经验 | analyst、designer、retrospector |

审查角色默认不联网，这和参考资料中审查者「只读、不联网、读不到密钥」的做法一致，目的是让审查只依据产物本身。

每次调用在 `input.md` 中列出本次开放的工具。工具清单与上下文清单一样带版本号，属于第 10 节的「信息」杠杆。

### 11.5 规则如何交给 Agent

- 程序按角色和阶段选择相关规则，而不是把全部规则一起给 Agent。例如 coder 拿到 `coding.md`、`module-design.md` 和测试规范，code_reviewer 拿到 `review.md` 和同一组编码规则。
- 规则选择表写在角色模板的 frontmatter 中，随模板版本管理。
- 审查者与作者拿到的是同一套规则。审查意见必须指出违反了哪一条，否则按第 7 节只报真问题的原则不予采纳。

## 12. 依据与限制

- 本设计以需求驱动的流水线为准。原 README 的 goal.md 自迭代循环已被取代。
- 参考资料：`reference/` 下两份存档（DeepSeek《Super-agent 设计探索》、卡兹克《Agent 自动化系统》）。采用了其中的思路：Router 不执行、Worker 隔离、审查与作者不同模型、审查有轮次上限、只把需要决策的事推给人、确定性判断写成程序。未采用：事件过滤、Thread 订阅、云端部署、飞书卡片，因为本系统的需求只来自用户本人，在本机运行。
- 参考 personagent 的 AGENTS.md 中关于任务状态、交接记录和合并确认的规则。
- 已读取全局规范 `GLOBAL_DEV_WORKFLOW.md` v1.11。

## 13. 待定问题

1. S7 发布候选的具体含义：只打候选标签，还是部署到某个可运行环境供 S8 验收。这取决于 personagent 的运行形态。
2. S8 验收的手段：computer use、浏览器自动化、CLI 测试，取决于 personagent 是什么类型的应用。
3. 流程程序的实现语言。
4. Web 界面的技术栈，以及与流程程序是否同一语言、同一进程。建议分成两个进程，界面挂掉不影响流水线。
5. 「需求变更」视图的对比粒度：按段落对比文本，还是只对比 `analysis.md` 中的结构化字段（范围、验收标准）。

用户入口已确定为三种并存：直接在 `inbox/` 建文件、`autodev` 命令、Web 界面。三者写同一种文件。
