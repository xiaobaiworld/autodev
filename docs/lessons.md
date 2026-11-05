# lessons.md

已踩过的坑和验证过的做法。开始新功能或做技术决策前先扫一遍。

## L001 Herdr 的真实接口是 `hc`，不是 `herdr agent/pane`（2026-11-05）

- 坑：设计文档按 `herdr 0.9.5` 的帮助文本写了 `herdr agent start/prompt/wait/read`。桌面应用实际由 `herdr-core` 管理，socket 在 `~/.local/state/herdr-core/default/default.sock`；`herdr` 命令默认连 `~/.config/herdr/herdr.sock`，报 `server_not_running`。设置 `HERDR_CLIENT_SOCKET_PATH` 也没用。
- 做法：用 `hc`（`hc ls`、`run --bg`、`send`、`wait`、`read`、`kill`、`rm`、`get`）。实测记录见设计文档 3.2。
- 教训：只看帮助文本不算验证。接口要真跑一轮才能写进设计。
- 注意：macOS 没有 `timeout` 命令，等待超时用 `hc wait --timeout` 或工具自带的超时。

## L002 测试计划不要让各项互相污染（2026-11-05）

来自 autoloop 验证报告（`docs/spikes/2026-11-04-autoloop-test-report.md`）。

- 坑 1：关键项（三阶段小案例 G5）排在最后，被前面的项耗尽额度，没有任何数据。
- 坑 2：三个 Agent 共用同一目录、同一提示词和同一卡片标题，卡片 key 由标题算出所以相同，回答时触发跨任务重复续接；目录里的 `requests/r1.md` 还让 Codex 去改了 `calc.py`。
- 坑 3：G7 的通过标准写成"运行输出里搜不到注入文字"。上游设计是事件详情放进 `context.json`，Agent 读了文件，输出里自然搜得到。该看的是"有没有照做"和"`cwd` 等控制字段是否被拒收"，这两项都通过。
- 坑 4：测试机的 Claude 走第三方网关，别名 sonnet 和 opus 都被映射成同一个模型，G3 不能据此判断 autoloop 有问题。
- 做法：最关键的项先跑；每个被测对象用独立目录和只读权限；卡片 key 各自唯一；通过标准要区分"进入提示词"和"被读到"；要验证模型切换，先确认账号是直连。

## L003 `hc` 只能证明"干完了"，答案要写文件（2026-11-05）

- `hc read` 返回整屏文字，回复可能滚出可见区域（测试里新开的 Codex 回复读到的是空白）。
- 做法：完成判断用 `hc wait` 的状态加产物文件，不解析屏幕。与设计文档 3.3 的 `done.json` 约定一致。

## L004 驾驶舱 P0 实验结论（2026-11-05）

做在 `/tmp/cockpit-spike/`，假 Agent 脚本加真 Codex 一轮，Claude 与 agy 各试一轮。

- E1 认领：`hc ls` 带 `where`（如 `pro1 / 1`），同空间可筛出 4 块。主控自己的地址用 `hc ls` 里前台进程是 claude 的那块判断，环境变量里没有终端 ID。
- E2 标签：`hc label <t> role=xxx` 可用，`hc get` 能读到，但 **`hc ls` 不带标签**，认领要逐个 `hc get`。重启 `hc` 服务后是否保留：未测。
- E3 普通 shell 窗格：`hc send` 发命令可用；**`hc wait` 对没有 Agent 状态的进程只会超时**，不能用来等假脚本结束。完成判断用 `done.json`，是否回到 shell 看 `hc get` 的 `foreground.name`。
- E4 退出：假 Agent 收到 `exit` 后前台回到 `zsh`，`hc get` 的 `status` 为 null，可靠。
- E5 Codex：`codex --sandbox workspace-write --ask-for-approval never` 可写文件；`hc wait` 返回 `status: done`，`out.txt` 正确。**`hc send "/exit"` 无效**，文本会被包成 `<hc from=...>` 提示当普通消息；`hc keys <t> ctrl+c ctrl+c` 能退出，窗格回到 zsh。
- E6 Claude：首次进入新目录会弹"信任此目录"，此时发提示会被当成选项，误选 "No, exit"，**窗格被关闭**（state finished、exit 1、从 `hc ls` 消失，只能由用户重新分屏）。做法：启动前先确认目录已被信任，或启动后先看屏幕再发提示。复测（新窗格 t1b）：窗格矮时只显示最后一个选项，先 `hc read <t> --lines 20` 看全，用 `hc keys <t> up` 移到 "Yes, I trust this folder" 再 `enter`，之后发提示正常，写出 out.txt，`hc wait` 返回 done。退出用 `hc keys <t> ctrl+c ctrl+c` 有效，前台回到 zsh。启动参数 `claude --permission-mode acceptEdits --model sonnet` 可用（横幅显示的模型名与 `--model` 不一致，疑似网关映射，未深究）。
- E6 agy：`agy -p '<提示>' --dangerously-skip-permissions` 是一次性模式，结束后自动回 shell，退出码 3 表示失败。本机报 `User location is not supported for the API use`（地区限制），所以没有验证写文件。agy 另有 `--mode accept-edits|auto|plan`、`--sandbox`。
- E7 清屏：`clear` 有效，`hc keys ctrl+l` 无效。

