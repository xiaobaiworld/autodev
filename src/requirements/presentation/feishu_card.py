# 定位: feishu_card.py 将语义对象渲染为飞书交互卡片 JSON。
from __future__ import annotations

from typing import Any

from requirements.presentation.base import BasePresenter
from requirements.presentation.model import RequirementResponse


class FeishuCardPresenter(BasePresenter):
    """飞书专属高颜值卡片呈现器。"""

    @property
    def channel_name(self) -> str:
        return "feishu_card"

    def render(self, response: RequirementResponse) -> dict[str, Any]:
        is_final = response.stage == "finalize"
        header_color = "green" if is_final else "blue"
        header_title = "📋 软件需求规格说明（草案）" if is_final else "💡 需求分析与架构探讨"

        elements: list[dict[str, Any]] = []

        # 1. 核心诉求摘要（引言区块）
        if response.summary and not is_final:
            elements.append({
                "tag": "markdown",
                "content": f"🎯 **核心诉求理解**：\n> {response.summary}",
            })
            elements.append({"tag": "hr"})

        # 2. 核心分析正文
        if response.body:
            body_content = response.body[:2800]
            elements.append({
                "tag": "markdown",
                "content": body_content,
            })

        # 3. 待抉择的方案列表（1、2 选项高亮展现）
        if response.choices:
            elements.append({"tag": "hr"})
            elements.append({
                "tag": "markdown",
                "content": "### 🗳️ **请选择你倾向的方向**",
            })

            choice_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
            for choice in response.choices:
                emoji = choice_emojis[choice.index - 1] if 0 < choice.index <= len(choice_emojis) else f"【{choice.index}】"
                choice_md = f"{emoji} **{choice.title}**\n{choice.description}"
                elements.append({
                    "tag": "markdown",
                    "content": choice_md,
                })

        # 4. 底部行动引导
        if response.call_to_action:
            elements.append({"tag": "hr"})
            elements.append({
                "tag": "markdown",
                "content": f"*{response.call_to_action}*",
            })

        return {
            "config": {
                "wide_screen_mode": True,
            },
            "header": {
                "template": header_color,
                "title": {
                    "tag": "plain_text",
                    "content": header_title,
                },
            },
            "elements": elements,
        }
