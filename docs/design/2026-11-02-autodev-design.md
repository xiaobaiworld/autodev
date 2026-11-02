---
title: AutoDev 流程设计（2026-11-02）
created: 2026-11-02
updated: 2026-11-02
status: 草稿
summary: AutoDev 是一个本地的需求驱动编程流程。用户在 inbox 提需求，主 Agent 按目录状态分发给执行 Agent 和独立的审查 Agent，循环直到通过或交人工决定。本文定义角色、目录、状态机、多项目模型、轮次上限与恢复方式，并列出待定问题。
---

# AutoDev 流程设计（2026-11-02）

## 1. 目标与范围

AutoDev 是一个在本机运行的编程流程。用户每次提出一条需求，系统在指定的目标项目里完成修改、审查和回修，最后交给用户确认。

本文只定义流程，不涉及具体实现语言。AutoDev 自身不保存业务代码，它管理的是一组目标项目。第一批目标项目是 `personagent`，后续可以增加更多项目。

不在范围内的事项：GitHub Issue、PR、CI、Webhook、定时任务、飞书通知。这些属于原架构图中的线上部分，本地版本不做。

## 2. 角色与读写边界

| 角色 | 职责 | 可写位置 |
| --- | --- | --- |
| 主 Agent（路由） | 扫描目录、移动需求文件、创建和清理 worktree、运行确定性检查、追加 events.jsonl | `requests/`、`runs/<id>/events.jsonl`、目标项目的 worktree 与分支 |
| 执行 Agent | 在 worktree 里按 spec 修改代码，写执行报告 | 对应 worktree，`runs/<id>/attempt-N/` |
| 审查 Agent | 读 spec、diff、测试日志，给出结论 | 只写 `runs/<id>/attempt-N/review.md` |
| 用户 | 提需求，决定 PASS 后是否合并，处理 needs-human | `requests/inbox/`、`requests/done/`、`requests/rejected/` |

规则：每个文件只有一个写者。执行 Agent 与审查 Agent 不共享推理过程，审查 Agent 只看产物，不看执行 Agent 的对话。

主 Agent 使用 Codex，运行在 herdr 管理的 pane 中。它选用便宜模型，只做流转，不做复杂判断。执行 Agent 与审查 Agent 各占一个 pane，分别由 herdr 启动。审查 Agent 默认使用与执行 Agent 不同的模型。

## 3. 目录结构

AutoDev 仓库只放流程状态和配置：

```
autodev/
├── config.yaml              # 项目注册表、轮次上限、执行与审查 Agent 配置
├── workspace/
│   ├── goal.md              # 现有文件，保留
│   ├── requests/            # 需求状态机，状态即目录
│   │   ├── inbox/
│   │   ├── active/
│   │   ├── review/
│   │   ├── rework/
│   │   ├── needs-human/
│   │   ├── done/
│   │   └── rejected/
│   └── runs/<id>/           # 每个需求的产物
│       ├── spec.md
│       ├── events.jsonl
│       └── attempt-N/
│           ├── diff.patch
│           ├── exec-report.md
│           ├── test.log
│           └── review.md
└── docs/
```

目标项目不在 autodev 里。worktree 放在目标项目旁边，避免和流程文件混在一起。

## 4. 需求状态机

```
inbox → active → review → done
                  │  ↑
                  ↓  │
                rework
                  │
                  ↓
              needs-human
```

| 状态 | 进入条件 | 离开条件 |
| --- | --- | --- |
| inbox | 用户新建 `<id>.md` | 主 Agent 领取，移到 active |
| active | 主 Agent 生成 spec、建 worktree、分派执行 | 执行 Agent 完成，移到 review |
| review | 执行完成，确定性检查通过 | 审查给出 PASS、REWORK 或 BLOCK |
| rework | 审查给出 REWORK，且未超轮次上限 | 执行 Agent 修改完成，回到 review |
| needs-human | 超过轮次上限、执行或审查阻塞、确定性检查连续失败 | 用户决定 |
| done | 审查 PASS，用户确认 | 终态 |
| rejected | 用户驳回 | 终态 |

移动文件使用原子 rename，同一需求不会被领取两次。

## 5. 单轮流程

1. 主 Agent 扫描 `inbox/`，取一个需求，按项目注册表确定目标项目。
2. 生成 `runs/<id>/spec.md`，包含目标、允许修改的范围（项目目录减去排除清单）、验收标准。
3. 为该需求建一个 worktree 和分支，移到 `active/`，分派执行 Agent。
4. 执行 Agent 改代码，写入 `attempt-N/diff.patch` 与 `exec-report.md`，主 Agent 移到 `review/`。
5. 主 Agent 做确定性检查：diff 是否触及排除清单、测试与构建是否通过。失败则退回 `rework/`，不调用审查 Agent。
6. 审查 Agent 读取 spec、diff、test.log，写入 `review.md`，结论为以下之一：
   - PASS：移到 `done/`，等用户确认合并；
   - REWORK：移到 `rework/`，回到第 4 步；
   - BLOCK：移到 `needs-human/`。
7. 每一步都向 `events.jsonl` 追加一行。

## 6. 多项目模型

`config.yaml` 维护项目注册表：

```yaml
projects:
  - name: personagent
    repo: ~/code/personagent
    base_branch: master
    worktree_root: ~/code/.worktrees/personagent
    exclude:
      - .git/
      - ".env*"
      - "*.lock"
      - .local-backups/
      - config.yaml
```

- 需求文件的 frontmatter 写明 `project: <name>`，缺失则不领取，移到 `needs-human/`。
- 同一项目同一时间只允许一个 active 需求，避免多个 worktree 同时修改同一仓库的分支状态。不同项目之间可以并行。
- 排除清单按项目配置，不设全局默认以外的隐含规则。

## 7. 轮次与失败

- 轮次上限在 `config.yaml` 中设置，默认 3 轮。超过即进入 needs-human。
- 执行 Agent 或审查 Agent 进入 blocked 状态（例如等待审批对话框），主 Agent 不替它回答，直接进入 needs-human。
- 主 Agent 崩溃后重启，先读取 `active/` 与 `review/` 中的文件，对照各 `runs/<id>/events.jsonl` 的最后一行，决定继续、回退或转 needs-human。
- worktree 清理只在需求进入 done、rejected 或 needs-human 并经用户确认后执行，避免误删未提交的改动。

## 8. 待定问题

1. 执行 Agent 用哪个：Claude Code、Codex，还是两者都支持。
2. 审查 Agent 用哪个，是否与执行 Agent 强制不同模型。
3. PASS 后的确认方式：终端提示，还是只放在 done 目录等用户手动处理。
4. 是否需要 `needs-human` 的通知（终端、系统通知或无）。
5. 确定性检查的具体命令：由项目注册表配置，还是由主 Agent 根据项目类型推断。
6. 第一个需求是否只做文档类，以验证整条流程。

## 9. 依据与限制

- 本设计以需求队列流转为准。原 README 描述的 goal.md 自迭代循环（planner、executor、evaluator、evolver）与本设计不一致，已在 README 中取代，不作为本设计依据。
- 参考 personagent 的 AGENTS.md 中关于任务状态、交接记录和合并确认的规则。
- 全局规范 `GLOBAL_DEV_WORKFLOW.md` 当前无法读取（macOS 对 iCloud 路径返回 EPERM），因此本文未对照它。待权限修复后需要补读，并核对是否有需要遵守的额外要求。
- herdr 的命令与 skill 来自本机 `herdr --skill` 输出，未在实际运行中验证。
