# S5 检查

状态：入口说明，2026-11-09 建立；事实来自 `templates/pipeline/*.json`、`config/agents.toml` 与源码，**不是新规则**。所属工作区：测试。返回 [阶段总览](../README.md)。

## 基本信息

| 项 | 内容 |
| --- | --- |
| 运行目录名 | `S5-check` |
| 执行角色 | checker（检查者） |
| 执行方式 | **程序**，不是 Agent |
| 注册表默认的 Agent 与模型 | 无（程序步骤） |
| 可能的结论 | PASS、FAIL、BLOCK |
| 结论去向 | PASS → S6；FAIL → 回 S4，轮次加一，受 `check_rounds` 上限约束；BLOCK → 阻塞 |

## 读取什么（输入）

- 代码目录（`workdir`，只用不改）
- 模板里的检查命令（`build.json` 的 S5 写的是 `python3 -m unittest discover -s tests`，`design.json` 没有 S5）

## 产出什么（输出）

- `check.log`（命令输出、退出码；超时被杀会注明）

## 交接

- 上游：S4 的代码
- 下游：S6 读取本轮检查结果（`check_now`）
- 人工介入：失败轮次超限时转人工

## 证据与追溯

- `check.log`；程序步骤没有中台运行与 Agent 日志，记录里标 `tool`

## 需要特别说明的

- **不信 Agent 自述**：结论完全由命令退出码决定；退出码为 0 但一个测试都没跑也判 FAIL。
- 实现见 `src/cockpit/tools.py` 的 `run_check`。环境变量被精简，HOME 与临时目录指向步骤目录下的草稿目录。

## 尚未实现或未验证

- 检查命令现在写死在 `templates/pipeline/build.json` 的 S5；`config.yaml` 里项目的 `checks` 仍是待定，目标项目的检查命令需显式配置。

## 阅读清单

| 资料 | 说明 |
| --- | --- |
| [流水线模板](../../../templates/pipeline/build.json) | |
| [程序步骤实现](../../../src/cockpit/tools.py) | |

此目录目前只有这份入口；内容多了再拆出 `contract.md`、`standard.md`，需要时再建 `templates/`、`examples/`，不预建空目录。