教训：对交互式程序发文本前，先确认它在等什么输入。窗格关闭不可由程序恢复，因此启动 Agent 的命令要先在 `/tmp` 目录试通，不要在真实窗格里试错。

## L005 模型选择与 magpie 映射（2026-11-05）

本机所有 Agent 经 magpie 网关（`127.0.0.1:3425`），模型名被映射，和标准名不一致。

- 坑 1：`~/.claude/settings.json` 里 `ANTHROPIC_DEFAULT_SONNET_MODEL` 指向 `ai-code-with/claude-opus-5-5`，所以 `claude --model sonnet` 实际是 Opus（L004 里"横幅模型名不一致"即此因）。别名 sonnet、opus 不可靠。
- 做法：启动时写完整 ID。Claude：`--model ai-code-with/claude-sonnet-5-5`，横幅显示 Sonnet 5.5，已验证。可用 ID 见 `~/.claude/settings.json` 的 `CLAUDE_CODE_MODEL_CAPABILITIES`。
- Codex：`-m gpt-6-sol -c model_reasoning_effort=low` 生效，横幅显示 `GPT-6-Sol low`。可用模型与强度档位见 `~/.codex/magpie-desktop-models.json`。
- agy：`agy models` 列出可选 ID，`agy --model claude-sonnet-5-5-low -p '...' --dangerously-skip-permissions` 成功退出码 0。L004 的地区限制只出现在默认模型上，指定模型后可用。
- `magpie ls` 看各 Agent 当前默认模型；`magpie <agent> <model>` 会改全局默认，调度程序不要用它，只用启动参数，避免影响用户日常使用。
- 坑 2：在 Agent 窗格（如主控 t14）里 `hc send` 到已跑过 Agent 的 shell 窗格（`reported=true`），文本会被包成 `<hc from="t14">…</hc>`，zsh 解析失败。做法：用 `hc exec hc send <t> "<命令>"` 发送，文本不被包装。已在 t18、t1b 验证。主控程序若不是 Agent 进程，需另行确认是否也会包装。
- 规则已整理成 `docs/MODELS.md`（改 `config.yaml` 的 `agents`、写启动命令前必读）；本条只记踩坑过程。

## L006 autoloop v2 补测结论（2026-11-05）

来自 `docs/spikes/2026-11-05-autoloop-test-report-v2.md`（另一个 Agent 执行，autoloop 提交 `8f8e2ee`）。

- 确认：G5 方式 A（外部推进 S1→S2→S3）通过，产物首行符合约定，重复事件被去重（`duplicate: true`，不增加轮次）。这支持"确定性流程在外、autoloop 当队列"的用法。
- 未确认：回执链 hops 观察到 0→6，熔断（8 层）没触到；G3、G4、G7 因 10 轮上限没跑。未测不等于通过，不能据此确认九阶段整体可靠。
- 再次踩到 L005 的坑：配置 sonnet/low，日志里实际模型是 `ai-code-with/claude-opus-5-5`，G3 仍无法判断。补测前先用完整模型 ID，且先做 G3-0 确认两个模型确实不同。
- 坑：把关键项放在方式 B 回执链之后，轮数被链条耗尽，重蹈 L002 坑 1。做法：每项独立计数，或先跑关键项，回执链单独占一次预算。
- 残留：`~/.local/bin/agent-autoloop` 软链接指向 `/tmp/autoloop-spike/home/app/...`，`/tmp` 重启后会失效；测试源码和数据库在 `~/.Trash/autoloop-spike-v2/`。
- 费用参考：10 轮约 727k input tokens、$0.81。

## L007 P3 一次 Agent 调用实测（2026-11-05）

- 判断"回到 shell"不能看前台进程名：`bash fake-agent.sh` 的前台名也是 `bash`，和 shell 同名。做法：比较 `hc get` 里前台 `pid` 与窗格 `pid`，相等才算回到 shell（`src/cockpit/invoke.py` 的 `at_shell`）。
- 实测：假 Agent 约 11 秒；真 Codex（`-m gpt-6-sol -c model_reasoning_effort=low --sandbox workspace-write --ask-for-approval never`）25.4 秒，写出 `out.txt` 与 `done.json`，`ctrl+c ctrl+c` 退出后窗格回到 shell。
- 发送统一走 `hc exec hc send`（L005）。主控是普通进程时是否还需要 exec 没测，保持 exec 无副作用。
- 提示词里要明确让 Agent 写 `done.json`，否则只能等到超时。

