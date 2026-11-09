# S7U 使用验证

状态：入口说明，2026-11-09 建立；事实来自 `templates/pipeline/*.json`、`config/agents.toml` 与源码，**不是新规则**。所属工作区：测试。返回 [阶段总览](../README.md)。

## 基本信息

| 项 | 内容 |
| --- | --- |
| 运行目录名 | `S7U-usage` |
| 执行角色 | user-simulator（使用模拟） |
| 执行方式 | **程序** |
| 注册表默认的 Agent 与模型 | 无（程序步骤） |
| 可能的结论 | PASS、FAIL、BLOCK |
| 结论去向 | PASS → S8；FAIL → 回 S4，轮次加一，受 `usage_rounds` 上限约束；BLOCK → 阻塞 |

## 读取什么（输入）

- 候选代码
- **人写的使用脚本**（写在模板的 S7U 里）

## 产出什么（输出）

- `usage.log`（每步命令的原始输出）

## 交接

- 上游：S7 的候选标签
- 下游：S8 优先引用使用记录
- 人工介入：失败轮次超限时转人工

## 证据与追溯

- `usage.log`；在隔离环境（临时 HOME 与数据文件）里把做出来的东西真的用一遍

## 需要特别说明的

- **当前使用脚本写死在 `templates/pipeline/build.json`，内容是演示项目 `todo` 的命令**（如 `bin/todo add`）。换成别的目标项目必须换一份脚本，不能当作通用验收。

## 尚未实现或未验证

- 使用脚本尚未做成按目标项目配置。

## 阅读清单

| 资料 | 说明 |
| --- | --- |
| [流水线模板](../../../templates/pipeline/build.json) | |
| [程序步骤实现](../../../src/cockpit/tools.py) | |

此目录目前只有这份入口；内容多了再拆出 `contract.md`、`standard.md`，需要时再建 `templates/`、`examples/`，不预建空目录。
