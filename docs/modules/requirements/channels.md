# 手机消息入口：通用组件与接入边界

来源：2026-11-07 用户要求手机上通过飞书或微信继续需求交流，并希望通讯能力可被后续模块复用。状态：通用组件、需求适配与飞书接线已实现；本机现有机器人已启用并连上飞书，真实手机消息验收待用户发起。

```text
飞书 / 企业微信 / 个人微信客户端
              |
  平台连接器：登录、验签、收消息、回传
              |
   通用 MessageGateway（src/channels/）
     用户白名单、重复消息去重、应用路由
              |
 RequirementsMessages / 未来其他应用适配
              |
    SessionStore（CLI 与网页同一后端）
```

已实现：`channels.MessageGateway` 接收已由平台连接器认证的 channel/actor/conversation/event_id/application/payload，按授权名单路由到登记应用；同消息同内容返回原结果，不同内容报冲突；中断结果不确定时不自动重执行。运行数据在 gitignore 的 `workspace/channels/`。

`requirements.messaging.RequirementsMessages` 将 create/list/show/reply/step/confirm/export/retry/reopen 映射到已有后端。会话绑定当前平台用户和对话，不能只靠猜测 ID 读取其他会话；确认必须是独立操作并携带当前版本/哈希，不从模型自然语言自动批准。其他应用可向 MessageGateway 注册处理函数，复用公共通讯入口，而不 import 需求业务。

最初待实际渠道连接器完成（飞书已由下节实现，微信仍待实现）：验证平台消息身份、解析文字/卡片操作、异步调用（step 会阻塞直到本轮结束）、消息长度分段和回传、配置与密钥来源、断线恢复，以及真实手机端验收。网关是内部 Python 接口，不是未经认证可公开暴露的 webhook；不得直接相信外部提供的 actor 字段。

最初只读核对的复用来源：全局 SYSTEM_CAPABILITY_INDEX 的飞书机器人条目，以及本机 `/Users/bai/code/autosys` 的 feishu-agent-bridge。该项目已有飞书长连接、白名单、消息解析及回复能力；优先考虑在其既有收消息/异步任务入口调用公共组件。此次只读其源码，未修改或重启用户已有机器人，也未读取或复制账号配置。

飞书、企业微信、个人微信并非同一接口，需确定首个渠道后才能落实接线与权限。不能把个人微信等同于企业微信机器人。此项已选择飞书，微信仍未选型；CLI/网页开发不依赖其他平台。账号接入时先查对应官方当前文档，沿用安全的本机凭证来源；不在仓库写 App Secret 或个人登录资料。

测试：`tests/test_message_gateway.py` 覆盖授权、消息去重、跨对话会话拒绝、版本确认及共享后端。未测试真实平台收发，不声称跨平台可直接上线。

## 首个实际渠道：飞书（2026-11-07 用户确认）

复用 autosys 的既有飞书长连接与白名单，新增 `/需求`、`/req` 命令，不另启动同一 App 的长连接。AutoDev 负责命令与结果格式；autosys 用受控 Python 子进程调用，JSON 经 stdin/stdout 传递，不相互 import 业务包。耗时工作用独立单线程队列，不阻塞事件回调；以 message_id 对应幂等请求，其他命令保持原路由。

命令：`/需求 新建 项目名 | 想法`、`/需求 列表`、`/需求 查看 ID`、`/需求 回复 ID | 回答`、`/需求 继续 ID`、`/需求 重试 ID`、`/需求 确认 ID 版本 哈希`、`/需求 导出 ID 版本`、`/需求 修订 ID`。新建/回复后自动推进梳理与有界审核；确认须显式版本/哈希，不把自然语言当授权。长文与导出复用飞书文件回传。

继承 cfg.allow_users，actor 来自 SDK 事件；配置默认关闭，只保存本机路径/解释器/超时，不复制 App Secret。需求正文不写普通消息日志。平台用户和对话绑定会话；CLI/网页已有需求可用本机签发的短期一次性配对码绑定，禁止猜 ID 接管。

先测试命令、权限、去重、配对、子进程和分流，再实现 AutoDev 适配、autosys 调用器/配置/daemon，分别跑全量测试。部署前核对机器人是否忙及中台连接；手机验收由用户发命令，不主动向历史群发测试消息。本轮沿用数据、安全、测试及 LLM 规范，无新增公网 API 或视觉框架选型。涉及调用器、配置模板、daemon、解析、测试和文档同步。

## 飞书交付与使用

已实现并启用现有 autosys 机器人 `/需求` 入口（2026-11-07）。无需增加飞书 App、权限或第二条 SDK 长连接，不新增公网端口。手机在现有机器人会话中发送：

```text
/需求
/需求 新建 活动报名 | 我想做一个社区活动报名网站
/需求 列表
/需求 查看 Q实际会话ID
/需求 回复 Q实际会话ID | 我的补充回答
```

新建/回复自动运行模型并回传问题、需求文档和审核结论；真实模式会花模型额度。审核通过时回复中附带可复制的完整确认命令。确认后可 `/需求 导出 ID 版本号` 下载 Markdown，或 `/需求 修订 ID` 后继续回答。所有命令也支持 /req。

从 CLI/网页已有会话接到手机：在本机执行 `PYTHONPATH=src python3 -m requirements pair ID`，5 分钟内在飞书发送返回的 `/需求 绑定 配对码`。演示会话须在同为 demo 的客户端使用，不与真实模式混用；真实机器人不会绑定演示需求。配对码只能消费一次，不应转发给别人。

本机部署：AutoLoop 独立数据目录 `~/.local/state/autodev/requirements-hub`，launchd 服务 `com.autodev.requirements-hub`；飞书仍是 `com.feishu-agent-bridge`。autosys 私有 config.toml 新增 [requirements] enabled/root/python/home/timeout/demo，原配置其他章节经语义对比未变；备份在 autosys/logs/config-backups/（gitignored）。启用前确认 AutoDev 在原有目录白名单内，没有扩大 allow.dirs，也未复制 App Secret。

验证：AutoDev 全量 257 项通过；新增飞书命令测试覆盖双模型路径、确认、导出、重复投递、白名单、跨对话拒绝、配对过期与一次性、真实子进程入口。autosys 全量 589 passed / 1 skipped；两处旧通讯工具简称断言在原始 HEAD 中同样失败，已将测试对齐当前 cc 规范名，未修改通讯业务逻辑。真实本地链路“桥接器→子进程→网关→后端→假回复器”通过；生产配置的本地“列表”调用也通过，未发飞书消息、未调模型。重载后进程更换、长连接 connected、无启动 traceback。端到端真实手机收发仍待用户发送 `/需求` 验收，不把启动成功当成手机验收通过。

源码分工：AutoDev 的 `channels.feishu`、`requirements.feishu` 和 requirements.messaging；autosys 的 `bridge.requirements_client`、配置和 daemon 分流。消息 ID 使用 SDK 的 message.message_id；事件格式参考[飞书接收消息文档](https://open.feishu.cn/document/server-docs/im-v1/message/events/receive)。接线独立于模型任务协议，后续微信只需替换平台入口与身份校验，不复制需求业务。

停用与回滚：将 autosys 私有配置 [requirements].enabled 改为 false 并在空闲时重载 `com.feishu-agent-bridge`，只停需求入口，其他命令继续；必要时使用 logs/config-backups 的私有原配置恢复。若不再使用需求中台，可 `launchctl bootout gui/$(id -u)/com.autodev.requirements-hub` 停止本次创建的独立服务；不要停止用户的其他中台。数据目录保留以便恢复。应用与配对码不包含 App Secret，原凭证无变动。
