# 定位: plain_text.py 将语义对象渲染为精美排版的通用文本（适用于微信、邮件或普通终端）。
from __future__ import annotations

from requirements.presentation.base import BasePresenter
from requirements.presentation.model import RequirementResponse


class PlainTextPresenter(BasePresenter):
    """通用排版纯文本呈现器（适用于微信、终端等普通文本渠道）。"""

    @property
    def channel_name(self) -> str:
        return "plain_text"

    def render(self, response: RequirementResponse) -> str:
        is_final = response.stage == "finalize"
        lines: list[str] = []

        if is_final:
            lines.append("📋 【软件需求规格说明（草案）】")
        else:
            lines.append("💡 【需求分析与架构探讨】")
        lines.append("=" * 30)

        if response.summary and not is_final:
            lines.append(f"🎯 核心诉求：{response.summary}")
            lines.append("-" * 30)

        if response.body:
            lines.append(response.body)

        if response.choices:
            lines.append("")
            lines.append("🗳️ 【请选择你倾向的方向】：")
            choice_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
            for choice in response.choices:
                emoji = choice_emojis[choice.index - 1] if 0 < choice.index <= len(choice_emojis) else f"[{choice.index}]"
                lines.append(f"{emoji} {choice.title}：{choice.description}")

        if response.call_to_action:
            lines.append("")
            lines.append(f"👉 {response.call_to_action}")

        return "\n".join(lines)
