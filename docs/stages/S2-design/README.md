# S2 设计

日期：2026-11-09。所属工作区：设计。状态：旧 Markdown 流水线已实现，V2.1 独立资产尚未接入。返回 [阶段总览](../README.md)。

| 要了解什么 | 唯一正文或入口 |
| --- | --- |
| 从哪里开始、读什么、写到哪里、交给谁 | [contract.md](contract.md) |
| 工作顺序、复用、原型、完成与人工决定 | [standard.md](standard.md) |
| 当前实际执行的角色、任务与转移 | [design.json](../../../templates/pipeline/design.json)，build 路径继承它 |
| 目标设计规范 | [V2.1](../../Agent自动化设计阶段规范_V2.1.md)；本页不复制规范摘要 |
| 本项目采用方式与未定事项 | [采用对照](../../design/2026-11-09-v21-mapping.md) |
| 规则、Schema 与校验器 | [design-system](../../../design-system/README.md) |
| 渠道、角色上下文与平台关系 | [阶段机器人设计](../../design/2026-11-08-stage-bots-design.md) |

当前角色为 `designer`；有效执行器和完整模型 ID 从注册表及覆盖配置解析。S2 输出 `design.md`、`dev-plan.md`、`prototype.md` 与完成标记；DONE → S3 同轮，BLOCK → 人工处理。版本、证据与代码检查的实际范围见契约，不把文档存在当作业务正确。

先读本页、契约、工作规范及本轮 input.md；按需查主规范、资产和对应项目资料。不自动读取其他项目、无关历史或凭证。现有未实现内容见契约末节与当前 next，暂不建立空 templates/examples 目录。
