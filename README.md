# AutoDev

AutoDev 是本机运行的需求驱动开发流程。确定性程序控制阶段、轮次和状态，Agent（Claude、Codex、agy）分别负责需求分析、设计、编码、审查和验收。

## 当前状态

以 [agent-autoloop](https://github.com/KKKKhazix/agent-autoloop) 为地基（`docs/DECISIONS.md` D014）：它负责派活、排队、重试、租约、事实日志，Agent 以无界面进程运行；我们的流水线驱动放在它外面，管阶段、审查轮次上限、作者与审查者厂商不同、产物校验。Herdr 桌面应用只做显示和管理窗口。

- 已跑通：真实 Agent 完成 S1 需求分析、S2 设计、S3 设计审查（`docs/spikes/2026-11-05-f2-pipeline-report.md`）。
- 进行中：命令行看板（`src/dashboard/`），布局放在 Herdr 的 `pro2` 空间。
- S1～S9 已连通，具体当前状态与限制见 next.md；上述早期验证记录保留追溯。
- 新增需求澄清模块：独立后端、CLI 和本机网页共用会话、双模型审核、人工确认与固定版本导出。启动无费用演示：`PYTHONPATH=src python3 -m requirements --demo serve`，打开 `http://127.0.0.1:8765`。真实配置与用法见 [使用指南](docs/modules/requirements/usage.md)。
- 通用手机消息路由及需求适配已实现，飞书/微信真实连接待确定渠道，见 [接入说明](docs/modules/requirements/channels.md)。

当前步骤和下一步见 [`next.md`](next.md)，方案见 [`docs/design/2026-11-05-autoloop-foundation.md`](docs/design/2026-11-05-autoloop-foundation.md)。

## 运行测试

```sh
PYTHONPATH=src python3 -m unittest discover -s tests          # 单元测试，不联网
python3 -I tests/smoke_autoloop.py                            # 联机冒烟，假 Agent，不花额度
```

`tests/f1_agents.py` 和 `tests/f2_pipeline.py` 会调用真实 Agent，花额度。需要先把 agent-autoloop 检出到 `~/code/agent-autoloop` 并切到提交 `8f8e2ee`。

## 文档

入口是 [`docs/INDEX.md`](docs/INDEX.md)。最常用的：

- [`next.md`](next.md)：当前状态与下一步
- [`docs/design/2026-11-05-autoloop-foundation.md`](docs/design/2026-11-05-autoloop-foundation.md)：当前主线方案
- [`docs/design/2026-11-02-autodev-design.md`](docs/design/2026-11-02-autodev-design.md)：九阶段流水线设计
- [`docs/DECISIONS.md`](docs/DECISIONS.md)：决策记录
- [`docs/lessons.md`](docs/lessons.md)：踩过的坑
- [`docs/MODELS.md`](docs/MODELS.md)：模型名规则（只写完整 ID）
- [`config.yaml`](config.yaml)：项目、Agent、角色和轮次上限配置
- [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)：换机器时用

已被取代的文档在 `docs/archive/`，只供追溯。
