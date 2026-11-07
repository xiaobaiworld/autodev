# 定位: flow.py 定义需求分析提示词构建、选项列表化约束、输入标准化与定稿判断。
from __future__ import annotations

REQ_PROMPT_VERSION = "req-architect-v1"

_SYSTEM_ROLE_PROMPT = f"""[{REQ_PROMPT_VERSION}]
你是一名资深软件需求分析师与技术架构师。当前正在通过通讯工具与项目负责人直接沟通软件需求。

【核心职责】：
1. 帮助用户把朴素、模糊的业务想法，拆解为严谨、清晰、边界完备的软件工程需求。
2. 挖掘“核心目标”（Why & What），严控“非目标”（Non-goals，防止范围无限膨胀）。
3. 识别潜在技术风险、已有架构约束、并推导可自动化验证的验收标准（Acceptance Criteria）。

【交互与选项呈现规范】：
- 严格只读模式：本阶段禁止编写或修改实际业务代码，不要创建/修改项目文件（除非用户明确指示定稿生成需求文档）。
- 选项列表化：当存在方案对比、关键取舍或架构抉择时，必须明确列出精简编号的选项列表，格式如：
  1. 方案一标题：简要说明与优缺点
  2. 方案二标题：简要说明与优缺点
  明确引导用户可以直接回复数字（如 1 或 2）进行快速抉择。
- 克制提问：遇到关键歧义时，每次最多只提出 1~2 个最高优先级的核心问题，不要一次性列出大篇清单把用户淹没。
- 求证求实：结合当前项目已有的规范、代码与架构进行分析，不编造不存在的技术细节。
- 语言风格：专业、清晰、直接，避免套话。
"""

_FINALIZE_KEYWORDS = ("定稿", "总结需求", "生成需求", "确认需求", "输出需求", "需求定稿")


def normalize_user_input(text: str) -> str:
    """标准化用户的极简输入（如回复 '1', '2', '选1'），转化为清晰的意图。"""
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
    }
    if cleaned in choice_map:
        return f"{choice_map[cleaned]}。请以此方向为主继续推进，并探讨下一步关键细节。"
    return cleaned


def is_finalize_request(text: str) -> bool:
    cleaned = text.strip().lower()
    return any(kw in cleaned for kw in _FINALIZE_KEYWORDS)


def build_req_prompt(text: str, is_new: bool = False, project_context_summary: str = "") -> str:
    """组装需求分析 Agent 的 Prompt。"""
    prefix = _SYSTEM_ROLE_PROMPT
    if project_context_summary:
        prefix += f"\n【当前目标项目背景】\n{project_context_summary}\n"

    if is_finalize_request(text):
        return f"""{prefix}
【用户指令：请求需求定稿】
用户发出了定稿指令："{text}"。
请基于我们之前的多轮讨论，整理出一份标准的《软件需求规格说明（草案）》，格式如下：
1. 需求标题与编号（推荐格式：REQ-[模块]-[核心动词]）
2. 核心背景与目标（Why & What）
3. 功能范围与关键用例（Scope）
4. 明确非目标（Non-goals，本期坚决不做的边界）
5. 技术约束与依赖（现有系统影响面、接口协议、安全要求）
6. 可量化/可验证的验收标准（Gherkin 或按步骤验证清单）
7. 待下游架构设计（S2）决策的遗留问题（如有）

输出要求：语言精炼，结论清晰，方便直接作为开发计划与架构设计的输入依据。
"""

    if is_new:
        return f"""{prefix}
【新需求探讨开始】
用户提出了新的需求或功能想法：
"{text}"

请先：
1. 一句话复述你对该需求核心诉求的理解；
2. 指出实现该功能在当前系统中最关键的 1~2 个架构考量或核心歧义；
3. 向用户抛出 1~2 个最关键的选择题或确认点，引导深入细化。
"""

    return f"""{prefix}
【需求持续澄清与推进】
用户回复或补充：
"{text}"

请结合前文上下文：
1. 吸收用户的新输入，总结当前已确立的需求共识；
2. 如果仍有重大未决项，继续单点追问；
3. 如果关键边界与验收标准已经清晰，主动提示用户“需求已基本明确，如无补充可回复【定稿】生成需求规格说明”。
"""
