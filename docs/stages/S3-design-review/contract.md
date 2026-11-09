# S3 设计审查：输入输出与交接契约

日期：2026-11-09。状态：当前旧流水线契约；D019 与 V2.1 目标能力见 [standard.md](standard.md)。返回 [S3 入口](README.md)。

## 1. 输入、角色与边界

开始条件是 S2 本轮 DONE。角色为 `design_reviewer`，有效执行器与完整模型 ID 从 [注册表](../../../config/agents.toml) 及项目覆盖解析，不在本文另设默认模型。

当前模板输入：原始需求、S1 分析、S2 最新轮次共用的项目快照、`design.md`、`dev-plan.md`、`prototype.md`。输入由 [pipeline.write_input](../../../src/cockpit/pipeline.py) 列在本轮 `input.md`；快照规则见 [S2 contract](../S2-design/contract.md)。不能只看作者的分析转述，也不能私自用更新后的项目文件替换审查基线。

审核者只产出审查文档，不修改目标项目代码或设计。该职责约束不等于 S2/S3 设计文件已有操作系统只读保护；S6/S8 的代码指纹校验也不能套称为已存在的设计包锁定机制。

## 2. 交付与程序校验

输出在 `workspace/runs/<运行号>/S3-design-review/round-N/`：

| 文件 | 要求与用途 |
| --- | --- |
| `review.md` | frontmatter 给出 verdict 与 findings；每项含 id、severity、location、problem、expected；必须有“原文对照”小节 |
| `done.json` | 运行号、阶段、轮次、角色、摘要、产物和结论等完成信息 |
| `record-aN.json`、`agent-aN.log` | 程序记录尝试、模型证据及原始日志；不是 Agent 自报的替代品 |

模板要求 PASS 时无 critical/high 问题；程序现有完成校验只核对约定文件、完成标记及“原文对照”标题是否存在，未实现 findings 的完整语义一致性检查。标题存在不能证明逐条对照已完成。

## 3. 结果与消费者

| verdict | 当前去向 |
| --- | --- |
| PASS | `pipeline/design` 结束；`pipeline/build` 进入 S4 同轮 |
| REWORK | 回 S2，新轮次；达到 `design_review_rounds` 上限转人工 |
| BLOCK | needs-human，不按通过处理 |

返修保留旧轮次的设计与审查；新轮次重新产出。S4/S6/S8 读取当前运行最新 S2 设计文件。正式设计包的哈希、版本锁定、意见失效和导出关联尚未实现，不以最新文件名代替完整版本协议。

## 4. 追溯与未接入能力

已有证据为本轮输入、审查、完成标记、尝试日志、共用上下文快照与运行事件。没有独立审核、单模型降级和复用免审三种可执行放行记录协议；现有 `check_vendors` 仍有旧跨厂商硬校验。

V2.1 的 `designsys.validate.validate_pack` 已是可调用独立模块，但没有接入 S3 转移。当前的 PASS 不代表 V1–V4 检查已全部运行；原型交互验证与截图评审也未接入。审查范围、风险处理及人工决定见 [standard.md](standard.md)。
