# 需求澄清模块 (Requirements Clarification Module)

> **当前版本**：`v0.3.1` (2026-11-07)  
> **当前状态**：**飞书端与全系统 Web 客户端双端落地运行，已直通 S2**  
> **服务状态**：macOS LaunchAgent 常驻守护 (`com.autodev.req-bot`) + 本机 Web 客户端 (`python3 -m web.server`)  
> **测试状态**：244 项单元测试全量通过 (`python -m unittest discover -s tests`)

---

## 一、模块定位与核心设计哲学

AutoDev 需求澄清模块是整个研发流水线（S1~S9）的源头枢纽。它通过飞书/桌面/命令行等交互渠道，协助项目负责人把朴素、模糊的业务想法，逐步梳理为一份标准、严谨、边界完备且机器可验证的《软件需求规格说明书（草案）》（SRS）。

### 核心三原则：
1. **输入端宽松容错**：输入可以发散、口语化、碎片化甚至直接贴粗糙文档；
2. **后台增量拼图**：结合系统已有代码模块、Git 提交记录与历史需求，由大模型在后台增量推断并自动归纳；
3. **输出端确定性收敛**：人机只在关键分歧点确认，最终产出必须 100% 符合统一结构，并由程序自动执行规则验真。

---

## 二、核心权威文档直达（两份标准文档）

本模块的体系规范与实现说明由以下两份核心文档构成：

| 文档路径 | 文档名称 | 核心职责 |
| :--- | :--- | :--- |
| 📘 **[`docs/specs/REQUIREMENT_SPEC_STANDARD.md`](../../specs/REQUIREMENT_SPEC_STANDARD.md)** | **《软件需求规格说明书产出规范与校验标准 (SRS Standard v1.0)》** | **产出物标准契约**：<br>• 从模糊到清晰的四阶段演进生命周期；<br>• 九大必填标准章节与格式规范；<br>• 需求规模分类 (Epic/Feature/Sub-feature) 与网状关系矩阵表示法；<br>• 自动化规则引擎断言（RULE-01 ~ RULE-09）。 |
| 📗 **[`docs/modules/requirements/feishu-requirement-bot.md`](feishu-requirement-bot.md)** | **《需求澄清模块与飞书端沉淀说明书》** | **模块实现与运行指南**：<br>• Session 演进全过程与核心决策全记录；<br>• 多渠道呈现层抽象（FeishuCard / PlainText）；<br>• 模型提示词演进（从 v1 到 v5）；<br>• 外部界面低保真线框图 (ASCII Wireframe) 原理；<br>• 真实场景黄金范本（Gold Standard Sample）。 |

### 本目录早期设计草案（保留备查与后续阶段合入）
- [`requirements.md`](requirements.md)：早期关于通用经验清单、版本基线与逐轮原始交互审计的需求草案；
- [`design.md`](design.md)：早期本机 CLI 小状态循环与 `workspace/requirements/` 目录结构设计草案；
- [`protocol.md`](protocol.md)：早期 CLI 命令、草稿 JSON 及逐轮调用计时约定草案（尚未在飞书守护进程中全量实现，供后续迭代参考）。

---

## 三、代码结构与技术拓扑

所有代码、配置与测试完全内聚在 `autodev` 项目内部，不依赖任何外部系统：

```text
autodev/
├── src/requirements/
│   ├── feishu_daemon.py       # 飞书官方 WebSocket 长连接常驻服务入口
│   ├── flow.py                # 提示词构建 (req-guided-v5)、极简数字输入标准化、定稿判断
│   ├── validator.py           # 确定性程序化检查器 (断言 RULE-01~09，定稿时自动验真)
│   ├── handoff.py             # 阶段交接器 (将通过校验的 SRS 直通移交主流水线 S2 架构设计)
│   ├── llm_provider.py        # 独立大模型注册表与调用层 (完整模型 ID 校验、cli_session/cli_stateless)
│   ├── context_detector.py    # 项目上下文探测器 (模块概貌、近期 Git 提交、历史需求)
│   ├── agent_runner.py        # Claude/Codex/agy CLI 驱动、只读沙箱保障、横幅过滤解析
│   ├── responder.py           # 飞书消息发送、交互卡片推送、Markdown 产物上传
│   ├── session.py             # 会话持久化 (项目路径、模型、调用模式、session_id、历史问答、最近定稿)
│   ├── config.py              # TOML 配置加载与鉴权白名单过滤
│   └── presentation/          # 多渠道呈现抽象层 (领域语义模型、FeishuCard、PlainText)
├── tests/
│   ├── test_requirements_flow.py           # 流程与提示词断言测试
│   ├── test_requirements_presentation.py   # 卡片与文本呈现器测试
│   ├── test_requirements_config.py         # 配置与目录校验测试
│   ├── test_requirements_context.py        # 上下文探测测试
│   ├── test_requirements_validator.py      # 程序化规则校验器与黄金范本契约测试
│   └── test_requirements_llm_and_handoff.py# 独立模型层与直通 S2 交接器测试
└── deploy/
    ├── install-req-bot.sh     # macOS LaunchAgent 一键安装/平滑重启脚本
    └── uninstall-req-bot.sh   # 服务安全卸载脚本
```

---

## 四、服务运维与使用指南

### 1. 服务控制与状态检查
```bash
# 查看服务是否在后台常驻运行
launchctl list | grep autodev

# 平滑重启服务（配置或代码更新后）
bash deploy/install-req-bot.sh

# 查看实时运行日志
tail -f logs/req_daemon.out
```

### 2. 飞书日常交互
- **直接发想法**：在飞书对话框直接描述需求（无需任何命令前缀）；
- **极简确认**：手机端直接回复 `1` 或 `2` 秒选方案；
- **看界面原型**：回复 `看原型` 或 `做个原型` 查看等宽文本线框图；
- **查看/切换大模型**：发送 `/model` 查看完整模型 ID 列表，发送 `/model <名称>`（如 `/model claude-opus`、`/model codex`）随时切换模型并保留历史对话；
- **查看/切换调用方式**：发送 `/mode` 或 `/mode <cli_session|cli_stateless>`；
- **重置新需求**：发送 `/new` 或 `新需求`；
- **需求定稿**：回复 `定稿`，系统自动完成程序化验真并在 `docs/requirements/` 落盘 Markdown 文档；
- **直通 S2 架构设计**：定稿后回复 `启动设计` 或 `/handoff`，跳过重复 S1 分析，直接初始化主流水线 `S2 架构设计` 任务。
