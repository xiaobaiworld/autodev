# 定位: flow.py 定义需求分析提示词构建、软件/部署/混合双轨自动与人工分类、选项列表化约束、输入标准化、规模与关联网络判断、原型/拓扑生成与定稿模板。
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

REQ_PROMPT_VERSION = "req-guided-v6 (compat req-guided-v5)"

REQ_TYPES = ("SOFTWARE", "DEPLOYMENT", "HYBRID")

REQ_TYPE_LABELS: dict[str, str] = {
    "AUTO": "🤖 Agent 自动寻找与分类 (Auto)",
    "SOFTWARE": "💻 偏软件功能开发 (SOFTWARE)",
    "DEPLOYMENT": "🚀 偏环境部署与脚本工程 (DEPLOYMENT)",
    "HYBRID": "🔗 软硬一体：功能开发+环境部署 (HYBRID)",
}

_DEPLOY_KEYWORDS = (
    "部署",
    "安装脚本",
    "部署脚本",
    "环境配置",
    "环境部署",
    "环境初始化",
    "上线脚本",
    "守护进程",
    "常驻服务",
    "开机自启",
    "launchd",
    "launchagent",
    "plist",
    "systemd",
    "dockerfile",
    "docker-compose",
    "docker",
    "nginx",
    "k8s",
    "kubernetes",
    "helm",
    "install.sh",
    "deploy.sh",
    "uninstall.sh",
    "运维脚本",
    "服务器环境",
    "反向代理",
    "进程保活",
    "健康检查探针",
    "回滚脚本",
    "幂等执行",
)

_SOFTWARE_KEYWORDS = (
    "页面",
    "按钮",
    "界面",
    "表单",
    "查询",
    "借阅",
    "借书",
    "还书",
    "支付",
    "收款",
    "购物车",
    "扫码",
    "导出",
    "报表",
    "弹窗",
    "工作台",
    "筛选",
    "排序",
    "增删改查",
    "业务流程",
    "前端",
    "后端接口",
)

_HYBRID_PHRASES = (
    "开发并部署",
    "代码和部署",
    "功能加部署",
    "配套部署脚本",
    "顺便写个部署",
    "并生成部署脚本",
    "既要开发又要部署",
)


def normalize_req_type(raw_type: str | None) -> str:
    """将用户输入或配置中的类型名归一化为 AUTO / SOFTWARE / DEPLOYMENT / HYBRID。"""
    if not raw_type:
        return "AUTO"
    cleaned = raw_type.strip().upper()
    alias_map = {
        "AUTO": "AUTO",
        "自动": "AUTO",
        "自动分类": "AUTO",
        "SOFTWARE": "SOFTWARE",
        "SOFT": "SOFTWARE",
        "DEV": "SOFTWARE",
        "软件": "SOFTWARE",
        "软件开发": "SOFTWARE",
        "功能开发": "SOFTWARE",
        "DEPLOYMENT": "DEPLOYMENT",
        "DEPLOY": "DEPLOYMENT",
        "OPS": "DEPLOYMENT",
        "INFRA": "DEPLOYMENT",
        "部署": "DEPLOYMENT",
        "环境部署": "DEPLOYMENT",
        "部署脚本": "DEPLOYMENT",
        "HYBRID": "HYBRID",
        "MIXED": "HYBRID",
        "混合": "HYBRID",
        "开发加部署": "HYBRID",
        "研发含部署": "HYBRID",
    }
    if cleaned in alias_map:
        return alias_map[cleaned]
    raise ValueError(f"不支持的需求类型: {raw_type!r}（可选: auto, software, deployment, hybrid）")


def detect_manual_type_override(user_text: str) -> str | None:
    """检测用户是否在自然语言对话中显式要求切换需求类型（人工直接分类轨道）。"""
    t = user_text.strip()
    if re.search(r"(切回|改为|恢复|使用)自动(寻找|分类|识别)", t):
        return "AUTO"
    if re.search(r"(这是|属于|改为|切为|按|定为)(偏)?(环境)?部署(工程|脚本)?需求", t):
        return "DEPLOYMENT"
    if re.search(r"(这是|属于|改为|切为|按|定为)(偏)?(软件|功能)(开发|研发)?需求", t):
        return "SOFTWARE"
    if re.search(r"(这是|属于|改为|切为|按|定为)(混合|软硬一体|开发含部署|开发加部署)需求", t):
        return "HYBRID"
    return None


def classify_requirement_type(
    user_text: str,
    history: list[dict[str, str]] | None = None,
    project_context: str = "",
) -> tuple[str, str]:
    """程序启发式 + 上下文联合预判：根据用户输入与历史对话自动寻找信号并推断需求类型。
    返回 (req_type, reason)，其中 req_type 为 SOFTWARE / DEPLOYMENT / HYBRID。
    """
    combined_parts = [user_text or ""]
    for item in history or []:
        if isinstance(item, dict):
            combined_parts.append(str(item.get("user") or ""))
    full_text = "\n".join(combined_parts).lower()

    matched_deploy = [kw for kw in _DEPLOY_KEYWORDS if kw in full_text]
    matched_soft = [kw for kw in _SOFTWARE_KEYWORDS if kw in full_text]
    matched_hybrid = [ph for ph in _HYBRID_PHRASES if ph in full_text]

    if matched_hybrid or (len(matched_deploy) >= 2 and len(matched_soft) >= 2):
        sample = ", ".join((matched_hybrid + matched_deploy[:2] + matched_soft[:2])[:4])
        return ("HYBRID", f"同时检测到软件功能与环境部署诉求（{sample}）")

    if matched_deploy and len(matched_deploy) >= len(matched_soft):
        sample = ", ".join(matched_deploy[:3])
        return ("DEPLOYMENT", f"检测到环境部署与脚本工程信号（{sample}）")

    if matched_soft:
        sample = ", ".join(matched_soft[:3])
        return ("SOFTWARE", f"检测到软件业务功能信号（{sample}）")

    return ("SOFTWARE", "默认归类为软件功能研发（待 Agent 结合仓库代码与部署目录进一步确认）")


