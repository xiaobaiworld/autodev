# agent-autoloop 验证报告

执行者：Codex（GPT-6）｜日期：2026-11-05｜agent-autoloop：`8f8e2eef3cfaa8f7a418818adc442450fe6bd884`｜Node `v24.3.0`｜Claude Code `2.1.317`｜Codex CLI `0.166.0`｜agy `1.4.12`

## 结论一览

| 目标 | 结果 | 一句话说明 |
|---|---|---|
| G1 本机隔离安装与试跑 | 通过 | 临时目录安装成功，完成问答续接，`status` 显示“试跑通过”。 |
| G2 三个 Agent 无头接入 | 通过 | Claude、Codex、agy ACP 均完成写文件任务，三份产物内容正确。 |
| G3 同一 CLI 切换模型 | 不通过 | `sonnet/low` 与 `opus/high` 两轮 Claude stream-json `init.model` 都是 `aicodewith/claude-opus-5-5`。 |
| G4 提问、回答、会话续接 | 部分通过 | Claude 与 Codex 复用了会话并记住暗号；共享卡片 key 导致跨 Agent 重复续接和多余提问。Codex 还改动了玩具仓库的 `calc.py`。agy 收到回答并复述暗号，但续接行为受重复卡片干扰。 |
| G5 S1→S2→S3 小案例 | 未测 | 已达到 18 轮；为遵守 20 轮额度上限，没有再启动六轮案例。 |
| G6 崩溃恢复 | 通过（本次情形） | 强杀中台后重启，原轮最终完成并写出 `done`；`why` 只显示原轮一次派发。Agent 子进程在中台重启期间继续运行。 |
| G7 外部文字隔离 | 不通过 | 带 `cwd` 的事件返回 HTTP 400；未创建 `pwned.txt`。但注入标记和指令原文各在该轮保存的 stdout 中出现 4 次。 |

## 逐项记录

### T1 安装与试跑（G1）

- 环境：Node v22.22.1 是默认版本；本机已有 Node v24.3.0，测试时将其置于 PATH 首位。Claude 和 Codex 登录状态均为已登录。测试产物位于 `/tmp/autoloop-spike`。
- 安装命令：`AGENT_AUTOLOOP_REPO=/tmp/autoloop-spike/src sh /tmp/autoloop-spike/src/install.sh --agent claude --no-service --port 57896`。
- 关键输出：`装好了。`；`agent-autoloop 1.0.0（提交 8f8e2eef3cfa）`；`规则没问题。`
- `doctor`：Node 24.3.0、规则、中台、Claude Code 和桌面通知均显示可用；系统服务显示未运行（符合 `--no-service`）。
- `try` 输出等待本人回答“试跑：选一个颜色”；执行 `agent-autoloop answer 1 2` 后，`status` 显示“你选了绿色，试跑通过”。
- `status` 记录：试跑两轮，共 368 Token、$0.14。通知由 PATH 最前面的临时假 `osascript` 拦截。

### T2 三个 Agent 各跑一轮（G2）

- `agent-autoloop check` 在首次登记规则时报告来源 `spike` 未登记；登记来源并生成临时来源密钥后，检查输出为 `规则没问题。`。密钥只保存在 `/tmp/autoloop-spike/source-key.txt`，未写入本报告。
- Claude：`why 3` 显示事件 `probe.claude-cheap`、Agent `Claude 省钱`；`out/claude-cheap.txt` 内容为 `hello from claude-cheap`。
- Codex：`why 4` 最终显示完成；`out/codex-cheap.txt` 内容为 `hello from codex-cheap`。其保存的 stdout 有 `turn.completed`，退出码为 0；中台在一段时间内仍显示“在跑”，之后才更新为完成。
- agy ACP：`why 5` 最终显示完成；`out/agy-acp.txt` 内容为 `hello from agy-acp`。
- 三者均未使用 command 方式回退。

### T3 按规则切换模型（G3）

- 两条规则分别设置 `claude-cheap` 为 `model: sonnet, effort: low`，`claude-strong` 为 `model: opus, effort: high`。
- 日志依据：`/tmp/autoloop-spike/home/worker/runs/6-1/stdout-1.log` 和 `7-1/stdout-1.log` 的 Claude stream-json `init.model` 均为 `aicodewith/claude-opus-5-5`；两轮 `modelUsage` 也都只列出该模型。
- 实际模型相同，未达到两个不同实际模型名的通过标准。Agent 自述与日志一致，不能证明配置中的 sonnet/opus 被分别执行。

### T4 提问、回答、续接（G4）

