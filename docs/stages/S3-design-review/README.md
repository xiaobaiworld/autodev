# S3 设计审查

日期：2026-11-09。所属工作区：设计。状态：旧 PASS/REWORK/BLOCK 协议已实现，D019 分级放行与 V2.1 验证尚未接入。返回 [阶段总览](../README.md)。

| 要了解什么 | 唯一正文或入口 |
| --- | --- |
| 审查输入、权限、产物、版本与交接 | [contract.md](contract.md) |
| 审查内容、分级策略、验证和人工决定 | [standard.md](standard.md) |
| 当前执行任务与去向 | [design.json](../../../templates/pipeline/design.json)、[build.json](../../../templates/pipeline/build.json) |
| 作者输入与设计交付 | [S2 contract](../S2-design/contract.md) |
| 已接受的策略与项目取舍 | [D019](../../DECISIONS.md#d019-设计审查分级优先独立审核允许降级与简单复用免审)、[V2.1 采用对照](../../design/2026-11-09-v21-mapping.md) |
| 程序验证的现状与限制 | [design-system](../../../design-system/README.md) |

当前角色为 `design_reviewer`，模型从有效注册表解析。产出 `review.md`（必须有“原文对照”）和完成标记；PASS 在 design 类型结束、在 build 类型进 S4；REWORK 回 S2 加轮次；BLOCK 或返修超限转人工。

先读本页、契约、规范与本轮 input.md，再检查完整需求、同一快照和完整设计产物。其他资料按任务加载，不能用无关聊天或后来更新的文件替代输入基线。检查范围、版本缺口与未接入能力见契约，不把旧跨厂商限制当作 D019 的当前设计要求。
