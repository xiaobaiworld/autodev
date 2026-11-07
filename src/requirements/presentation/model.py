# 定位: model.py 定义需求分析结果的渠道无关语义模型与解析提取逻辑。
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RequirementChoice:
    index: int
    title: str
    description: str


@dataclass(frozen=True)
class RequirementResponse:
    stage: str  # "explore" | "clarify" | "finalize"
    summary: str
    body: str
    choices: list[RequirementChoice] = field(default_factory=list)
    call_to_action: str = ""
    raw_markdown: str = ""


def extract_semantic_response(text: str, is_finalize: bool = False) -> RequirementResponse:
    """从 Agent 的 Markdown 输出中解析出结构化的语义对象。"""
    raw = text.strip()
    if is_finalize:
        return RequirementResponse(
            stage="finalize",
            summary="软件需求规格说明（草案）",
            body=raw,
            choices=[],
            call_to_action="如需调整请继续回复；如无异议可回复【确认】归档。",
            raw_markdown=raw,
        )

    lines = raw.splitlines()
    summary = ""
    body_lines: list[str] = []
    choices: list[RequirementChoice] = []
    call_to_action = ""

    # 尝试抽取第一段有实质意义的内容作为 summary
    found_summary = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if not found_summary and not stripped.startswith("#"):
            summary = stripped
            found_summary = True
            continue
        body_lines.append(line)

    body_text = "\n".join(body_lines).strip()

    # 尝试解析选项列表 (1. 2. 3.)
    choice_idx = 1
    choice_matches = list(re.finditer(r"(?:^|\n)\s*(?:(\d+)[\.、\)]|【选项\s*(\d+)】)\s*(.+)", raw))
    if choice_matches:
        for m in choice_matches:
            idx_str = m.group(1) or m.group(2)
            idx = int(idx_str) if idx_str and idx_str.isdigit() else choice_idx
            content = m.group(3).strip()
            if "：" in content:
                parts = content.split("：", 1)
                title, desc = parts[0].strip(), parts[1].strip()
            elif ":" in content:
                parts = content.split(":", 1)
                title, desc = parts[0].strip(), parts[1].strip()
            else:
                title, desc = content[:20], content
            choices.append(RequirementChoice(index=idx, title=title, description=desc))
            choice_idx += 1

    if choices:
        call_to_action = "👉 请直接回复数字（如 1 或 2）选择你倾向的方案，也可直接输入补充想法。"
    else:
        call_to_action = "💬 请告诉我你的具体想法或针对上述考量的决定。"

    return RequirementResponse(
        stage="clarify" if choices else "explore",
        summary=summary or "需求分析与考量",
        body=body_text or raw,
        choices=choices,
        call_to_action=call_to_action,
        raw_markdown=raw,
    )