def extract_agent_classified_type(reply_text: str) -> str | None:
    """从大模型回复或定稿 SRS 中提取 Agent 自动判定并写出的需求类型（SOFTWARE / DEPLOYMENT / HYBRID）。"""
    if not reply_text:
        return None
    # 1. 优先匹配显式标签，如 "🧭 需求类型：DEPLOYMENT" 或 "- **需求类型**：DEPLOYMENT"
    m = re.search(
        r"(?:需求类型|交付类型|类型分类)\s*\*{0,2}\s*[：:]\s*`*([A-Za-z\u4e00-\u9fa5+_/\-\s（）()]+)",
        reply_text,
    )
    if m:
        snippet = m.group(1).upper()
        if "HYBRID" in snippet or "混合" in snippet or ("软件" in snippet and "部署" in snippet):
            return "HYBRID"
        if "DEPLOYMENT" in snippet or "DEPLOY" in snippet or "环境部署" in snippet or "部署脚本" in snippet:
            return "DEPLOYMENT"
        if "SOFTWARE" in snippet or "软件" in snippet or "功能研发" in snippet:
            return "SOFTWARE"

    # 2. 兜底匹配行内明确的枚举标记
    if re.search(r"🧭\s*[^：\n]*[：:]\s*[^\n]*(DEPLOYMENT|偏环境部署|部署工程)", reply_text, re.I):
        return "DEPLOYMENT"
    if re.search(r"🧭\s*[^：\n]*[：:]\s*[^\n]*(HYBRID|开发含部署|混合型)", reply_text, re.I):
        return "HYBRID"
    if re.search(r"🧭\s*[^：\n]*[：:]\s*[^\n]*(SOFTWARE|偏软件开发|软件功能)", reply_text, re.I):
        return "SOFTWARE"
    return None


_SYSTEM_ROLE_PROMPT = f"""[{REQ_PROMPT_VERSION}]
你是一名极其克制、善于通过具象场景例子与原型/拓扑图引导用户的资深需求与部署架构分析师。你的任务是通过多轮极简、启发式的对话，协助项目负责人把朴素的想法梳理为一份标准的 9 章节《软件/部署需求规格说明书》。

【需求类型双轨识别职责（Agent 自动寻找分类 + 人工可指定）】：
系统中的需求分为三大类型，你必须在每轮对话中结合【当前目标项目背景】里的代码模块（`src/`）和部署资产（`deploy/`、脚本、守护配置）自动帮用户寻找定位并分类（若人工已指定则遵从人工指定）：
1. 💻 **SOFTWARE（偏软件功能开发）**：侧重业务功能、接口与界面交互，下游产出业务代码与测试；
2. 🚀 **DEPLOYMENT（偏环境部署与脚本工程）**：侧重环境初始化、一键安装/启动/停止/卸载脚本（如 `deploy/*.sh`）、守护进程配置（LaunchAgent/systemd/Docker/Nginx）、健康检查探针、幂等重跑与回滚机制，下游产出可执行部署脚本包；
3. 🔗 **HYBRID（软硬一体：软件开发+环境部署）**：既要开发新软件功能，又要求配套生成部署脚本或守护服务配置。

【核心红线（按需求类型精准区分）】：
1. 对 `SOFTWARE` 需求：严禁深入底层数据库建表 SQL 或具体业务代码实现细节；对 `DEPLOYMENT` / `HYBRID` 需求：**允许并必须厘清目标操作系统、运行守护方式、端口、目录路径、环境变量与拟生成的部署脚本名称**，但仍严禁在需求阶段直接编写大段完整实现源码或 SQL。
2. 严禁单次长篇大论！单次回复总字数必须严格控制在 300 字以内（包含线框图/拓扑图时总行数不超过 26 行），适配移动端飞书与 Web 阅读。
3. 严禁一次抛出多个开放性问题！每次只推进一个点，最多只问 1 个问题。
4. 必须换算成具体的操作场景（软件看使用者操作，部署看管理员执行脚本、探针检查与故障回滚场景）。

【需求规模与关联网络判断职责（重要）】：
当用户提出需求或探讨方向时，必须结合项目背景自动寻找并做出清晰判断：
0. 🧭【需求类型分类】：明确标定是 `SOFTWARE (偏软件开发)`、`DEPLOYMENT (偏环境部署)` 还是 `HYBRID (开发含部署)`；
1. 🏷️【需求规模类别】：判断是【史诗级大需求(Epic)】、【标准功能(Feature)】、【子功能小需求(Sub-feature)】还是【改动增强(Enhancement)】；
2. 📂【功能层级归属/模块归属】：软件需求指出挂载在 `src/` 哪个主业务模块下；部署需求指出挂载在 `deploy/` 或哪套运行环境体系下；
3. 🔗【需求关联网络】：基于近期 Git 变更、现有部署脚本和需求列表，自动寻找与其他需求的关系：Parent(所属父需求)、Depends-on(前置依赖，如部署需求依赖哪个软件模块需求)、Relates-to(业务协同)、Blocks(后置解锁) 或 None(独立)。

【需求拼图清单（按识别出的需求类型自动切换）】：
- 若为 `SOFTWARE`：
  • 拼图 1：核心目标与使用者场景
  • 拼图 2：核心业务流程与外部界面感知（UI 线框图）
  • 拼图 3：明确非目标 / 边界（本期坚决不做什么）
  • 拼图 4：可量化业务验收标准（Given-When-Then）
- 若为 `DEPLOYMENT`（或 `HYBRID` 的部署部分）：
  • 拼图 1：目标运行环境基线与痛点（什么 OS/架构、用 LaunchAgent/systemd/Docker 哪种守护、解决什么部署痛点）
  • 拼图 2：拟生成的部署脚本清单与生命周期（需生成哪些 `.sh`/配置文件，如何完成「预检 → 安装 → 启动 → 升级幂等重跑 → 回滚/卸载」）
  • 拼图 3：安全权限边界与明确非目标（哪些目录可写、密钥如何外置、本期不覆盖哪些操作系统或集群）
  • 拼图 4：部署探针、幂等重跑（连续跑 2~3 次结果一致）与异常回滚验收标准

【原型 / 部署拓扑草图呈现规范（```text）】：
- 对 `SOFTWARE`：使用 ```text 绘制页面 UI 线框图（展示标题、输入框、按钮、列表）；
- 对 `DEPLOYMENT`：使用 ```text 绘制 **部署架构拓扑与命令交互草图**（展示「宿主机 ↔ 守护服务 ↔ 监听端口 ↔ 日志/配置路径」拓扑框图，以及执行如 `bash deploy/install.sh` 的终端命令与预期输出）；
- 宽度控制在 35~44 个字符宽以内，保证手机端与 Web 端一屏清晰展示。

【每轮输出结构规范（必须包含以下模块）】：
1. 📌 [进度感知]：一句话标明当前阶段，如：`📌 [进度: 已定位为环境部署需求，正在明确部署脚本清单与守护方式]`
2. 🎯 [事实确认与拓扑判断]：
   • 核心诉求：一句话精准复述刚才达成的一致；
   • 🧭 需求类型：明确写出 `SOFTWARE (偏软件开发)`、`DEPLOYMENT (偏环境部署)` 或 `HYBRID (开发含部署)`；
   • 🏷️ 规模类别：指出是大需求(Epic)、标准功能(Feature)、还是子功能(Sub-feature)；
   • 📂 模块归属：指出归属的代码模块（`src/...`）或部署目录（`deploy/...`）；
   • 🔗 需求关联：明确与项目内已有模块/脚本/需求的关系（Parent/Depends-on/Relates-to/None）；
3. 🗳️ [单点推进（带具象场景举例）]：针对当前最缺的一块拼图，提出 1 个最关键的决策点，并收敛为 2 个带具体例子的选项：
   1. 方案一标题：简要说明。（例如：具体的操作或脚本执行场景示例）
   2. 方案二标题：简要说明。（例如：具体的操作或脚本执行场景示例）
   💡 附带提议：“需要看界面原型或部署拓扑草图吗？随时告诉我【看原型】/【看拓扑】或直接回复 1、2 继续。”

【定稿收口规则】：
当 4 块拼图全部集齐且用户无异议时，主动提示：
`🎉 需求核心要素已完整对齐！如无其他补充，请回复【定稿】，我将为你输出标准 9 章节需求规格说明书。`
"""

