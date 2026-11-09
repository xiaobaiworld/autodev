# S9 正式发布

状态：入口说明，2026-11-09 建立；事实来自 `templates/pipeline/*.json`、`config/agents.toml` 与源码，**不是新规则**。所属工作区：测试。返回 [阶段总览](../README.md)。

## 基本信息

| 项 | 内容 |
| --- | --- |
| 运行目录名 | `S9-publish` |
| 执行角色 | publisher（发布者） |
| 执行方式 | **程序**，前面有**人工关口**（`gate: human`） |
| 注册表默认的 Agent 与模型 | 无（程序步骤） |
| 可能的结论 | PASS、BLOCK |
| 结论去向 | PASS → 完成；进入前停在人工关口，等用户批准 |

## 读取什么（输入）

- 验收结果
- **人工批准**
- 版本配置（`build.json` 里 `version` 写死为 `0.1.0`，`note` 是演示项目的“命令行待办工具”）

## 产出什么（输出）

- 本地正式标签（形如 `v0.1.0`）
- `CHANGELOG.md`
- `release.log`

## 交接

- 上游：S8 通过的验收
- 下游：无（流水线终点）
- 人工介入：**进入前必须由用户批准**：`python3 -m driver.reply <运行号> continue`

## 证据与追溯

- `release.log`、代码目录里的标签与 `CHANGELOG.md`；**只在本地，不推送、不部署**。同名正式标签已存在时拒绝覆盖（BLOCK），转人工

## 需要特别说明的

- 批准通过 `driver.reply` 或 Web 的“待你决定”完成，不由飞书线程直接改状态。

## 尚未实现或未验证

- 不推送远端、不部署：这两件事目前没有流程。

## 阅读清单

| 资料 | 说明 |
| --- | --- |
| [流水线模板](../../../templates/pipeline/build.json) | |
| [人工回复](../../../src/driver/reply.py) | |

此目录目前只有这份入口；内容多了再拆出 `contract.md`、`standard.md`，需要时再建 `templates/`、`examples/`，不预建空目录。
