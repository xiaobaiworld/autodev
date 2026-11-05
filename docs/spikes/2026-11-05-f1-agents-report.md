# F1 报告：agent-autoloop 上真实 Agent 无界面各跑一轮（2026-11-05）

脚本：`tests/f1_agents.py`。上游提交 `8f8e2ee`，临时数据目录，桌面通知被拦截。任务是在临时目录写 `out.txt`，强度最低。判定只看文件、日志和 `why`，不信 Agent 自述。

| Agent | 正常结束 | 文件内容 | 实际模型名 | 用量记录 |
| --- | --- | --- | --- | --- |
| claude-opus（`ai-code-with/claude-opus-5-5`） | 通过 | 通过 | 通过 | 有，约 $0.081 |
| claude-sonnet（`ai-code-with/claude-sonnet-5-5`） | 通过 | 通过 | 通过 | 有，约 $0.040 |
| codex（`gpt-6-sol`，low） | 通过 | 通过 | 未验证 | 有，input 90699、output 441 |
| agy（`claude-sonnet-5-5-low`，走 `command`） | 通过 | 通过 | 未验证 | 无 |

- 两个不同的 Claude 完整 ID 得到两个不同的实际模型名（日志里 `claude-opus-5-5` 与 `claude-sonnet-5-5`），magpie 别名问题在完整 ID 下不再出现。这是 Claude 这一对的对照，Codex 和 agy 没有对照。
- Codex 的 `exec --json` 事件里没有模型字段，实际模型无法从日志确认。agy 的输出是纯文本，同样确认不了，也没有用量。
- 权限探针（Claude，`acceptEdits`）：
  - `date > probe.txt` 被执行了，文件存在。
  - 带命令替换的 `printf ... "$(date +%Y)" > probe.json` 被拒绝，日志 `permission_denials` 有这一条，约 11 秒正常结束，没有挂起。
  - 没有测其他类型的命令，不能据此说 Bash 一律被拒。
- 每次探针花费约 $0.04，四个 Agent 加探针一次完整运行合计估计不到 $0.3（按各轮上报的费用相加，Codex 和 agy 没有费用）。

## 发现的问题

- Codex 的 stderr 有一条 `failed to connect to Responses WebSocket` 错误，这一轮仍然成功，原因没有查。
- 日志里 Codex 执行过 `cat` 读取 iCloud 下的路径，看起来是在读全局开发规范。我没有展开看内容，所以只能说它读了本机的全局规则文件，这意味着无界面的 Codex 会受到你全局规范的影响，要不要隔离留待决定。
- 脚本自身两处错误已修：实际模型名原来读错了文件（`entry.json` 完成后不存在，运行目录名就是 `<轮次>-<尝试>`），用量检测会把 `"usage": null` 误判为"有"。

## 结论与没做的

- F1 的五条标准里，Claude 两个 Agent 全部满足，Codex 和 agy 各有一项"未验证"。我不把"未验证"算作通过。
- 没测：Claude 的 `-p` 在需要批准的各类操作下的行为（只测了两条命令）；超时被强杀；agy 的权限（用了 `--dangerously-skip-permissions`，该测试目录是临时目录，任务无害）。
- 下一步 F2 不依赖这几项，但 Codex 实际模型确认要在 F2 前后补一个办法，例如在 `command` 插件里自己打印模型，或在规则里固定模型后读 `~/.codex` 的会话记录。
