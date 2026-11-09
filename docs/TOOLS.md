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
  - 左：`python3 -m dashboard.logpane --home <autoloop 数据目录>`，跟着最新一轮 Agent 的日志（Claude、Codex 的事件转成“工具/命令/说/想/完成”几行，agy 纯文本原样显示）。
  - 右上：`python3 -m dashboard --home <autoloop 数据目录> --root <AutoDev 根目录>`，看板。
  - 右下：中台自己的日志（`agent-autoloop up` 的输出）。
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

## 6. 版本化兼容工作台（2026-11-07 历史记录）

- 无费用网页：`PYTHONPATH=src python3 -m requirements --demo serve --port 8765`；真实模式去掉 --demo，传 --home <运行中中台目录>。CLI 与网页共用后端，详细操作见 docs/modules/requirements/usage.md。
- 不收费集成：`python3 tests/f_requirements_hub.py`，隔离中台 + 假 command Agent；收费试用须显式 `python3 tests/f_requirements_real.py --real --root <新的数据目录>`。
- 模块不复用会清空旧规则的 build_rules；规则带会话命名空间、tell=never，模型文本回复由后台校验落盘，不给模型确认文件写权限。
- Codex 用户 MCP 配置可能先于 enabled=false 校验失败；模块使用临时 CODEX_HOME，仅复制 provider/auth 配置，排除用户工具/钩子，见 L013。不能把请求的模型 ID 当成独立验证的实际模型。
- 手机端现有飞书能力先查全局 SYSTEM_CAPABILITY_INDEX 的 feishu-agent-bridge（autosys）；本次只新增通用内部路由，未接真实平台。

## 7. 兼容适配器飞书入口（历史部署记录）

- 已复用 autosys 现有机器人，手机发 `/需求` 获取命令；原消息白名单和 App 不变，不另起同 App 长连接。
- 后端中台 home=`~/.local/state/autodev/requirements-hub`，本机 launchd 服务 `com.autodev.requirements-hub`；旧 `/tmp/autodev-demo/home` 本次检查不可达，不依赖它。
- CLI/网页会话接手机：`PYTHONPATH=src python3 -m requirements pair ID`，飞书用一次性码绑定。平台按 message_id 去重。
- 源码在 AutoDev 的 channels.feishu / requirements.feishu 与 autosys 的 bridge.requirements_client。详细运行、停用及证据见模块 channels.md；飞书 SDK 格式以 https://open.feishu.cn/document/server-docs/im-v1/message/events/receive 为准。

## 8. 兼容网页入口（历史部署记录）

- http://127.0.0.1:8766 为真实需求工作台，launchd=com.autodev.requirements-web，当前根与独立需求中台共用飞书数据。浏览器查看不调用模型，创建/回答会调用。
- 临时演示页 8767，根 /tmp/autodev-requirements-preview，明确 --demo，不与真实会话混用。新版网页支持搜索、文档/审核/调用页签和飞书配对；设计见模块 web-design.md。

## 9. 两套需求入口的整合（2026-11-08）

- 默认统一网页 `PYTHONPATH=src python3 -m web.server` 与独立飞书 `requirements.feishu_daemon` 用 main 的 ReqSessionStore/SRS。
- 第 6～8 节描述旧版本化入口；保留作兼容，不表示当前服务仍在线，也不自动启动第二条飞书连接。兼容 CLI 仍用 `python3 -m requirements`，后端实现移至 versioned_session.py，旧导入保留。
- 整合用 `git merge-tree --write-tree origin/main HEAD` 可先只读检查冲突；原目录有并行修改时用独立 worktree，不 stash/reset 别人的工作。

## 10. 本机 Agent/模型注册表

- config.yaml 以 agent_registry 引用 config/agents.toml，角色默认值和模型能力统一在注册表登记。本机 workspace/agent-registry.toml 或 AUTODEV_AGENT_REGISTRY 指定文件整体替代它，不叠加隐藏备用模型。
- 只读检查：`PYTHONPATH=src python3 -m cockpit.registry`；角色解析加 `--role designer`；检查其他文件用 `--file PATH`，均不调用模型、不打印 Key 值。
- Ollama 仅提供无状态文本适配，不自动探测服务或下载模型，不具备流水线代码产物协议。自定义 executable 不支持 autoloop 内置适配器，直接调用路径可用。细节见注册表设计第 8 节。

## 11. 项目登记（网页与飞书共用，2026-11-08）