_FINALIZE_KEYWORDS = ("定稿", "总结需求", "生成需求", "确认需求", "输出需求", "需求定稿")
_PROTOTYPE_KEYWORDS = (
    "原型",
    "线框图",
    "界面图",
    "原型图",
    "画界面",
    "看界面",
    "界面长什么样",
    "做个原型",
    "做原型",
    "界面草图",
    "看原型",
    "看拓扑",
    "拓扑图",
    "部署拓扑",
    "部署图",
    "命令示意",
)


def is_prototype_request(text: str) -> bool:
    """判断是否为要求查看或生成界面原型 / 部署拓扑草图的指令。"""
    cleaned = text.strip().lower()
    return any(kw in cleaned for kw in _PROTOTYPE_KEYWORDS)


def normalize_user_input(text: str) -> str:
    """标准化用户的极简输入（如回复 '1', '2', '选1', '看原型', '看拓扑'），转化为清晰的意图。"""
    cleaned = text.strip()
    if cleaned.isdigit() and len(cleaned) <= 2:
        return f"我选择方案 {cleaned}。请以此方向为主继续推进，并探讨下一步关键细节或提供进一步建议。"
    choice_map = {
        "选1": "我选择方案 1",
        "选2": "我选择方案 2",
        "选3": "我选择方案 3",
        "第一种": "我选择方案 1",
        "第二种": "我选择方案 2",
        "第三种": "我选择方案 3",
        "第一个": "我选择方案 1",
        "第二个": "我选择方案 2",
        "第三个": "我选择方案 3",
        "看原型": "我想看一下当前需求的外部界面原型（低保真线框图）或部署架构拓扑草图。请用直观立体的 ```text 文本框图为我绘制示例。",
        "需要原型": "我想看一下当前需求的外部界面原型（低保真线框图）或部署架构拓扑草图。请用直观立体的 ```text 文本框图为我绘制示例。",
        "做个原型": "我想看一下当前需求的外部界面原型（低保真线框图）或部署架构拓扑草图。请用直观立体的 ```text 文本框图为我绘制示例。",
        "画个原型": "我想看一下当前需求的外部界面原型（低保真线框图）或部署架构拓扑草图。请用直观立体的 ```text 文本框图为我绘制示例。",
        "看拓扑": "我想看一下当前环境部署需求的架构拓扑与脚本命令交互草图。请用 ```text 绘制宿主机、服务守护、端口、日志路径及脚本执行示意。",
        "部署拓扑": "我想看一下当前环境部署需求的架构拓扑与脚本命令交互草图。请用 ```text 绘制宿主机、服务守护、端口、日志路径及脚本执行示意。",
    }
    if cleaned in choice_map:
        return choice_map[cleaned]
    return cleaned


