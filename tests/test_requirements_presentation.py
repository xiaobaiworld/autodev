import unittest
from requirements.presentation import (
    FeishuCardPresenter,
    PlainTextPresenter,
    RequirementChoice,
    RequirementResponse,
    extract_semantic_response,
)


class TestRequirementsPresentation(unittest.TestCase):
    def test_extract_semantic_response_with_choices(self):
        text = """
分析用户需求：做定时提醒。
有以下两个方案：
1. 轻量化轮询：使用现有服务做定时。
2. 调度分离：使用系统 launchd 守护。
请选择。
"""
        res = extract_semantic_response(text, is_finalize=False)
        self.assertEqual(res.stage, "clarify")
        self.assertEqual(len(res.choices), 2)
        self.assertIn("轻量化轮询", res.choices[0].title)
        self.assertIn("调度分离", res.choices[1].title)

    def test_feishu_card_presenter(self):
        presenter = FeishuCardPresenter()
        res = RequirementResponse(
            stage="clarify",
            summary="增加提醒功能",
            body="分析内容",
            choices=[
                RequirementChoice(index=1, title="方案一", description="轻量"),
                RequirementChoice(index=2, title="方案二", description="独立"),
            ],
            call_to_action="请回复 1 或 2",
        )
        card = presenter.render(res)
        self.assertTrue(card["config"]["wide_screen_mode"])
        self.assertEqual(card["header"]["template"], "blue")
        elements = card["elements"]
        self.assertTrue(any("🎯 **核心诉求理解**" in el.get("content", "") for el in elements if el.get("tag") == "markdown"))
        self.assertTrue(any("1️⃣ **方案一**" in el.get("content", "") for el in elements if el.get("tag") == "markdown"))

    def test_plain_text_presenter(self):
        presenter = PlainTextPresenter()
        res = RequirementResponse(
            stage="clarify",
            summary="增加提醒功能",
            body="分析内容",
            choices=[
                RequirementChoice(index=1, title="方案一", description="轻量"),
            ],
            call_to_action="请回复 1",
        )
        text = presenter.render(res)
        self.assertIn("【需求分析与架构探讨】", text)
        self.assertIn("1️⃣ 方案一：轻量", text)


if __name__ == "__main__":
    unittest.main()