- 唯一写入入口：`cockpit.projects.register_project(root, name, path, *, init_git=False, expected_hash=None)`，写 `config.yaml` 的 `projects` 段（`name`、`repo`），返回 `registered`（附 `version_hash`）或 `needs_init`，失败抛 `RegistryError`。网页和飞书都只调用它，不另写规则。
- 规则：名称仅字母/数字/`-`/`_`、以字母或数字开头、最长 64 字符且不重名；路径展开 `~` 后取绝对路径，不能与已登记项目相同，已存在的必须是目录；目录不存在或不是 Git 仓库时返回 `needs_init`（目录不存在时带 `missing: true`）且不改配置、不建目录，用户明确同意后才在本地新建目录并 `git init`，全程不涉及远程；写入用 `atomic_write`，支持 `expected_hash` 乐观锁，写后回读不到新条目则恢复原文件。
- 网页：`POST /api/projects`，请求体 `{name, path, init_git, expected_hash}`；顶栏“新增项目”按钮收到 `needs_init` 时弹确认框（区分“目录不存在”与“不是 Git 仓库”两种说法），确认后带 `init_git: true` 重提。
- 飞书：`/project add <名称> <路径>`（路径须在 `allow_dirs` 白名单内）；目录不存在或非 Git 目录时回复提示，同一会话回复 `/project init yes` 才新建并初始化并登记；新建目录只限白名单内（网页端目前没有白名单，沿用现状），随后切换到该项目。待确认状态只在守护进程内存里，重启即失效，需重新发送 `add`。
- 验证范围：`tests/test_project_registry.py` 9 项临时目录测试（含目录不存在先询问、同意后本地新建、不存在目录仍先查重名与重复路径、路径是文件被拒绝）；网页 `/api/projects` 另在临时根目录上用真实 HTTP 服务实测过成功、需初始化、重名、非法名、过期哈希五种情形。飞书 `on_message` 路由与白名单分支未真机验证。

## 12. 设计机器人常驻部署（2026-11-09）

- **当前选定的部署目录：`/Users/bai/code/autodev`**。常驻服务（launchd 标签 `com.autodev.design-bot`）固定指向安装脚本所在的检出目录，用该目录下的 `.venv` 和 `config.design.toml` 运行，日志在该目录的 `logs/`。
- 安装：在部署目录里执行 `deploy/install-design-bot.sh`；卸载：`deploy/uninstall-design-bot.sh`。只动设计机器人，不碰需求机器人（`com.autodev.req-bot`）。前提是该目录已有 `.venv`（装了 `lark_oapi`）和 `config.design.toml`。
- 凭证文件 `config.design.toml` 已被 `.gitignore` 忽略，只存在于本机，权限 600；`[allow] users` 为空且未开 `discover` 时机器人拒绝启动。首次取 open_id：临时设 `discover = true`，机器人只记录发送者、不回复。
- **以后换环境或换目录部署**：脚本按自身位置确定目录，不需要改脚本内容。步骤：在旧位置执行卸载脚本 → 在新目录取得代码、建 `.venv` 并安装 `lark_oapi`、放入 `config.design.toml` → 在新目录执行安装脚本 → 同步修改本节“当前选定的部署目录”。需要同时跑多份时用环境变量 `AUTODEV_DESIGN_LABEL` 换标签，避免互相覆盖；同一应用凭证只能有一个长连接在线，否则消息会被分走。
- 已验证：长连接可建立；白名单用户发消息能收到回复（手动进程，2026-11-09）。未验证：launchd 重启后自动恢复、崩溃自动拉起。

## 13. 多工作区收敛与运行证据归档（2026-11-09）

- 背景：本机曾有 `autodev`、`autodev-merge-workbench`、`autodev-project-registry`、`autodev-rerun-luna` 四个 git worktree，均登记在 `autodev` 名下。统一以 `/Users/bai/code/autodev` 为主目录，其余待确认后用 `git worktree remove` 清理（不要直接 `rm -rf`，否则 git 里仍留着登记）。
- Luna 复跑的原始运行记录（`workspace/` 整份，115 个文件，含 `runs/R20261107-001` 与演示项目 `projects/toy` 的独立 git 仓库）已整份复制到主目录 `workspace/archive/luna-rerun-R20261107-001/`，逐文件比对与源目录一致。**没有与主目录的 `workspace/runs/` 合并**：两边都有 `R20261107-001`，但主目录那份是停在 S6 第 3 轮的另一次运行，Luna 那份是 S9 已完成的重跑，合并会互相覆盖。Luna 复跑的报告与代码提交已在 git（`docs/reports/2026-11-07-session-report-luna.md`、提交 `6b7a41e`）。
- 归档约定见 `docs/DATA_SPEC.md` 的“归档目录”。归档不入 git，删除前先确认已不需要。
