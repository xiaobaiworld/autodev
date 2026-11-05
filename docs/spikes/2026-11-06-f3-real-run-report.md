# F3 报告：真实流水线在 Herdr 三格里实时跑（2026-11-06）

入口：`python3 -m driver.run --home <autoloop 数据目录> --root <AutoDev 根目录> --request <需求.md> --effort low`。中台是 `/tmp/autodev-demo` 里的那个，看板和日志窗格读同一个 home 和 root。

## 结果

| 项 | 结果 | 证据 |
| --- | --- | --- |
| S1 到 S3 跑通 | 通过，约 140 秒 | S1 ACCEPT、S2 DONE、S3 PASS，状态 done |
| 实际模型 | S1、S2 为 `claude-opus-5-5`；S3 为 `gpt-6-sol`、强度 low | Claude 日志的 `model` 字段；Codex 会话记录 `turn_context` |
| 运行中日志实时出现 | 通过 | 截图：S1 运行 12 秒时，左窗格已显示 Read input.md、Read context.json |
| 看板同步 | 通过 | 截图：`#4 s1-analyst claude-opus 运行中 00:12` |
| 中台日志同步 | 通过 | 右下窗格 `run 4 (s1-analyst) turn 1 started` |

## 运行中发现并修掉的

- 日志窗格的标题重复出现：窗格只有 63 列，日志行最宽 166 列，折行后画面比窗格高，滚动把旧画面留在上面。改为按显示宽度截断，并有测试保证每行不超过窗格宽度。
- 看板同样比窗格高，标题被挤出。改为从多到少试，直到放得下。
- 工具结果开头的行号（`1\t---`）去掉。

## 没验证的 / 要注意的

- 这次 S3 一次 PASS，REWORK 回路仍只用假 Agent 测过。
- Codex 这一轮读了本机的全局规范文件（`~/Library/Mobile Documents/.../GLOBAL_DEV_WORKFLOW.md`）和仓库里的 `next.md`、`docs/` 文件；原因是 Codex 的工作目录是 workspace，它去找项目规则。会不会影响审查结论没有评估。
- 看板只列 active 和 needs-human 的需求，跑完的需求（status done）从看板上消失，只剩运行列表里的几行。这是个缺口。
- 看板第一行的 `R20261105-001` 是我之前调试留下的旧失败记录，一直占着位置。
