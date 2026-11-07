import unittest
from requirements.flow import build_req_prompt, is_finalize_request, normalize_user_input


class TestRequirementsFlow(unittest.TestCase):
    def test_normalize_user_input(self):
        self.assertIn("我选择方案 1", normalize_user_input("1"))
        self.assertIn("我选择方案 2", normalize_user_input("2"))
        self.assertIn("我选择方案 1", normalize_user_input("选1"))
        self.assertIn("我选择方案 2", normalize_user_input("第二种"))
        self.assertEqual(normalize_user_input("我想加一个按钮"), "我想加一个按钮")

    def test_is_finalize_request(self):
        self.assertTrue(is_finalize_request("可以定稿了"))
        self.assertTrue(is_finalize_request("请总结需求"))
        self.assertTrue(is_finalize_request("生成需求"))
        self.assertFalse(is_finalize_request("我想加一个功能"))

    def test_build_req_prompt_new(self):
        prompt = build_req_prompt("做个定时功能", is_new=True)
        self.assertIn("新需求探讨开始", prompt)
        self.assertIn("严格只读模式", prompt)

    def test_build_req_prompt_finalize(self):
        prompt = build_req_prompt("定稿", is_new=False)
        self.assertIn("用户指令：请求需求定稿", prompt)
        self.assertIn("软件需求规格说明", prompt)


if __name__ == "__main__":
    unittest.main()
