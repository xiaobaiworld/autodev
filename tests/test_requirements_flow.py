import unittest
from requirements.flow import (
    build_req_prompt,
    build_srs_template,
    classify_requirement_type,
    detect_manual_type_override,
    extract_agent_classified_type,
    is_finalize_request,
    is_prototype_request,
    normalize_req_type,
    normalize_user_input,
)


class TestRequirementsFlow(unittest.TestCase):
    def test_normalize_user_input(self):
        self.assertIn("我选择方案 1", normalize_user_input("1"))
        self.assertIn("我选择方案 2", normalize_user_input("2"))
        self.assertIn("我选择方案 1", normalize_user_input("选1"))
        self.assertIn("我选择方案 2", normalize_user_input("第二种"))
        self.assertIn("外部界面原型", normalize_user_input("看原型"))
        self.assertIn("外部界面原型", normalize_user_input("做个原型"))
        self.assertIn("部署", normalize_user_input("看拓扑"))
        self.assertEqual(normalize_user_input("我想加一个按钮"), "我想加一个按钮")

    def test_is_finalize_request(self):
        self.assertTrue(is_finalize_request("可以定稿了"))
        self.assertTrue(is_finalize_request("请总结需求"))
        self.assertTrue(is_finalize_request("生成需求"))
        self.assertFalse(is_finalize_request("我想加一个功能"))

    def test_is_prototype_request(self):
        self.assertTrue(is_prototype_request("看原型"))
        self.assertTrue(is_prototype_request("需要原型"))
        self.assertTrue(is_prototype_request("给我做个原型"))
        self.assertTrue(is_prototype_request("界面长什么样"))
        self.assertTrue(is_prototype_request("看拓扑"))
        self.assertTrue(is_prototype_request("部署拓扑"))
        self.assertFalse(is_prototype_request("我想加一个功能"))

    def test_dual_track_requirement_classification(self):
        # 1. 程序与 Agent 自动分类（DEPLOYMENT / SOFTWARE / HYBRID）
        rtype, reason = classify_requirement_type("帮我写一套 LaunchAgent 守护进程与 install.sh 部署脚本")
        self.assertEqual(rtype, "DEPLOYMENT")
        self.assertIn("部署", reason)

        rtype_soft, _ = classify_requirement_type("在页面上增加扫码借书按钮和列表筛选")
        self.assertEqual(rtype_soft, "SOFTWARE")

        rtype_hybrid, _ = classify_requirement_type("做一个扫码支付页面，并生成部署脚本和 docker-compose 守护配置")
        self.assertEqual(rtype_hybrid, "HYBRID")

        # 2. 从 Agent 回复文本中自动提取分类
        self.assertEqual(
            extract_agent_classified_type("• 🧭 需求类型：DEPLOYMENT (偏环境部署与脚本工程)"),
            "DEPLOYMENT",
        )
        self.assertEqual(
            extract_agent_classified_type("- **需求类型**：HYBRID (功能开发+环境部署)"),
            "HYBRID",
        )
        self.assertEqual(
            extract_agent_classified_type("• 🧭 需求类型：SOFTWARE (偏软件开发)"),
            "SOFTWARE",
        )

        # 3. 人工自然语言切换与 normalize_req_type
        self.assertEqual(detect_manual_type_override("这是环境部署需求"), "DEPLOYMENT")
        self.assertEqual(detect_manual_type_override("切为软件开发需求"), "SOFTWARE")
        self.assertEqual(detect_manual_type_override("切回自动分类"), "AUTO")
        self.assertEqual(normalize_req_type("deploy"), "DEPLOYMENT")
        self.assertEqual(normalize_req_type("软件开发"), "SOFTWARE")

    def test_build_req_prompt_new(self):
        prompt = build_req_prompt("做个定时功能", is_new=True)
        self.assertIn("新需求探讨开始", prompt)
        self.assertIn("req-guided-v5", prompt)
        self.assertIn("需求规模", prompt)
        self.assertIn("模块归属", prompt)
        self.assertIn("拼图 1：确认核心目标与使用场景", prompt)
        self.assertIn("看原型", prompt)

    def test_build_req_prompt_prototype(self):
        prompt = build_req_prompt("我想看原型", is_new=False)
        self.assertIn("用户指令：请求外部界面原型示例", prompt)
        self.assertIn("界面原型线框图", prompt)

    def test_build_req_prompt_finalize_software_and_deployment(self):
        prompt_soft = build_req_prompt("定稿", is_new=False, req_type="SOFTWARE", req_type_source="manual")
        self.assertIn("用户指令：请求需求定稿", prompt_soft)
        self.assertIn("软件需求规格说明", prompt_soft)
        self.assertIn("外部界面原型草图", prompt_soft)

        prompt_deploy = build_req_prompt("定稿", is_new=False, req_type="DEPLOYMENT", req_type_source="auto", inferred_type="DEPLOYMENT")
        self.assertIn("偏环境部署与脚本工程 (DEPLOYMENT)", prompt_deploy)
        self.assertIn("拟生成的部署脚本与配置文件清单", prompt_deploy)
        self.assertIn("幂等重跑验证", prompt_deploy)

    def test_build_srs_templates_all_types(self):
        for rtype in ("SOFTWARE", "DEPLOYMENT", "HYBRID"):
            tpl = build_srs_template(rtype)
            self.assertIn(f"**需求类型**：{rtype}", tpl)
            self.assertIn("## 6. 外部界面原型草图 (UI Wireframe)", tpl)



if __name__ == "__main__":
    unittest.main()
