# agent-autoloop 补测报告 v2（2026-11-05）

执行者：Codex（GPT-6）｜日期：2026-11-05｜agent-autoloop：`8f8e2eef3cfaa8f7a418818adc442450fe6bd884`｜Node `v24.10.0`｜Claude Code `2.1.318`｜Codex CLI `0.166.0`｜agy `1.5.0`

## 结论一览

| 目标 | 结果 | 说明 |
|---|---|---|
| G5 方式 A：外部推进 S1→S2→S3 | 通过 | 三阶段顺序完成，产物首行符合约定；直接事件 hops 都是 0；重复事件未增加轮次。 |
| G5h 跳数与熔断 | 未测 | 回执链已实测 hops 从 0 递增到 6；10 轮上限用完，未触及 8 层熔断，也未观察熔断通知。 |
| G4 提问、回答、续接 | 未测 | 达到轮数上限前未开始。 |
| G7 外部文字隔离 | 未测 | 达到轮数上限前未开始。 |
| G3 模型切换 | 未测 | 未执行 G3-0 和两模型对照。S1/S2 的配置为 sonnet/low，日志实际模型名为 `ai-code-with/claude-opus-5-5`；这不足以判断模型切换能力。 |

## 测试环境与隔离

- 测试执行时的源码 checkout 固定在提交 `8f8e2eef3cfaa8f7a418818adc442450fe6bd884`，路径为 `/tmp/autoloop-spike/src`。
- 中台使用 `AGENT_AUTOLOOP_HOME=/tmp/autoloop-spike/home`、`--no-service`、随机端口 `54698`；通知命令由 `/tmp/autoloop-spike/fakebin/osascript` 拦截。
- 测试执行时的玩具仓库位于 `/tmp/autoloop-spike/toy2`，只包含 `calc.py`、`requests/r1.md` 和测试产物。全程没有读取或打印登录凭据，没有连接真实项目或外部消息通道。
- 安装器创建了 `/Users/bai/.local/bin/agent-autoloop` 链接，目标为 `/tmp/autoloop-spike/home/app/bin/agent-autoloop.ts`；按计划保留链接。
- 收尾时将测试源码、玩具仓库、脚本、临时密钥和中台数据库移入 `/Users/bai/.Trash/autoloop-spike-v2/`；脱敏日志保留在 `/tmp/autoloop-spike/logs`。为了保持计划要求保留的命令链接有效，仅保留链接目标 `/tmp/autoloop-spike/home/app`。

## T1：G5 三阶段小案例

### 方式 A：外部推进

- `agent-autoloop check` 输出“规则没问题”。驱动脚本 `/tmp/autoloop-spike/scripts/drive.sh` 依次发送 `r1:s1`、`r1:s2`、`r1:s3`，等待相应轮次结束后检查产物。
- `why 1`、`why 2`、`why 3` 显示 S1、S2、S3 分别由 `claude-cheap`、`claude-cheap`、`codex-cheap` 完成，三条外部事件的 hops 均为 0。
- 产物首行：`runs/r1/analysis.md` 为 `结论：ACCEPT`；`runs/r1/design.md` 为 `# 设计：calc.divide`；`runs/r1/review.md` 为 `结论：PASS`。
- `calc.py` 与初始提交一致。
- 三轮完成后再次发送 `r1:s2`，响应为 `duplicate: true`；运行数仍为 3，没有额外派发。

### 方式 B：Agent 回执链

- 增加 `emits` 后从外部发出 hops=0 的 S1 事件。`why` 记录的事件 hops 依次为 `0→1→2→3→4→5→6`，每次回执发出的下一阶段事件 hops 比输入增加 1。
- 第 4 至第 10 轮均完成；总计 10 轮、运行中 0、排队 0。每轮的事件与回执摘要保存在 `/tmp/autoloop-spike/logs/evidence-summary.json`，Agent 输出保存在同目录的 `run-<轮次>-stdout-1.log` 与 `run-<轮次>-stderr-1.log`。
- 第 10 轮输入 hops=6，未记录新的后续事件。轮数上限已到，因此没有继续验证 hops=8/9 的熔断点，也没有观察到熔断通知。
- 中台汇总用量：727,437 input tokens、8,934 output tokens、费用 `$0.809296`。这是 CLI 上报汇总。

## 未执行项

G4、G7、G3 均因测试计划规定的 10 轮上限而未执行。agy 没有参与本次补测。未把这些未执行项推断为通过或失败。

## 对 AutoDev 的建议

方式 A 的证据支持将外部确定性流程串在 autoloop 上：三阶段产物、顺序和事件去重均符合预期。方式 B 的 hops 递增已观察到 6 层，但熔断未验证；G4、G7、G3 也未测，因此目前只能确认 G5 方式 A，不能据此确认九阶段流程的整体可靠性。