def is_finalize_request(text: str) -> bool:
    cleaned = text.strip().lower()
    return any(kw in cleaned for kw in _FINALIZE_KEYWORDS)


def _build_finalize_section_guide(effective_type: str) -> str:
    """根据 SOFTWARE / DEPLOYMENT / HYBRID 类型生成差异化的 9 章节定稿指引（外层 9 章节同构，内层异核）。"""
    if effective_type == "DEPLOYMENT":
        return """## 1. 需求标识与元数据
（包含：需求编号[建议 REQ-DEPLOY-xxx]、需求名称、需求类型[`DEPLOYMENT (偏环境部署与脚本工程)`]、提出人、分析师、归属项目、定稿时间）

## 2. 需求规模分类与需求关联网络
（必须显式包含：🧭 **需求类型**[DEPLOYMENT]、🏷️ **需求规模类别**[Epic/Feature/Sub-feature/Enhancement]、📂 **功能层级归属/模块归属**[如 deploy/ 下的具体目录或服务体系]、🔗 **需求关联网络**[Parent/Depends-on/Relates-to/Blocks/Supersedes/None，标明所部署或关联的上游软件模块]）

## 3. 核心背景与业务目标 (Why & What)
（必须显式包含：**业务背景**[当前环境/手工部署痛点]、**业务目标**[自动化部署、进程自愈、耗时或稳定性指标]）

## 4. 业务用例与核心流程 (Scope)
（针对环境部署需求，本节必须明确列出：
  a. **拟生成的部署脚本与配置文件清单**（如 `deploy/install.sh`、`deploy/check-health.sh`、`*.plist` / `*.service` / `.env.example`）；
  b. **五步部署生命周期流程**：1. 环境预检(Pre-check) → 2. 安装与配置注入 → 3. 服务启动与守护绑定 → 4. 升级与幂等重跑 → 5. 停止/卸载与故障回滚）

## 5. 明确非目标与边界 (Non-goals)
（必须包含带 ❌ 标记的具体排除项，如本期不跨平台支持某系统、不自动修改生产防火墙或宿主机全局权限等）

## 6. 外部界面原型草图 (UI Wireframe)
（针对无 GUI 的环境部署需求，在 `## 6. 外部界面原型草图 (UI Wireframe)` 标题下使用 ```text 代码块绘制 **【部署架构拓扑与命令交互草图】**，至少 6 行，清晰展示：宿主机/服务进程/监听端口/日志与配置路径拓扑，以及执行一键部署脚本的命令与预期终端输出）

## 7. 业务约束与前置依赖
（包含：**目标环境基线**[OS 版本、CPU 架构、依赖软件版本]、**身份与权限约束**[运行账户、是否需要 sudo、目录读写边界]、**安全与配置约束**[密钥/Token 外置方式，严禁硬编码进脚本]）

## 8. 可量化验收标准清单 (Acceptance Criteria)
（必须包含至少 3 个可验证的部署场景 Given-When-Then：
  - **场景 1（首次部署与健康探针验证）**：脚本退出码为 0，守护进程存活，端口或健康检查命令返回预期状态；
  - **场景 2（幂等重跑验证）**：连续重复执行部署脚本 2~3 次不报错、不产生重复孤儿进程或破坏已有配置；
  - **场景 3（异常阻断与安全回滚）**：当端口被占用、依赖缺失或配置未填时，输出清晰错误原因并以非 0 退出码安全中止）

## 9. 下游架构设计关注点
（提炼 1~3 个给下游 S2 设计与 S4 脚本编码的关键考量：如脚本幂等实现机制、日志轮转路径、哪些高危操作触碰 BLOCK_RULE 需人工审批确认；严禁在本文档直接写完整业务源码或建表 SQL）"""

    if effective_type == "HYBRID":
        return """## 1. 需求标识与元数据
（包含：需求编号[建议 REQ-HYBRID-xxx]、需求名称、需求类型[`HYBRID (软件功能开发+环境部署工程)`]、提出人、分析师、归属项目、定稿时间）

## 2. 需求规模分类与需求关联网络
（必须显式包含：🧭 **需求类型**[HYBRID]、🏷️ **需求规模类别**[Epic/Feature/Sub-feature/Enhancement]、📂 **功能层级归属/模块归属**[同时指出 `src/` 业务模块与 `deploy/` 部署目录]、🔗 **需求关联网络**[Parent/Depends-on/Relates-to/Blocks/Supersedes/None]）

## 3. 核心背景与业务目标 (Why & What)
（必须显式包含：**业务背景**、**业务目标**[涵盖软件业务收益与自动化部署运行目标]）

## 4. 业务用例与核心流程 (Scope)
（分两部分按步骤 1. 2. 3. 列出：
  a. **核心软件业务流程**；
  b. **配套部署脚本清单与部署启动流程**（如 `deploy/*.sh`、服务守护配置与幂等重跑要求））

## 5. 明确非目标与边界 (Non-goals)
（必须包含带 ❌ 标记的具体功能边界与部署环境边界排除项）

## 6. 外部界面原型草图 (UI Wireframe)
（必须包含 ```text 代码块，至少 6 行，同时展示核心外部交互界面线框与服务部署拓扑/启动命令示意）

## 7. 业务约束与前置依赖
（包含：身份与权限约束、目标部署环境基线[OS/端口/守护方式/密钥外置]、业务规则约束）

## 8. 可量化验收标准清单 (Acceptance Criteria)
（必须包含：场景 1[核心功能正向验收]、场景 2[部署脚本幂等执行与健康探针验收]、场景 3[异常与边界阻断验收] 的 Given-When-Then 用例）

## 9. 下游架构设计关注点
（提炼给下游 S2 架构设计与部署脚本设计的考量，严禁直接写建表 SQL 或完整实现代码）"""

    # 默认 SOFTWARE
    return """## 1. 需求标识与元数据
（包含：需求编号、需求名称、需求类型[`SOFTWARE (偏软件功能开发)`]、提出人、分析师、归属项目、定稿时间）

## 2. 需求规模分类与需求关联网络
（必须显式包含：🧭 **需求类型**[SOFTWARE]、🏷️ **需求规模类别**[Epic/Feature/Sub-feature/Enhancement]、📂 **功能层级归属/模块归属**、🔗 **需求关联网络**[Parent/Depends-on/Relates-to/Blocks/Supersedes/None]）

## 3. 核心背景与业务目标 (Why & What)
（必须显式包含：**业务背景**、**业务目标**）

## 4. 业务用例与核心流程 (Scope)
（按步骤 1. 2. 3. 列出清晰业务流程）

## 5. 明确非目标与边界 (Non-goals)
（必须包含带 ❌ 标记的具体排除项）

## 6. 外部界面原型草图 (UI Wireframe)
（必须包含 ```text 代码块绘制的低保真线框图，至少 5 行，展示标题栏、输入框、按钮、展示区）

## 7. 业务约束与前置依赖
（包含：身份与权限约束、环境与前置依赖、规则约束）

## 8. 可量化验收标准清单 (Acceptance Criteria)
（必须包含：场景 1、场景 2 等可验证的 Given-When-Then 用例）

## 9. 下游架构设计关注点
（提炼 1~3 个给下游 S2 架构设计的考量，严禁包含代码实现或建表 SQL）"""


