# next.md

更新：2026-11-06 ｜ 阶段：以 agent-autoloop 为地基的集成（F0 到 F2 完成，F3 进行中）

## 恢复上下文时先读

1. 本文件
2. `docs/design/2026-11-05-autoloop-foundation.md`：当前主线方案（F0 到 F6 步骤、结构、待决）
3. `docs/DECISIONS.md`：D001 到 D014（D014 是用 autoloop 做地基）
4. `docs/lessons.md`：L001 到 L011，开始新功能前先扫一遍
5. `docs/MODELS.md`：模型名只写完整 ID
6. `docs/design/2026-11-02-autodev-design.md`：流程设计（第 3.2、3.3、5 节已被地基方案部分取代，见各节顶部说明）
7. `docs/DATA_SPEC.md`、`config.yaml`
8. 全局规范：`~/Library/Mobile Documents/com~apple~CloudDocs/agent/coding/AI编程全局规范/GLOBAL_DEV_WORKFLOW.md`
9. 换机器时另读 `AGENT_HANDOFF.md`

## 当前状态

- 地基：agent-autoloop 检出在 `~/code/agent-autoloop`，锁定提交 `8f8e2ee`。中台管派活、排队、重试、租约、事实日志、卡片；Agent 以无界面进程运行（Claude `-p`、Codex `exec`、agy `-p`）。
- 我们的部分放在中台外面：`src/driver/` 向中台发事件、读事实流；`src/cockpit/pipeline.py`、`controller.py`、`store.py` 管阶段、轮次上限、厂商不同检查、产物校验与状态落盘。
- 已验证：F0 冒烟（`tests/smoke_autoloop.py`）；F1 三个 Agent 各跑一轮；F2 真实 Agent 跑通 S1 到 S3（Opus、Opus、Codex，约 157 秒），REWORK 轮次上限在真实中台上验证。
- F3 界面：`src/dashboard/` 命令行看板读中台 `/v1/state` 与 `state.json`；在 Herdr 桌面应用的 `pro2` 空间里用 `herdr-app` 建了三格布局（左主窗格、右上看板、右下日志）。看板还没接真实流水线。
- 测试：111 个单元测试通过（`PYTHONPATH=src python3 -m unittest discover -s tests`）。

## 下一步

1. F3：把看板和日志窗格接到真实 S1 到 S3 流水线，验证真实 Agent 运行时日志是否实时滚动（现在只用假 Agent 验证过）；Web 界面后做。主窗格已定为显示当前步骤的日志（`src/dashboard/logpane.py`）。
2. 写 `pro2` 布局重建脚本（用户问过“能否保存”，桌面应用没有保存命令，建议用脚本重建）。
3. F4 模板：角色模板与规则从一处生成。
4. F5 崩溃与卡住：强杀中台、强杀 worker、Agent 超时、中台重试在真实环境触发。
5. F6 清理：移除不再需要的窗格驱动代码（`src/cockpit/` 的 `claim.py`、`invoke.py`、`config.py`、`main.py`、`status.py` 中不再用的部分），回写设计文档第 3、5、9 节。
6. 未验证项：agy 的实际模型名与用量；真实审查者给出 REWORK 并回应意见；强度参数在 Claude 启动参数里的写法；`/v1/stream` 从序号 0 重放在历史很大时的开销。

## 仍然开放的问题（来自早期设计，与地基无关）

- 目标项目 personagent 目前没有可运行的产品代码，S7 发布候选和 S8 验收的具体做法、`config.yaml` 的 `checks` 都还定不了。
- AutoDev 暂不含 GitHub PR，与 personagent 要求 Issue、TASK、PR 的规则需先协调。
- 设计文档第 8 节与第 13 节对 S7 “只打标签还是部署”表述不一致。
- “需求变更”视图对比原文、结构化字段还是两者，未定。
- 需求分析的审核角色、结论协议和轮次上限待设计（D013）。
- 跨机器 `hc --on homemac` 与 `keep` 丢失检测未测；autoloop 的 G4 提问续接、G7 外部文字隔离、熔断也未在我们的集成里测过。

## 已归档（不再维护，保留追溯）

`docs/archive/`：驾驶舱设计与开发计划、autoloop 测试计划 v1 与 v2、空的 `goal.md` 模板。