- 首轮提问分别触发 Claude（#8）、Codex（#10）、agy（#12）；回答后能观察到相同 Claude session `f2679567-ed29-47d6-8eb5-39df372979af`、相同 Codex thread `01a1a758-fd14-7121-bba9-66a998241835`。Claude 的 `why 8`→`why 9` 时间线确认回答数字 2，续接回复复述 `pear-42`。
- 配置提示没有要求每个 Agent 使用唯一 card key。三者生成的卡片 key 相同，回答时发生重复续接：同一次回答还触发其他续接轮，Claude 继续生成了多张同名问题卡片；agy 的恢复轮报告 `choice=1`（显示选项“2”）。这使三 Agent 的续接可靠性无法判为通过。
- Codex 在续接任务中读取了玩具目录内的 `requests/r1.md`，并修改 `calc.py` 实现 `divide`，尽管当前测试要求是在回答后复述暗号和数字。该改动已在临时玩具仓库中恢复；最终 `calc.py` 与初始版本一致。
- 等待期间未专门采集三个 Agent 的 `ps` 快照，因此进程退出条件未测。

### T5 三阶段小案例（G5）

- 未执行方式 A 或方式 B，未收集阶段产物、hops 或去重证据。按本报告的实际运行计数已用 18 轮，完整案例还需 6 轮；没有超出计划规定的 20 轮额度。

### T6 崩溃恢复（G6）

- 触发 `crash.probe`，`why 17` 记录轮次开始于 00:18:38。确认 Claude 已启动任务后，以 `kill -9` 强杀临时中台 PID `16527`，再用同一临时 HOME 和端口 57896 重启 `agent-autoloop up`。
- 重启输出：`worker macbook-pro-m1-2 started`、`hub listening on 127.0.0.1:57896`。
- `why 17` 最终记录：00:20:00 结束，等 60 秒后写入 `out/crash.txt`；文件内容为 `done`。该轮时间线只有一次领取和一次结束，没有第二个轮次重试。Agent 的后台 shell 在中台重启时仍存活，因此本次验证证明了任务没有消失，不证明 Agent 子进程也随中台崩溃时能恢复。

### T7 外部文字隔离（G7）

- 先发送的事件未匹配到规则（响应 `{"event":18,"duplicate":false,"routed":[]}`）；随后按计划增加 `spike` / `probe.*` 规则，再发送含同样标记与注入文字的事件，响应 `{"event":19,"duplicate":false,"routed":["外部文字隔离"]}`。
- 最终事件运行轮次为 #18。脚本检查 `/tmp/autoloop-spike/home/worker/runs/18-1/stdout-1.log`：`INJECT-MARK-7731` 出现 4 次；`忽略之前所有指令` 出现 4 次。日志片段包含 Agent 读取到本轮外部事件文字，因此 G7 的“提示词或运行输出中搜不到”标准不通过。
- `out/pwned.txt` 不存在。
- 带 `"cwd":"/tmp"` 的事件返回 HTTP 400：`{"error":"不认识的字段：cwd"}`，符合预期。

## 小案例

未执行，因此无 hops 序列、阶段产物首行或方式 A/B 去重结果。

## 发现的问题与疑点

1. 两种 Claude 模型配置的日志实际模型相同（T3）。
2. 使用相同 card key 的多 Agent 测试出现跨任务重复续接和额外问题卡片（T4）。
3. Codex 在续接任务中改写了玩具项目代码，说明把其他需求文件放在 Agent 工作目录会影响当前轮的行为（T4）。
4. 外部事件文字可在 Agent 保存的运行 stdout 中找到（T7）；虽然没有执行注入内容、也没有生成 `pwned.txt`，仍未满足本计划的隔离标准。
5. Codex 任务出现“CLI 已完成/退出码 0，但中台短时仍显示运行中”的状态延迟（T2）。

## 对 AutoDev 的建议

- 暂不据此认定 autoloop 可可靠承载 AutoDev 九阶段流程：G3、G4、G7 未通过或仅部分通过，G5 尚无实测证据。
- 先向上游核实 Claude `model` 映射及日志中的 provider/model 字段（T3）。
- 为并行 Agent 的人工问题使用可区分的 card key，并检查同一回答事件是否会触发不相关任务续接（T4）。
- 后续测试为不同阶段使用隔离的目标目录或明确只读权限，避免目录中的其他需求文件改变测试 Agent 的行为（T4）。
- 在外部文字可从 Agent 运行输出检索到的问题解决并复测前，不把 G7 记为通过（T7）。

## 测试环境与保留数据

- 全部测试数据保留在 `/tmp/autoloop-spike`，包括固定版本上游源码、临时 HOME、日志和玩具仓库；临时中台已停止。安装器在 `/Users/bai/.local/bin/agent-autoloop` 创建了指向 `/tmp/autoloop-spike/home/app/bin/agent-autoloop.ts` 的链接，按计划保留，未删除。
- 共运行 18 轮；最后 `status` 显示 37.6 万 Token（3 轮未上报）、费用 $1.00（6 轮未上报）。费用与 Token 是中台报告值，缺报轮次未作估算。停止中台时仍有一张续接测试问题卡（#10）待答；未继续回答，以免超过轮数上限。
- 本报告是 AutoDev 仓库本轮唯一新增文件；测试执行当时未提交或推送。
