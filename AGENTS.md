# AutoDev：给 Agent 的项目说明

## 第一步：先查工具手册

找任何功能之前（建窗格、读终端、发事件、看状态、调模型……），先读 [`docs/TOOLS.md`](docs/TOOLS.md)。里面有已确定的工具、该查的在线文档、跑通过的命令和踩过的坑。先找这里，再找别处。

- 查工具用法：先看 `docs/TOOLS.md` 里的在线文档链接，再用工具自带手册核对版本。
- 不要用 `herdr --help` 或 `herdr pane ...` 去查。本机的 `herdr` 是终端版，不是桌面应用（`docs/lessons.md` L011）。
- 查到新用法或踩到坑，补进 `docs/TOOLS.md` 和 `docs/lessons.md`。

## 开始任务前

1. 读 `next.md`（当前状态）和 `docs/lessons.md`（已踩的坑）。
2. 模型名只写完整 ID，见 `docs/MODELS.md`。
3. 决策在 `docs/DECISIONS.md`，当前主线方案在 `docs/design/2026-11-05-autoloop-foundation.md`。文档入口是 `docs/INDEX.md`。

## 约定

- 地基是 agent-autoloop（`~/code/agent-autoloop`，提交 `8f8e2ee`），不改它的内核。改前先在 `docs/DECISIONS.md` 记原因。
- 不动用户已有的 Herdr 空间和终端（如 `pro1`）。`hc kill`、`herdr-app do ...close` 只用于自己创建的。
- 测试：`PYTHONPATH=src python3 -m unittest discover -s tests`，提交前必须全过。联机脚本 `tests/f1_agents.py`、`tests/f2_pipeline.py` 会花额度。
- 提交格式 `<类型>: <一句话>`（feat、fix、test、doc、refactor）；文档与代码同提交或连续两个提交内同步。
- 通用规范见用户的全局 `~/.claude/CLAUDE.md`，与本文冲突时以全局规范为准。