def build_req_prompt(
    text: str,
    is_new: bool = False,
    project_context_summary: str = "",
    req_type: str = "AUTO",
    req_type_source: str = "auto",
    inferred_type: str = "SOFTWARE",
    inferred_reason: str = "",
) -> str:
    """组装需求分析 Agent 的 Prompt，支持 Agent 自动寻找分类与人工指定双轨模式。"""
    prefix = _SYSTEM_ROLE_PROMPT
    if project_context_summary:
        prefix += f"\n【当前目标项目背景（含软件模块与现有部署资产）】\n{project_context_summary}\n"

    effective_type = req_type if (req_type in REQ_TYPES and req_type_source == "manual") else (
        req_type if req_type in REQ_TYPES else inferred_type
    )
    if req_type_source == "manual" and req_type in REQ_TYPES:
        type_directive = (
            f"\n【当前需求类型状态：👤 人工显式锁定为 `{req_type}` ({REQ_TYPE_LABELS.get(req_type, req_type)})】\n"
            f"请严格按 `{req_type}` 类型的拼图清单与模板推进，并在回复中标明 `🧭 需求类型：{req_type}（人工指定）`。\n"
        )
    else:
        type_directive = (
            f"\n【当前需求类型状态：🤖 Agent 自动寻找与分类模式】\n"
            f"• 程序初步信号预判：`{inferred_type}`（依据：{inferred_reason or '基于当前对话文本'}）\n"
            f"• 请你结合上方【当前目标项目背景】里的代码模块（`src/`）与部署资产（`deploy/` 等）做最终判断，并在回复中显式写出 `🧭 需求类型：SOFTWARE | DEPLOYMENT | HYBRID`。\n"
        )
    prefix += type_directive

    if is_finalize_request(text):
        sec_guide = _build_finalize_section_guide(effective_type)
        doc_kind_note = (
            "本需求属于【偏环境部署与脚本工程 (DEPLOYMENT)】，请重点写清拟生成的部署脚本清单、五步部署生命周期、部署架构拓扑与命令交互草图，以及健康探针与幂等重跑验收标准。"
            if effective_type == "DEPLOYMENT"
            else (
                "本需求属于【软硬一体：功能开发+环境部署 (HYBRID)】，请同时写清核心软件功能流程与配套部署脚本清单、拓扑草图及幂等验收标准。"
                if effective_type == "HYBRID"
                else "本需求属于【偏软件功能开发 (SOFTWARE)】，请聚焦业务用例、外部界面线框图与黑盒验收标准。"
            )
        )
        return f"""{prefix}
【用户指令：请求需求定稿（目标类型：{effective_type}）】
用户发出了定稿指令："{text}"。
{doc_kind_note}
请基于我们之前的多轮讨论，整理出一份标准的《软件需求规格说明（草案）》，严格遵循 SPEC-REQ-STANDARD-v1.1 格式，必须原样使用以下 9 个二级标题（`## N. ...`）以便通过自动化校验器（validator.py）：

{sec_guide}

输出要求：语言精炼，结构严谨，严禁直接编写建表 SQL 或业务函数源码，方便直接作为下游 S2 设计与 S4 实现/脚本生成的输入依据。
"""

    if is_prototype_request(text):
        return f"""{prefix}
【用户指令：请求外部界面原型示例 / 部署拓扑草图（当前类型：{effective_type}）】
用户希望查看当前需求的可视化线框图或部署拓扑草图："{text}"。

请严格按照规范回复：
1. 📌 [进度感知]：标明进入【界面原型感知 / 部署拓扑草图感知】；
2. 🎯 [场景说明]：一句话说明当前草图代表哪个核心交互环节或哪套环境部署链路；
3. 📱 [界面原型线框图 / 部署拓扑草图]：使用 ```text 绘制一个直观立体的 ASCII/Unicode 文本框图（控制在 14 行以内：若为 SOFTWARE 则展示页面标题、输入控件、操作按钮；若为 DEPLOYMENT/HYBRID 则展示「宿主机 ↔ 守护进程 ↔ 端口 ↔ 日志/配置路径」拓扑及脚本执行命令示例）；
4. 🗳️ [单点推进（2选1）]：针对该原型或部署拓扑的关键细节，抛出 2 个带具体例子的推进选项，末尾提示回复 1 或 2。
"""

    if is_new:
        return f"""{prefix}
【新需求探讨开始】
用户提出了新的需求、功能或部署想法：
"{text}"

请严格按照规范回复：
1. 📌 [进度感知]：标明进入【拼图 1：确认核心目标与使用场景（含自动类型定位）】；
2. 🎯 [事实确认与拓扑判断]：
   • 核心诉求：一句话精准复述你理解的核心诉求；
   • 🧭 需求类型：自动判断并明确标出是 `SOFTWARE (偏软件功能开发)`、`DEPLOYMENT (偏环境部署与脚本工程)` 还是 `HYBRID (功能开发+环境部署)`；
   • 🏷️ 需求规模：明确判断是大需求(Epic)、标准功能(Feature)还是子功能小需求(Sub-feature)；
   • 📂 模块归属：自动在项目中寻找并指出挂载在哪个业务模块（`src/...`）或部署目录（`deploy/...`）下；
   • 🔗 需求关联：明确与项目内已有模块、部署脚本或历史需求的关系（Parent/Depends-on/Relates-to/None）；
3. 🗳️ [单点推进（带具象场景举例）]：聚焦当前类型最核心的第一个分歧点（软件看使用场景，部署看目标 OS/守护方式/脚本范围），给出 2 个带生动例子的选项（1 和 2），引导用户选择；末尾附带提示：“需要做个界面原型或部署拓扑草图吗？随时回复【看原型】/【看拓扑】”。
"""

    return f"""{prefix}
【需求持续澄清与推进】
用户回复或补充：
"{text}"

请严格按照规范回复：
1. 📌 [进度感知]：更新当前正在讨论的拼图进度；
2. 🎯 [事实确认]：一句话复述刚才确认的内容（同时保持或动态修正 `🧭 需求类型`、`🏷️ 规模`、`📂 模块归属` 与 `🔗 需求关联`）；
3. 🗳️ [单点推进（带具象场景举例）]：按当前需求类型（`{effective_type}`）推进下一块拼图，给出 2 个带生动例子的选项（1 和 2），适时提示是否需要界面原型/部署拓扑草图，或在 4 块拼图全部集齐时提示【定稿】。
"""


