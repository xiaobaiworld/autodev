# 手机消息入口：通用组件与接入边界

来源：2026-11-07 用户要求手机上通过飞书或微信继续需求交流，并希望通讯能力可被后续模块复用。状态：本地通用组件及需求应用适配已实现，平台真实接线待选渠道；不是已上线机器人。

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

待实际渠道连接器完成：验证平台消息身份、解析文字/卡片操作、异步调用（step 会阻塞直到本轮结束）、消息长度分段和回传、配置与密钥来源、断线恢复，以及真实手机端验收。网关是内部 Python 接口，不是未经认证可公开暴露的 webhook；不得直接相信外部提供的 actor 字段。

已核对的复用来源：全局 SYSTEM_CAPABILITY_INDEX 的飞书机器人条目，以及本机 `/Users/bai/code/autosys` 的 feishu-agent-bridge。该项目已有飞书长连接、白名单、消息解析及回复能力；优先考虑在其既有收消息/异步任务入口调用公共组件。此次只读其源码，未修改或重启用户已有机器人，也未读取或复制账号配置。

飞书、企业微信、个人微信并非同一接口，需确定首个渠道后才能落实接线与权限。不能把个人微信等同于企业微信机器人。此项待用户选择，CLI/网页开发不依赖该选择。账号接入时先查对应官方当前文档，沿用安全的本机凭证来源；不在仓库写 App Secret 或个人登录资料。

测试：`tests/test_message_gateway.py` 覆盖授权、消息去重、跨对话会话拒绝、版本确认及共享后端。未测试真实平台收发，不声称跨平台可直接上线。
