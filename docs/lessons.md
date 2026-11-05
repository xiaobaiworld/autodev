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
- E6 Claude：首次进入新目录会弹"信任此目录"，此时发提示会被当成选项，误选 "No, exit"，**窗格被关闭**（state finished、exit 1、从 `hc ls` 消失，只能由用户重新分屏）。做法：启动前先确认目录已被信任，或启动后先看屏幕再发提示。未验证 Claude 的正常退出方式。
- E6 agy：`agy -p '<提示>' --dangerously-skip-permissions` 是一次性模式，结束后自动回 shell，退出码 3 表示失败。本机报 `User location is not supported for the API use`（地区限制），所以没有验证写文件。agy 另有 `--mode accept-edits|auto|plan`、`--sandbox`。
- E7 清屏：`clear` 有效，`hc keys ctrl+l` 无效。

教训：对交互式程序发文本前，先确认它在等什么输入。窗格关闭不可由程序恢复，因此启动 Agent 的命令要先在 `/tmp` 目录试通，不要在真实窗格里试错。