def build_srs_template(
    req_type: str = "SOFTWARE",
    req_id: str | None = None,
    title: str | None = None,
    project: str = "/Users/bai/code/autodev",
) -> str:
    """生成可直接用于飞书定稿对照与 Web 端一键新建的 9 章节标准模板（支持 SOFTWARE / DEPLOYMENT / HYBRID）。"""
    norm_type = normalize_req_type(req_type)
    if norm_type == "AUTO":
        norm_type = "SOFTWARE"
    today_compact = datetime.now().strftime("%Y%m%d")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if norm_type == "DEPLOYMENT":
        rid = req_id or f"REQ-DEPLOY-SERVICE_DAEMON-{today_compact}"
        doc_title = title or "服务一键环境部署与守护自启工程"
        return f"""# 软件需求规格说明书（部署工程规范）：{doc_title}

## 1. 需求标识与元数据
- **需求编号**：{rid}
- **需求名称**：{doc_title}
- **需求类型**：DEPLOYMENT (偏环境部署与脚本工程)
- **提出人**：项目负责人 (Owner)
- **分析师**：AutoDev 需求分析师 ({REQ_PROMPT_VERSION})
- **归属项目**：`{project}`
- **定稿时间**：{now_str}

---

## 2. 需求规模分类与需求关联网络
- 🧭 **需求类型**：`DEPLOYMENT (偏环境部署与脚本工程)` — 核心产物为可执行部署脚本、守护配置与环境验证探针。
- 🏷️ **需求规模类别**：`标准功能需求 (Feature)` — 聚焦单机/标准环境的自动化部署与守护闭环。
- 📂 **功能层级与模块归属**：归属于 `deploy/`（环境部署与运维工程模块），服务于主项目核心后台进程。
- 🔗 **需求关联网络**：
  - `Parent（所属父需求）`：`None（独立部署工程需求）`
  - `Depends-on（前置依赖）`：`REQ-WEB-UNIFIED_CLIENT-20261107`（依赖被部署的目标服务入口就绪）
  - `Relates-to（业务协同）`：`deploy/install-req-bot.sh`（复用已验证的 LaunchAgent 部署约定）

---

## 3. 核心背景与业务目标 (Why & What)
- **业务背景**：当前服务在本地或新机器上线时需手工配置虚拟环境、环境变量并手动启动进程，遇到机器重启或进程异常退出时缺乏自动拉起、健康检查与一键回滚脚本。
- **业务目标**：交付一套标准化、幂等可重复执行的部署脚本包（`deploy/*.sh` 及守护配置），实现 30 秒内一键完成「环境预检 → 安装配置 → 守护启动 → 健康探针验真」，且重复执行 3 次以上结果完全一致。

---

## 4. 业务用例与核心流程 (Scope)
- **拟生成的部署脚本与配置文件清单**：
  1. `deploy/install-service.sh`：一键预检、配置生成与守护进程注册/重启脚本；
  2. `deploy/check-health.sh`：进程存活、端口监听与 HTTP/日志探针自检脚本；
  3. `deploy/uninstall-service.sh`：安全停止服务、卸载守护配置与回滚清理脚本。
- **五步标准部署生命周期流程**：
  1. **环境预检 (Pre-check)**：管理员执行安装脚本，脚本自动检查操作系统、Python 虚拟环境（`.venv`）、目标端口占用与必要配置文件，缺失时给出明确提示并退出；
  2. **配置与守护模板生成**：脚本将路径与端口参数渲染至系统守护配置（如 macOS `~/Library/LaunchAgents/*.plist` 或 Linux `systemd` 单元），不硬编码任何敏感密钥；
  3. **服务启动与自愈绑定**：卸载旧实例（若存在）并加载新守护任务，开启崩溃自动拉起（`KeepAlive`）并重定向标准输出/错误日志至 `logs/`；
  4. **升级与幂等重跑 (Idempotency)**：在已部署环境下再次运行 `install-service.sh`，脚本自动平滑重启并保持单实例运行，不产生重复进程或残留锁文件；
  5. **健康探针与一键回滚/卸载**：自动调用 `check-health.sh` 验证端口与响应码；异常时可通过 `uninstall-service.sh` 一键停止并恢复部署前状态。

---

## 5. 明确非目标与边界 (Non-goals)
- ❌ **不修改业务功能代码**：本次需求仅生成与维护 `deploy/` 下的部署脚本及守护配置，不改动核心业务模块逻辑；
- ❌ **不跨公网暴露端口或修改系统防火墙**：默认仅绑定本机回环或指定安全地址，不自动开放公网防火墙规则；
- ❌ **不将真实密钥写入版本库**：所有 Token / Secret 必须从外部环境或本地受保护配置文件读取。

---

## 6. 外部界面原型草图 (UI Wireframe)
```text
┌──────────────────────────────────────────────┐
│ [部署架构拓扑与命令交互示意]                 │
├──────────────────────────────────────────────┤
│  管理员终端: bash deploy/install-service.sh  │
│        │                                     │
│        ▼ (1.预检 .venv & 配置 ➔ 2.注册守护)  │
│  ┌────────────────────────────────────────┐  │
│  │ 宿主机守护 (LaunchAgent / systemd)     │  │
│  │   ├─► 进程: python -m web.server       │  │
│  │   ├─► 端口: 127.0.0.1:8765 (Loopback)  │  │
│  │   └─► 日志: logs/web-server.{{out,err}}  │  │
│  └────────────────────────────────────────┘  │
│        │                                     │
│        ▼ (3.健康探针 deploy/check-health.sh) │
│  [✅ PASS] PID=48210 | Port=8765 | HTTP=200  │
└──────────────────────────────────────────────┘
```

---

## 7. 业务约束与前置依赖
- **目标环境基线**：macOS（LaunchAgent `launchctl`）或 Linux（`systemd`），具备 Python 3.10+ 及项目 `.venv` 虚拟环境；
- **身份与权限约束**：仅在当前普通用户权限下运行（如 `~/Library/LaunchAgents`），无需 `sudo` 修改系统全局目录，不触碰高危权限红线；
- **安全与配置约束**：严禁在部署脚本中硬编码 `app_secret` 或 API Key；脚本必须设置 `set -euo pipefail` 保证错误即刻可见。

---

## 8. 可量化验收标准清单 (Acceptance Criteria)
1. **场景 1（首次一键部署与健康探针通过）**：
   - *Given* 目标机器存在 `.venv` 且服务尚未启动；
   - *When* 执行 `bash deploy/install-service.sh` 并运行 `bash deploy/check-health.sh`；
   - *Then* 脚本退出码为 `0`，守护进程处于运行态，目标端口正常响应，耗时 ≤ 10 秒。
2. **场景 2（幂等重复运行验证 — 连续执行 3 次）**：
   - *Given* 服务已通过部署脚本启动运行；
   - *When* 连续重复执行 `bash deploy/install-service.sh` 3 次；
   - *Then* 每次退出码均为 `0`，系统中始终只有 1 个服务进程实例，无端口冲突报错或孤儿进程。
3. **场景 3（依赖缺失阻断与一键卸载回滚）**：
   - *Given* 关键配置文件或虚拟环境缺失，或管理员执行 `bash deploy/uninstall-service.sh`；
   - *When* 触发部署预检或执行卸载脚本；
   - *Then* 预检失败时清晰输出缺失项并以非 `0` 退出码中止；卸载后守护项与监听进程被彻底清理。

---

## 9. 下游架构设计关注点
1. 部署脚本在重复执行时的平滑停止与重启竞争条件处理（确保端口释放后再拉起新进程）；
2. 日志文件目录（`logs/`）的自动创建与防无限膨胀策略；
3. 下游 S4 编码阶段需直接生成可执行的 `deploy/*.sh` 脚本，并在 S5 检查阶段通过 `bash -n` 语法检查与隔离沙箱实跑验证。
"""

    if norm_type == "HYBRID":
        rid = req_id or f"REQ-HYBRID-FEATURE_AND_DEPLOY-{today_compact}"
        doc_title = title or "业务功能模块研发与配套一键部署工程"
        return f"""# 软件需求规格说明书（研发含部署混合规范）：{doc_title}

## 1. 需求标识与元数据
- **需求编号**：{rid}
- **需求名称**：{doc_title}
- **需求类型**：HYBRID (软硬一体：功能开发+环境部署)
- **提出人**：项目负责人 (Owner)
- **分析师**：AutoDev 需求分析师 ({REQ_PROMPT_VERSION})
- **归属项目**：`{project}`
- **定稿时间**：{now_str}

---

## 2. 需求规模分类与需求关联网络
- 🧭 **需求类型**：`HYBRID (软硬一体：功能开发+环境部署)` — 既交付业务功能代码，又配套交付一键部署与守护脚本。
- 🏷️ **需求规模类别**：`标准功能需求 (Feature)`
- 📂 **功能层级与模块归属**：代码归属 `src/` 对应业务模块，部署脚本归属 `deploy/` 目录。
- 🔗 **需求关联网络**：
  - `Parent（所属父需求）`：`None`
  - `Depends-on（前置依赖）`：`None`
  - `Relates-to（业务协同）`：`REQ-WEB-UNIFIED_CLIENT-20261107`

---

## 3. 核心背景与业务目标 (Why & What)
- **业务背景**：新增核心业务能力的同时，需要保证该服务在宿主环境可一键启动并常驻守护，避免“代码写完但无法稳定运行”。
- **业务目标**：完成核心业务功能闭环，并同步交付可幂等执行的部署与健康检查脚本。

---

## 4. 业务用例与核心流程 (Scope)
1. **核心业务流程**：使用者发起业务请求 → 系统完成核心校验与处理 → 返回结构化结果并在界面展示；
2. **配套部署脚本清单与流程**：提供 `deploy/install.sh` 与 `deploy/check-health.sh`，依次完成环境预检、服务守护注册、启动与健康探针验证。

---

## 5. 明确非目标与边界 (Non-goals)
- ❌ **不做多机分布式集群编排**：本期仅面向本机或单节点标准环境部署；
- ❌ **不接入外部商业付费网关**：仅使用本机已有环境依赖。

---

## 6. 外部界面原型草图 (UI Wireframe)
```text
┌──────────────────────────────────────────────┐
│ [业务界面 + 部署拓扑双视图]                  │
├──────────────────────────────────────────────┤
│ 【外部交互界面】                             │
│  [ 输入参数框............ ]  [ 立即执行 ]    │
│  状态反馈: ● 运行正常                        │
├──────────────────────────────────────────────┤
│ 【部署拓扑与命令】                           │
│  $ bash deploy/install.sh && check-health.sh │
│  Host ──► Service Daemon ──► 127.0.0.1:Port  │
└──────────────────────────────────────────────┘
```

---

## 7. 业务约束与前置依赖
- **身份与权限约束**：仅授权用户可访问核心操作，部署脚本在普通用户权限下运行；
- **环境与前置依赖**：依赖 Python 3 标准环境，密钥通过环境变量或本地配置读取。

---

## 8. 可量化验收标准清单 (Acceptance Criteria)
1. **场景 1（核心功能正向验收）**：
   - *Given* 服务正常运行且输入合法参数；
   - *When* 用户触发核心业务操作；
   - *Then* 返回预期业务结果并通过单元测试。
2. **场景 2（一键部署与幂等重跑验收）**：
   - *Given* 代码构建完成；
   - *When* 连续执行 2 次部署脚本并运行健康探针；
   - *Then* 退出码均为 `0`，服务单实例存活且探针检查通过。

---

## 9. 下游架构设计关注点
1. 业务模块与部署配置的参数解耦（端口、路径可通过环境变量覆盖）；
2. 部署脚本的幂等性与异常退出码设计。
"""

    # 默认 SOFTWARE 模板
    rid = req_id or f"REQ-SOFT-FEATURE-{today_compact}"
    doc_title = title or "标准软件业务功能需求"
    return f"""# 软件需求规格说明书（草案）：{doc_title}

## 1. 需求标识与元数据
- **需求编号**：{rid}
- **需求名称**：{doc_title}
- **需求类型**：SOFTWARE (偏软件功能开发)
- **提出人**：项目负责人 (Owner)
- **分析师**：AutoDev 需求分析师 ({REQ_PROMPT_VERSION})
- **归属项目**：`{project}`
- **定稿时间**：{now_str}

---

## 2. 需求规模分类与需求关联网络
- 🧭 **需求类型**：`SOFTWARE (偏软件功能开发)`
- 🏷️ **需求规模类别**：`标准功能需求 (Feature)`
- 📂 **功能层级与模块归属**：归属于 `src/` 下对应的核心业务模块。
- 🔗 **需求关联网络**：
  - `Parent（所属父需求）`：`None`
  - `Depends-on（前置依赖）`：`None`
  - `Relates-to（业务协同）`：`REQ-WEB-UNIFIED_CLIENT-20261107`

---

## 3. 核心背景与业务目标 (Why & What)
- **业务背景**：阐述当前使用者的操作痛点与未被满足的业务场景。
- **业务目标**：说明功能上线后带来的可量化效率提升或业务闭环收益。

---

## 4. 业务用例与核心流程 (Scope)
1. 使用者进入功能页面并输入/选择必要业务条件；
2. 点击主操作按钮触发处理；
3. 系统完成业务校验并即时反馈处理结果。

---

## 5. 明确非目标与边界 (Non-goals)
- ❌ **本期不实现跨系统批量导入导出**；
- ❌ **暂不改造底层历史归档数据格式**。

---

## 6. 外部界面原型草图 (UI Wireframe)
```text
┌────────────────────────────────────────┐
│ 📋 功能页面标题栏                      │
├────────────────────────────────────────┤
│ 关键输入项: [ 请填写内容.......... ]   │
│ 筛选项:     (●) 方案一   ( ) 方案二    │
├────────────────────────────────────────┤
│ [ 🚀 确认提交 ]          [ 取消重置 ]  │
└────────────────────────────────────────┘
```

---

## 7. 业务约束与前置依赖
- **身份与权限约束**：仅对已授权白名单用户开放操作权限；
- **环境与前置依赖**：复用现有项目基础运行环境；
- **规则约束**：关键写操作需具备并发安全保护。

---

## 8. 可量化验收标准清单 (Acceptance Criteria)
1. **场景 1（核心正向业务流）**：
   - *Given* 用户已登录且输入满足业务规则；
   - *When* 点击【确认提交】；
   - *Then* 状态立即更新并展示成功反馈，响应耗时 ≤ 2 秒。
2. **场景 2（异常或边界输入阻断）**：
   - *Given* 用户提交空值或冲突参数；
   - *When* 尝试提交；
   - *Then* 界面给出明确中文错误原因并阻断写入。

---

## 9. 下游架构设计关注点
1. 核心状态变更的原子性与并发锁控制；
2. 异常路径的可观测日志记录与边界防御。
"""
