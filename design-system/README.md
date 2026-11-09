# 设计阶段可执行资产

日期：2026-11-09。状态：MVP 1 独立模块已实现，尚未接入流水线或设计机器人。阶段说明从 [S2](../docs/stages/S2-design/README.md)、[S3](../docs/stages/S3-design-review/README.md) 进入，目标规范是 [V2.1](../docs/Agent自动化设计阶段规范_V2.1.md)，本页只解释资产布局。

| 位置 | 职责 | 当前边界 |
| --- | --- | --- |
| [rules/classification.toml](rules/classification.toml) | 功能特征、风险与 D0–D3 分类条件 | 初版阈值，需真实需求校准 |
| [rules/library.toml](rules/library.toml) | 18 条基线规则与适用条件 | 全为 R1，没有逐条规则验证器和成熟样例 |
| [schemas/](schemas/) | plan、technical、data、security、handoff 五种结构 | MVP 1 的 A01/A04/A05/A07/A08；尚无完整 UI/API 产物 Schema |
| [src/designsys/](../src/designsys/) | 分类、规则选择、Schema/设计包验证、D0 文档生成 | 纯函数模块，不派 Agent、不改流水线状态 |
| [测试](../tests/) 中的 `test_designsys_*` | 分类、结构、规则覆盖与失败处理等单元验证 | 不代表真实设计包或机器人验收 |

用法与已知限制统一维护在 [TOOLS 第 15 节](../docs/TOOLS.md#15-设计阶段-v21-的可执行资产d0262026-11-09)。不要把可执行文件搬入 `docs/stages/`，也不要将运行时设计包写到本目录。

尤其需要区分：验证器当前信任 `plan.json` 声明的特征，尚无需求文本独立核对；V1–V3 也只是已有检查子集，不能宣称四层验证齐全；原型交互指标当前为“不适用”。设计包的版本锁定与持久化位置仍需在接入方案中确定。
