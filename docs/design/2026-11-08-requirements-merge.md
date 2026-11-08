# 需求工作台分支整合

## 已确认范围

2026-11-08 用户确认以 main v0.3.3 为准，迁入 feat/requirements-workbench 独有能力。保留 main 的 SRS 九章节标准、分类、ReqSessionStore、独立飞书守护、统一网页和 S2 交接。兼容入口保留双模型有界审核、版本哈希、人工确认、固定版导出、CLI、演示模式及消息授权/去重/一次性配对。

## 设计与数据边界

- main 的 requirements.session.ReqSessionStore 与 .req_session.json 格式保持不变。版本化后端独立放在 requirements.versioned_session，保留顶层 requirements.SessionStore/SessionError；旧 requirements.session.SessionStore/SessionError 导入兼容。
- requirements CLI、requirements.web 与 requirements.feishu 是版本化兼容入口；默认统一网页仍为 python3 -m web.server，默认飞书仍为 requirements.feishu_daemon。两套入口不自动同步或转换数据、不自动启动、不修改任何运行服务。
- 版本化 JSON 草稿与 main 九章节 SRS 不可互当完成依据；旧确认结果不自动提交 S2。workspace/requirements、workspace/channels 与 .req_session.json 均忽略提交。历史基线和运行记录明确适用入口，不能用旧端口/服务记录声称当前运行状态。

## 执行与验收

1. 独立 worktree 整合，保留原工作区阶段机器人文档与 requests/。只解决本次冲突，不合 Luna 实验分支。
2. 先补并运行两个后端的共存测试：公共导入、各自读写和跨重启恢复、数据不互写；旧分支原测试覆盖审核/确认/配对，main 原测试覆盖 SRS/分类/统一网页。
3. 全量 unittest、版本化隔离中台假 Agent 集成、pipeline/build 假 Agent 全流程、JS 语法与 diff 检查通过。失败读取测试 traceback 与隔离中台输出；不通过则修根因再测，不改真实服务、不调收费模型。
4. 核对 README、模块入口、设计/协议、索引、决策、工具手册、next 与 changelog；验证后提交并 push 到已有功能 PR，更新正文与核对 GitHub 检查/冲突状态。用户已授权本次合并，满足条件后合入 main、同步本地主分支并复验。

## 不在本次范围

将双模型审核接入 main 统一 UI、两套格式数据迁移、跨渠道自动绑定到 ReqSessionStore、真实飞书/收费模型验收及部署。需要独立需求与验收标准。

## 文档核对与下一步

入口、重要决策 D018、模块边界、开发流程、两套数据流/磁盘格式、CLI/Python API 和兼容消息接口、变更记录及索引均已同步。文档健康：早期草案继续保留，明确其适用范围与历史服务状态，不复制 main 的 SRS 标准。无新增公网端点、依赖或部署配置；不升级发布版本或打标签。下一步依用户试用决定是否另立统一客户端的版本化审核及数据迁移需求。
