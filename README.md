# AutoDev

AutoDev 是一个在本机运行的需求驱动编程流程。用户在 `workspace/requests/inbox/` 放一条需求，主 Agent 按目录状态分派执行 Agent 和独立的审查 Agent，循环到审查通过或交由人工决定。

## 当前阶段

第一阶段只跑通一个目标项目，第一个目标是 `personagent`。多项目模型已经在设计中预留（见 `config.yaml` 的 `projects` 注册表），但暂不作为本阶段的验收内容。

## 核心流程

```
inbox → active → review → done
                  │  ↑
                  ↓  │
                rework
                  │
                  ↓
              needs-human
```

- 主 Agent：扫描目录、生成 spec、建 worktree、运行确定性检查、记录事件
- 执行 Agent：在 worktree 中按 spec 修改代码
- 审查 Agent：只读 spec、diff 和测试日志，给出 PASS、REWORK 或 BLOCK

每个文件只有一个写者。审查 Agent 不看执行 Agent 的对话，只看产物。

## 文档

- `docs/design/2026-11-02-autodev-design.md`：流程设计（草稿）
- `docs/DECISIONS.md`：关键决策记录

## 状态

设计阶段，尚无可运行代码。待定问题见设计文档第 8 节。