## L008 P4 真实跑 S1 到 S3 的坑，以及主控需要巡检（2026-11-05）

- 坑 1：Claude 只能读自己的工作目录。`input.md` 引用的需求和上阶段产物在目录外，会弹读取确认，窗格空等了约 6 分钟，主控毫无察觉。做法：启动加 `--add-dir <workspace>`（`launch_cmd` 的 `add_dirs`）。
- 坑 2：`--permission-mode acceptEdits` 只放行文件编辑，不放行 Bash。Claude 用 shell 写 `done.json` 会再弹确认。做法：`input.md` 要求一律用文件写入工具；弹窗仍可能出现，所以不能只靠提示词。
- 坑 3：旧的退出逻辑在 10 秒内没回到 shell 就 `hc kill`。t1b 在 S1 完成的同一秒被杀（`reason: killed`，时间与旧逻辑吻合，推断是它杀的），S2 启动时窗格已不存在，三次重试都立刻 `pane_lost`，转 needs-human。被杀的窗格程序恢复不了，只能由用户重新分屏。做法：退出改为逐档升级（配置的退出键、`esc` 加退出键、`ctrl+d`），仍退不出就报 `agent_blocked`，不 kill。窗格丢失不再重试，直接转 needs-human。
- 坑 4：续跑时 `started_at`、`deadline_at` 没有刷新，状态区用时和超时时刻按第一次启动算。尚未修。

### 原则：主控要有巡检，卡住由专门的处理者接手（用户 2026-11-05 提出）

- 主控除了推进步骤，还要每隔一段时间检查各窗格的运行状态：`hc get` 的 `status.state`（blocked、working、idle）、距上次进展多久、`started_at` 距今多久。
- 长时间无进展（卡在权限确认、对话框、无输出）时，不由主流程硬等，交给一个专门处理这类事的角色，建议叫 watchdog。
- 处理原则：能在不影响整体运行的前提下继续往下走，就直接处理并继续（例如放行只写步骤目录的 `done.json` 之类确认）；会影响其他部分、涉及删除数据、凭证、权限、对外发送、花钱的，不自动放行，转 needs-human。
- 本次的三次卡住（读取确认、Bash 确认、窗格被杀）都是巡检能提前发现的。Monitor 靠我手动盯，不能当成产品功能。
- 还没做，详见 `docs/design/2026-11-05-cockpit.md` 新增的 2.6 节。

## L009 F1：autoloop 无界面跑真实 Agent（2026-11-05）

- 无界面模式下没有"卡住等弹窗"：Claude `-p --permission-mode acceptEdits` 遇到不放行的 Bash 直接拒绝（日志 `permission_denials`），约 11 秒结束。L008 的两次卡住是交互界面特有的，这是换底座的实证依据之一。只测了两条命令，不能推广到所有 Bash。
- 完整模型 ID 下，Claude 的 opus 与 sonnet 能得到不同的实际模型名；判定模型靠 stream-json 开头的 `"model"` 字段，Codex `exec --json` 和 agy 没有，只能记"未验证"。
- 验证脚本自己也会错：读错文件、把 `"usage": null` 当成有用量。判定逻辑要先用已知结果跑一遍，不能默认正确。
- 运行目录的命名是 `<轮次>-<尝试>`（`home/worker/runs/1-1/`），完成后 `entry.json` 不在，日志在 `stdout-<n>.log`。
- 无界面的 Codex 读了本机全局规范文件，如需隔离要另行设计（见 F1 报告）。

## L010 F2：驱动放在 autoloop 外面（2026-11-05）

- 中台对失败的轮次不是终态：`retryLater` 把它放回 `queued` 并记 `attempts`、`error`，退避从 5 分钟翻倍到 60 分钟，连续 10 次后才 `cancelled`。判终点要分清 `done/nothing/cancelled`（终点）和 `queued` 带 `attempts`（重试中），不能看到 `failed` 就当结束。
- 同一来源同一事件 id 只记一次。驱动重试一个步骤要换新 id，否则拿不到新的一轮。
- 事件的 `subject` 只允许字母数字和 `# . _ : / @ -`，会进提示词；`summary`、`detail` 不进。所以用 subject 传步骤目录路径，不传任何自由文字。
- `/v1/stream` 的事实里能拼出"事件 → 轮次 → 状态"（`events`、`run_events`、`runs` 三张表），驱动不需要轮询 `why`。
- macOS 没有 `timeout`；zsh 不会展开变量里的通配符、也不拆分变量里的命令；`python3 -I` 会忽略 `PYTHONPATH`。这些在本轮各撞过一次。
- 用假 Agent（`tests/fake_stage_agent.py`）加真实中台，可以零成本测流转、轮次上限这类确定性逻辑，真实 Agent 只留给"能不能干活"的检验。
