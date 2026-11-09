# 需求工作台验证记录

> 2026-11-09 旧飞书桥适配层（`src/channels/`、`requirements.feishu`、`requirements.messaging`）与配对码功能已移除，见 D024；下文涉及它们的内容仅作历史证据，对应命令和接口已不存在。

> 2026-11-08 整合说明：本文件对应版本化兼容工作台（`requirements.versioned_session.SessionStore`），不作为默认统一网页、`ReqSessionStore` 或九章节 SRS 的契约。两套会话不自动同步；端口、launchd 与真实试用记录是当时证据，本次未复核运行服务。入口与边界见 [模块说明](README.md)。

日期：2026-11-07。分支：feat/requirements-workbench。对应需求：v0.9（保留已确认 v0.8，并补入本期网页）。结论：独立后端、CLI、本机网页以及真实双模型梳理/审核已可运行；消息平台连接尚未交付。

## 自动验证

- 全量 unittest：250 项通过（含本次 38 项新测试）；覆盖本地契约、来源引用、清单、版本哈希、双模型返工与上限、业务决定转人工、幂等、重复确认、旧基线导出、错误/超时/中断/重启、符号链接拒绝、忙碌冲突、CLI/API 一致性、HTTP 跨站防护，以及消息路由的授权/去重/会话绑定。
- `python3 tests/f_requirements_hub.py`：通过。真实隔离 AutoLoop + 假 command Agent，验证规则合并不覆盖既有规则、派发、事实流关联和原始回复。
- `python3 tests/f2_pipeline.py --build`：通过。既有流水线跑到 S9；覆盖 S5 失败、S6 返工、S7U 失败后的修复及最终本地标签。假 Agent，不花模型额度。
- `node --check src/requirements/static/app.js` 与 `git diff --check`：通过。
- 临时 Codex 配置测试证明 MCP、hooks 不复制，连接配置保留，匿名测试 auth 文件权限 0600；CLI 构造使用无工具/只读限制。此项及真实无工具调用不能证明任意第三方 CLI 无漏洞。

## 浏览器实际操作

宿主 CUA 浏览器连接不可用；使用本机已有 gstack browse，在补齐它缺少的官方 Playwright headless 浏览器后完成验收。

入口 `http://127.0.0.1:8765`，数据根 `/tmp/autodev-requirements-preview`，显式演示模式，会话 `Q50534ff712c5`：

1. 点击新需求，填写匿名项目与一个想法。
2. 收到模拟澄清问题，确认按钮禁用。
3. 在页面填写目标/用户/功能/范围/约束/验收六项并提交。
4. 草稿从 v1 变成 v2，模拟审核通过，确认按钮开放。
5. 点击确认，页面显示“已确认完成 · v2”，可开启新修订和下载已确认版本。
6. 点击下载；另外 HTTP 读回验证 200、attachment 文件名与实际 Markdown 等于该版本正文。控制台无消息。
7. 查看 1280 桌面与 375 手机宽度截图，无横向溢出，交互及文档均可阅读。

截图位于本机临时文件 `/tmp/requirements-workbench-desktop.png`、`/tmp/requirements-workbench-tablet.png`、`/tmp/requirements-workbench-mobile.png`，仅作当次证据，重启清理后不保证保留。浏览器内容明确显示“无费用演示”；此项不冒充真实模型审核。

## 真实双模型匿名案例

显式运行：`python3 tests/f_requirements_real.py --real --root /tmp/requirements-real-20261107-v1`。独立中台由脚本创建并在结束时停止，不操作用户现有中台或 Herdr 空间。

- 会话：`Q9c3406e4f917`。
- 输入：匿名社区活动报名，已给出重复昵称、空昵称、存储、范围与验收要求。
- 梳理：请求配置 `ai-code-with/claude-opus-5-5`、low；succeeded，13345ms。
- 审核：请求配置 `gpt-6-sol`、low；succeeded，7240ms。
- 结果：需求 v1，独立审核 PASS，结构缺项为空，状态 waiting-human / confirmation。
- 整包哈希：`f8885eaa9d6c0b7837b2a55036d3a35a452306486ade3b453b9ab178564df115`。
- 未自动人工确认。最终确认和导出路径已由匿名演示、API/CLI/HTTP 测试验证，真实案例保留等用户状态。
- 原始输入、回复、计时、需求版本、审核和汇总在该数据根的 workspace/requirements/ 与 result.json。临时路径不可当作永久归档。

