# 当前状态与下一步

更新：2026-11-09。文档目录整理已完成并推送文档分支；法律工作台的需求→设计→HTML原型整合测试已完成，当前准备推送开发分支。文档入口：[docs/INDEX.md](docs/INDEX.md)；整理范围与验收：[执行记录](docs/design/2026-11-09-doc-organization-review.md#8-本轮执行范围2026-11-09)。

## 目录与工作边界

| 目录 | 用途 |
| --- | --- |
| `/Users/bai/code/autodev` | 部署检出，分支 `deploy`；两机器人服务指向这里。不要在此开发、切分支或动本机凭证/运行数据 |
| `/Users/bai/code/autodev-dev` | 开发 worktree，共用既有 `.venv`；不要在此启动机器人 |

本轮开始核对：两个检出与本地 `origin/main` 引用都是 `beb96f8`，没有重新联网确认远端。文档整理使用分支 `docs/organize-stage-contracts`，现已继续到 `feat/legal-workbench-integration`；最终提交以 Git 为准，不在本文件循环硬编码自身提交号。

开发前先读 `docs/TOOLS.md`、`docs/lessons.md` 与适用需求/设计。本轮用户已明确授权推送当前开发分支；合并main及更新部署未授权。部署目录里的未跟踪文件不处理。

## 当前实现与验证边界

- S1～S9 旧流水线已有历史真实运行证据；按阶段查 [stages](docs/stages/README.md)，数据协议查 [DATA_SPEC](docs/DATA_SPEC.md)。不把历史实跑视为本次复跑。
- 默认需求澄清模块已支持飞书/Web、SRS 定稿与交接；版本化兼容工作台独立保留。设计机器人入口仍只回固定说明，`design_view.py` 尚未接入。
- V2.1 MVP 1 的分类、规则/Schema、设计包验证与 D0 文档是独立模块，**未正式接常驻流水线/机器人；本轮独立适配已用真实设计包验证**。入口：[design-system](design-system/README.md)、[采用对照](docs/design/2026-11-09-v21-mapping.md)。
- 当前 S2/S3 仍用三份 Markdown 设计产物；D019 分级放行、V2.1 四层验证、原型交互检查和完整版本/授权协议尚未接入。
- 服务状态沿用用户交接：需求、设计两个机器人未受影响；旧 requirements-hub 仍在但已无调用者，8766 网页停用。**本轮未查询或重启服务**，实际状态需操作时另核对。
- 全量单元测试命令：`PYTHONPATH=src .venv/bin/python -m unittest discover -s tests`；本轮 456 项通过。系统解释器缺 SDK 的首轮失败及复核见整理执行记录。

## 本轮文档整理

- 补目录职责、唯一正文及按需加载规则；S2/S3 拆出 contract/standard，平台文档改为引用；增加执行资产与归档入口。
- 保留执行模板、源码、配置、固定基线、已校验 SRS 与运行路径；S4 旧稿核对为历史设计，未逐项复跑旧实验。
- 当前清点、迁移/保留理由与缺口见 [清单](docs/design/2026-11-09-doc-inventory.md)。最终检查与提交状态见 [执行记录](docs/design/2026-11-09-doc-organization-review.md)。

## 当前：法律工作台整合测试（2026-11-10）

用户已提供五类法律业务，授权按默认值自动完成需求文档、设计包与HTML原型，不再等待能力清单的逐项决定。本轮独立项目：`/Users/bai/code/legal-agent-workbench-mvp`；开发分支 `feat/legal-workbench-integration`，不覆盖 personagent 或修改部署目录。

- 入口与范围：[整合设计](docs/design/2026-11-09-legal-workbench-integration.md)。
- 已完成：真实需求模型定稿并通过SRS校验、项目登记、handoff/S1基线、D3/15规则分类、HTML原型及17项验收浏览器回归。
- 已完成：D3结构化包、15/15规则、12任务、5严格Schema/OpenAPI、3专项最终PASS、17AC浏览器验证；Controller设计流水线done，固定交付在目标docs/design/v1.0.0。见[最终报告](docs/reports/2026-11-10-legal-workbench-integration.md)。
- 已修复并回归：Claude argv将前导 `---` 提示词误当选项的问题；全量462项测试通过；当前集成入口另覆盖审查合并不能隐藏高风险。
- 原型外部服务/法源/Word为标注的模拟；生产接入尚未实现。失败的模型调用与重试保留在独立项目workspace。

## 下一步

用户审阅法律工作台原型后，按目标项目handoff的12任务开发；或先把本轮集成适配纳入设计模块正式入口。两者尚未决定，不默认升级常驻机器人。当前推送只针对feat/legal-workbench-integration，保留部署目录和两个服务。

## 背景：首个项目 personagent

用户希望用 AutoDev 的需求分析和设计模块，推进同级 `personagent` 的 Agent 专业人士工作台。先评估现有能力、模板与缺口，给出默认方案和影响清单供用户决定，再确定实施清单并完成。该评估因本轮文档整理而暂缓，**尚未完成、没有确认实施范围**。

需结合真实目标项目规则与资料，不能把“律师、会计等专业人士”的产品方向自动扩展为一次实现全部行业，也不能把 AutoDev 平台规则整体注入目标项目。

## 设计接入仍需明确的事项

1. 设计 Agent 对原型/结构化文件的受控写入目录和权限；不放宽到目标项目产品代码。
2. 新旧并存的流水线类型名；旧运行与旧模板的影响清单。原计划用假 Agent 验证接入，不花额度。
3. 关键特征从需求文本独立核对；当前验证器信任 plan 自述，特征漏报不能被识别。
4. D2 人工确认默认值、模型建议阈值及冲突处理；依据采用对照，不因文档整理代为定案。
5. 部署/设备类规则按真实需求补，不预设；MVP 2 原型闭环、MVP 3 高风险优化按主规范后续推进。

## 其他遗留事项与追溯

机器人旧会话 ID 失效自动恢复、职责范围守卫、设计只读指令接入、旧中台停用与统一 Web 常驻仍未完成；不并入本轮文档任务。先前对话涉及过的凭证重置事项尚无完成证据，凭证只留本机、不写入 Git。

- [整理前完整 next 快照](docs/archive/2026-11-09-next-before-stage-docs.md)：包含所有移出的历史、旧目标与运行证据，原样保留。
- [更早快照](docs/archive/2026-11-09-next-before-reorg.md)：前轮整理前的历史。
- 决策到 D026，经验到 L027；工具先查手册，不用 `herdr --help`。macOS 无 `timeout`；测试不要用忽略 PYTHONPATH 的 `python3 -I`。
