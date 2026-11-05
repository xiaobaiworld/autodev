# 工具手册（已确定的工具和用法）

找任何功能之前先读这里。本文只记已经确认过的工具、该查的文档、跑通过的命令和踩过的坑。没有的再去别处找，查到后补回这里。

## 0. 怎么查

1. 先看本文。
2. 本文没有，看全局的 `agent/tools/SYSTEM_CAPABILITY_INDEX.md`（iCloud，机器级能力；不含 herdr、hc、autoloop）。
3. 都没有，查该工具的在线最新文档（第 1 节的链接），再用工具自带的手册核对版本是否一致：`hc --skill`、`herdr-app --skill`、`herdr-app commands`。
4. 不要用 `herdr --help` 或 `herdr pane/workspace ...`。本机的 `herdr` 是终端版 0.9.5，连的是旧服务，和桌面应用不是一个产品（L001、L011）。
5. 查到新用法或踩到坑，补进本文和 `docs/lessons.md`。

## 1. 已确定的工具

| 工具 | 管什么 | 在线文档 | 自带手册 |
| --- | --- | --- | --- |
| `herdr-app` | 桌面窗口：空间、标签页、窗格、布局 | [手册](https://github.com/herdrdev/herdr-app/blob/master/defaults/AGENTS.md)、[命令表](https://github.com/herdrdev/herdr-app/blob/master/docs/commands.md)、[布局与模块](https://github.com/herdrdev/herdr-app/blob/master/docs/mods.md) | `herdr-app commands`、`herdr-app --skill`，本机 `~/.config/herdr-app/AGENTS.md`（每次启动重写） |
| `hc`（herdr-core） | 终端的运行、读、写、等待、标签；不管布局 | [herdr.dev/core](https://herdr.dev/core/)、[仓库](https://github.com/herdrdev/herdr-core) | `hc --help`、`hc --skill`、`hc schema` |
| agent-autoloop | 中台：派活、排队、重试、租约、事实日志、卡片 | [协议](https://github.com/KKKKhazix/agent-autoloop/blob/main/docs/protocol.md)、[配置手册](https://github.com/KKKKhazix/agent-autoloop/blob/main/skills/agent-autoloop/SKILL.md) | 本机 `~/code/agent-autoloop/docs/protocol.md`（提交 `8f8e2ee`） |
| Claude、Codex、agy | 干活的 Agent | 见 `docs/MODELS.md` | 同左 |

## 2. 显示窗口（herdr-app）

三层结构：空间（space，侧边栏）、标签页（tab，顶部）、窗格（pane，标签页内的分屏）。

```sh
herdr-app do space.new --name pro2 --folder ~/code/autodev           # 新空间，自动选中
herdr-app do tab.new --name "名字" --folder ~/code/autodev           # 新标签页
herdr-app do pane.split --direction right --pane <窗格id>            # 向右或向下分屏
herdr-app ls        # 结构和各窗格的 id
herdr-app status    # 当前选中的空间、标签页、窗格，以及文件错误
herdr-app shot /tmp/x.png   # 截取窗口，用 Read 看图确认画面
```

- 命令返回新建的 `space`、`tab`、`pane`、`terminal` id。分屏时显式传 `--pane`，不依赖焦点。
- 新建后用 `hc label <t> role=xxx` 打标签，用 `hc exec hc send <t> "<命令>"` 往里发命令（原因见第 3 节）。
- 现行布局：`pro2` 空间，左主窗格、右上看板、右下中台日志。
- 没有“保存布局”命令。空间、标签页、分屏由 herdr-core 保存，关窗口不丢；关掉整个空间会结束它的终端。要重建就写脚本（待写）。
- 窗格标题栏显示的是启动它的命令，没找到给单个窗格改名的命令。
- 窗口外观是 `layouts/<名>.json`，用 `layout.clone` 复制出自己的一份再改。

## 3. 终端（hc）

```sh
hc ls ; hc get <t> ; hc read <t> --lines 20     # 读屏幕只给可见部分，要加 --lines
hc label <t> role=x ; hc kill <t> ; hc rm <t>
hc exec hc send <t> "<命令>"                     # 往 shell 窗格发命令
```

- 在 Agent 窗格（如 Claude Code）里直接 `hc send`，文本会被包成 `<hc from="…">`，zsh 解析失败。改用 `hc exec hc send`。
- `hc run --bg` 建的终端算调用者的子终端，没有窗格，界面里看不到。要窗格用 `herdr-app`。
- 被杀掉的窗格，程序恢复不了。不要 `hc kill` 用户的窗格。
- `hc wait` 对没有 Agent 状态的普通 shell 只会超时。完成判断看产物文件，不看屏幕。
- 清屏用 `clear`，`ctrl+l` 无效。

## 4. 中台（agent-autoloop）

- 位置 `~/code/agent-autoloop`，锁定提交 `8f8e2ee`，不改内核。
- 隔离运行：`AGENT_AUTOLOOP_HOME=<临时目录>`，`init --command '<命令> {prompt}' --no-service --port N`，`up`；用假的 `osascript` 拦住桌面通知。样例见 `tests/smoke_autoloop.py`。
- 命令：`emit`、`why <轮次>`、`status`、`doctor`、`check`。
- 接口：`POST /v1/events`（来源密钥）、`GET /v1/state`、`GET /v1/stream?after=N`（本人密钥，SSE）、`POST /v1/runs/<n>/cancel`。我们的封装在 `src/driver/hub.py`。
- 事件的 `subject` 只能用字母、数字和 `# . _ : / @ -`，因为它会进提示词；`summary`、`detail` 不进。
- 中台里 `failed` 不是终点，会回到 `queued` 并带 `attempts` 重试；终点是 `done`、`nothing`、`cancelled`。
- 同一来源同一事件 id 只记一次。重试一个步骤要换新 id。
- 无界面 Agent 遇到没放行的 Bash 直接拒绝，不会挂起（L009）。

## 5. 环境坑

- zsh 不会拆分变量里的命令，也不会展开变量里的通配符。要运行带参数的命令，写成脚本。
- macOS 没有 `timeout` 命令。
- `python3 -I` 会忽略 `PYTHONPATH`，跑测试不要加 `-I`。
- 模型名一律写完整 ID，别名会被 magpie 映射成别的模型（`docs/MODELS.md`）。
- 网页抓取：`WebFetch` 打不开 herdr.dev 时用 `curl` 取公开页面，只读。
