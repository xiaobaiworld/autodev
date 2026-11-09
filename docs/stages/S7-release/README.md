# S7 发布候选

状态：入口说明，2026-11-09 建立；事实来自 `templates/pipeline/*.json`、`config/agents.toml` 与源码，**不是新规则**。所属工作区：测试。返回 [阶段总览](../README.md)。

## 基本信息

| 项 | 内容 |
| --- | --- |
| 运行目录名 | `S7-release` |
| 执行角色 | releaser（发布者） |
| 执行方式 | **程序** |
| 注册表默认的 Agent 与模型 | 无（程序步骤） |
| 可能的结论 | PASS、BLOCK |
| 结论去向 | PASS → S7U；BLOCK → 阻塞 |

## 读取什么（输入）

- 前序通过的代码与版本配置

## 产出什么（输出）

- 本地 git 候选标签（形如 `v0.1.0-rc.N`）
- `release.log`

## 交接

- 上游：S6 通过的代码审查
- 下游：S7U 使用验证
- 人工介入：无单独人工关口

## 证据与追溯

- `release.log` 与代码目录里的标签；**只在本地，不推送**

## 需要特别说明的

- 实现见 `src/cockpit/tools.py` 的 `run_release`：候选标签序号取已有 rc 标签最大值加一，不会冲突。版本号 `0.1.0` 现在写死在 `build.json`。

## 尚未实现或未验证

- 无

## 阅读清单

| 资料 | 说明 |
| --- | --- |
| [流水线模板](../../../templates/pipeline/build.json) | |
| [程序步骤实现](../../../src/cockpit/tools.py) | |

此目录目前只有这份入口；内容多了再拆出 `contract.md`、`standard.md`，需要时再建 `templates/`、`examples/`，不预建空目录。
