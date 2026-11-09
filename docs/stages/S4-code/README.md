# S4 编码

状态：入口说明，2026-11-09 建立；事实来自 `templates/pipeline/*.json`、`config/agents.toml` 与源码，**不是新规则**。所属工作区：开发。返回 [阶段总览](../README.md)。

## 基本信息

| 项 | 内容 |
| --- | --- |
| 运行目录名 | `S4-code` |
| 执行角色 | coder（编码者） |
| 执行方式 | Agent |
| 注册表默认的 Agent 与模型 | codex / codex |
| 可能的结论 | DONE、BLOCK |
| 结论去向 | DONE → S5（同一轮）；BLOCK → 阻塞 |

## 读取什么（输入）

- 需求、分析、设计、计划、原型
- 代码目录（`workdir`，可写）
- 上一轮检查结果（`check_prev`）与代码审查意见（`review_code_prev`）
- 人工意见（`human`）

## 产出什么（输出）

- 代码变更（在 `workspace/projects/<项目>/<运行号>/` 的 git 仓库里，git 操作全部由程序完成）
- `exec-report.md`

## 交接

- 上游：S3 通过的设计包
- 下游：S5 检查，S6 看完整差异
- 人工介入：BLOCK 或各返修轮次超限时转人工

## 证据与追溯

- 代码目录的 git 历史、`full.patch`、`exec-report.md`、`record-aN.json`

## 需要特别说明的

- 原有 [S4 编码阶段设计](../../design/2026-11-06-s4-code-stage.md) 已标为历史设计稿：模板驱动、build 类型与 S4 等核心内容已实现。保留原位作追溯，不再当成当前待办；旧实验未逐项复跑，不能据此宣称全部验证。
- 编码者只改文件、不碰 git；检查与审查者对代码目录只读。

## 尚未实现或未验证

- 目标项目的路径与检查命令需显式配置，不能沿用演示项目。

## 阅读清单

| 资料 | 说明 |
| --- | --- |
| [流水线模板](../../../templates/pipeline/build.json) | |
| [S4 编码阶段设计（原稿）](../../design/2026-11-06-s4-code-stage.md) | |
| [工作目录实现](../../../src/cockpit/workdir.py) | |

此目录目前只有这份入口；内容多了再拆出 `contract.md`、`standard.md`，需要时再建 `templates/`、`examples/`，不预建空目录。