模型栏只记录请求配置；本模块依用户要求不解析底层 CLI 日志，不能将配置写成独立验证的实际响应模型或 token 成本。测试成功证明当前两个 CLI 能按该参数返回有效结果，不证明所有账号与环境都可用。

## 反向检查与限制

本次未调用额外审查子 Agent；对过期审核、模型伪造确认、无限往返、重复消息、重启重复采纳、规则覆盖、目录越界及跨站写请求逐项写测试并反查实际代码。

仍有边界：本机单用户；完整历史按输入快照传递，超大上下文明确报错而不自动摘要；通用清单仍需真实需求打磨；只做一次真实匿名案例，未实测真实模型返工分支的稳定性；若上游接受派发但进程中断且无法核对结果，不能保证严格恰好一次外部调用，必须明确恢复或重试。

手机端目前仅有通用 MessageGateway 与需求适配，不含平台验签、长连接登录或真实发送。飞书已有 autosys 项目可复用，但本次没有修改或重启它；微信的个人号/企业号需先区分。未公开部署或开放远程监听。

## 飞书增量验证（2026-11-07）

新增 7 项飞书测试后，AutoDev 全量 257 项通过；另对 CLI 配对入口运行模块回归 42 项通过。飞书桥接项目 589 项通过、1 项跳过。真实本地子进程桥接和生产配置的本地列表预检通过，均使用假回复器、不发送平台消息。独立中台健康；现有飞书机器人已重载并连接 WebSocket，无启动 traceback。详细边界和操作见已删除的 channels.md（旧桥已移除，D024）；真实手机指令及文件回传待用户验收。历史的“平台未接”描述是上一步状态，由本节取代。

## 网页工作台第二版（2026-11-07）

设计见 web-design.md。新增同源 POST /api/sessions/ID/pair 及回归测试；全量 258 项通过，JS 语法与差异格式检查通过。界面改为搜索/列表、交流、章节文档，审核与调用独立页签；修复跨会话请求过期覆盖及等待状态，支持网页飞书配对，保留纯文本 DOM 输出。

浏览器在 8767 演示页实际新建“网页新版验收”，补充六项信息，看到版本 v2 审核后确认完成；查看审核页签和配对弹窗，控制台无消息。桌面和手机截图 /tmp/requirements-web-v2-desktop.png、/tmp/requirements-web-v2-mobile.png 已查看。真实 8766 服务启动并只读检查 200、demo=false、模型连接配置有效；本轮不额外调用真实模型。页面与模型完整后端链路沿用上文已验证能力。

## main 整合验证（2026-11-08）

以 main v0.3.3 为准解决 11 个同名文件冲突。ReqSessionStore 与默认 SRS/统一网页/飞书/S2 交接保留，版本化后端移至 versioned_session.py，原 session 与顶层导入兼容。297 项 unittest 通过，包含 main 和旧分支原测试，以及两套存储同根共存、重启恢复和双向不互写测试。隔离 AutoLoop 假 Agent 集成通过；pipeline/build 假 Agent 完整 S1～S9 回归通过，覆盖 S5/S6/S7U 返工和人工关口，证据目录 `/var/folders/7h/pjw56r4n4fs4ng3_n9zdw4j80000gn/T/autoloop-f2-znbrdz06`（临时目录）。JS 语法检查通过。

本轮不额外调用收费模型、不发送真实飞书消息、不部署或重启服务；未重新做浏览器视觉验收，网页代码沿用原分支。两套格式无自动转换，版本化确认结果不自动进入九章节 SRS/S2。原工作区未提交的阶段机器人文档与 requests/ 不在此次整合内。
