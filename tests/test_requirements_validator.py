import os
import re
import unittest
from requirements.flow import build_srs_template
from requirements.validator import inspect_srs_document, validate_requirement_spec


VALID_SPEC_SAMPLE = """# 软件需求规格说明书（草案）

## 1. 需求标识与元数据
- **需求编号**：REQ-ORDER-PAY-20261107
- **需求名称**：扫码支付集成
- **提出人**：张三
- **分析师**：AutoDev (req-guided-v4)
- **归属项目**：/tmp/project
- **定稿时间**：2026-11-07 12:00:00

## 2. 架构拓扑与近期关联
- 📂 **功能层级归属**：属于 order 模块下的结算子功能。
- 🔗 **近期功能关联**：与近期做的 REQ-ORDER-CART 强关联，复用购物车结算实体。

## 3. 核心背景与业务目标 (Why & What)
- **业务背景**：用户在收银台结账需要快速完成付款。
- **业务目标**：3 秒内完成扫码唤起与支付确认。

## 4. 业务用例与核心流程 (Scope)
1. 顾客出示二维码；
2. 收银员扫描二维码；
3. 系统扣款成功。

## 5. 明确非目标与边界 (Non-goals)
- ❌ 本期不接入海外信用卡刷卡通道。
- ❌ 暂不支持先享后付分期业务。

## 6. 外部界面原型草图 (UI Wireframe)
```text
┌────────────────────────┐
│ 扫码收款台              │
├────────────────────────┤
│ 请扫描顾客付款码：     │
│ [ 📷 扫码中... ]        │
├────────────────────────┤
│ [ 确认收款 ] [ 取消 ]   │
└────────────────────────┘
```

## 7. 业务约束与前置依赖
- 必须接入支付网关。

## 8. 可量化验收标准清单 (Acceptance Criteria)
- 场景 1（正常扣款）：Given 余额充足 When 扫码 Then 成功扣款。
- 场景 2（余额不足）：Given 余额为零 When 扫码 Then 提示余额不足。

## 9. 下游架构设计关注点
- 幂等性控制与分布式事务补偿。
"""


class TestRequirementsValidator(unittest.TestCase):
    def test_valid_spec(self):
        res = validate_requirement_spec(VALID_SPEC_SAMPLE)
        self.assertTrue(res.is_valid, f"验证失败: {res.errors}")
        self.assertEqual(len(res.errors), 0)

    def test_valid_spec_with_scale_and_relations(self):
        new_sample = VALID_SPEC_SAMPLE.replace(
            "## 2. 架构拓扑与近期关联\n- 📂 **功能层级归属**：属于 order 模块下的结算子功能。\n- 🔗 **近期功能关联**：与近期做的 REQ-ORDER-CART 强关联，复用购物车结算实体。",
            "## 2. 需求规模分类与需求关联网络\n- 🏷️ **需求规模类别**：标准功能 (Feature)\n- 📂 **模块归属**：order 模块\n- 🔗 **需求关联网络**：Parent: None; Depends-on: REQ-CART-01; Relates-to: REQ-PAY-GW",
        )
        res = validate_requirement_spec(new_sample)
        self.assertTrue(res.is_valid, f"验证失败: {res.errors}")

    def test_missing_sections(self):
        # 缺少非目标和原型
        broken = VALID_SPEC_SAMPLE.replace("## 5. 明确非目标与边界 (Non-goals)", "## 5. 其他说明")
        res = validate_requirement_spec(broken)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("RULE-02" in err for err in res.errors))

    def test_missing_topology_dimensions(self):
        # 缺少近期功能关联
        broken = VALID_SPEC_SAMPLE.replace("🔗 **近期功能关联**", "相关描述")
        res = validate_requirement_spec(broken)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("RULE-03" in err for err in res.errors))

    def test_missing_wireframe(self):
        # 原型节没有 ```text
        broken = VALID_SPEC_SAMPLE.replace("```text", "```")
        res = validate_requirement_spec(broken)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("RULE-06" in err for err in res.errors))

    def test_forbidden_tech_overstepping(self):
        # 包含 SQL 语句
        broken = VALID_SPEC_SAMPLE + "\n数据库设计：CREATE TABLE orders (id int);"
        res = validate_requirement_spec(broken)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("RULE-08" in err for err in res.errors))

    def test_gold_standard_sample_in_doc_is_valid(self):
        # 读取实现说明书中的黄金范本，确保文档范本 100% 通过校验器
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        doc_path = os.path.join(root_dir, "docs", "modules", "requirements", "feishu-requirement-bot.md")
        with open(doc_path, "r", encoding="utf-8") as f:
            doc_text = f.read()
        match = re.search(r"````markdown\n(.*?)\n````", doc_text, re.DOTALL)
        self.assertIsNotNone(match, "未能在 feishu-requirement-bot.md 中找到 ````markdown 黄金范本")
        sample_md = match.group(1)
        res = validate_requirement_spec(sample_md)
        self.assertTrue(res.is_valid, f"文档中的黄金范本未通过校验器: {res.errors}")

    def test_doc_relative_links_exist(self):
        # 检查核心文档中的所有本地相对链接是否真实存在
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        doc_files = [
            os.path.join(root_dir, "docs", "specs", "REQUIREMENT_SPEC_STANDARD.md"),
            os.path.join(root_dir, "docs", "modules", "requirements", "README.md"),
            os.path.join(root_dir, "docs", "modules", "requirements", "feishu-requirement-bot.md"),
        ]
        for doc_file in doc_files:
            self.assertTrue(os.path.exists(doc_file), f"核心文档不存在: {doc_file}")
            with open(doc_file, "r", encoding="utf-8") as f:
                text = f.read()
            for m in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
                link = m.group(1).split("#")[0].strip()
                if not link or link.startswith(("http://", "https://", "mailto:", "file://")):
                    continue
                target_path = os.path.normpath(os.path.join(os.path.dirname(doc_file), link))
                self.assertTrue(
                    os.path.exists(target_path),
                    f"文档 {doc_file} 中的相对链接失效: '{link}' -> {target_path}",
                )


    def test_deployment_and_hybrid_templates_pass_validator(self):
        for rtype in ("SOFTWARE", "DEPLOYMENT", "HARDWARE", "HYBRID"):
            tpl = build_srs_template(rtype)
            res = validate_requirement_spec(tpl)
            self.assertTrue(res.is_valid, f"{rtype} 模板未通过校验: {res.errors}")
            inspected = inspect_srs_document(tpl)
            self.assertEqual(inspected["req_type"], rtype)
            if rtype == "DEPLOYMENT":
                self.assertTrue(len(inspected["deliverables"]) >= 2)

        # 验证缺少幂等/探针验收标准的 DEPLOYMENT 文档会被 RULE-07 拦截
        deploy_tpl = build_srs_template("DEPLOYMENT")
        broken_deploy = re.sub(
            r"## 8\. 可量化验收标准清单.*?(?=## 9\.)",
            "## 8. 可量化验收标准清单 (Acceptance Criteria)\n- 场景 1：Given 用户打开页面 When 点击按钮 Then 显示欢迎语。\n\n",
            deploy_tpl,
            flags=re.S,
        )
        res_broken = validate_requirement_spec(broken_deploy)
        self.assertFalse(res_broken.is_valid)
        self.assertTrue(any("RULE-07" in e and "DEPLOYMENT" in e for e in res_broken.errors))

        # 验证缺少设备/重连/模拟验收标准的 HARDWARE 文档会被 RULE-07 拦截
        hw_tpl = build_srs_template("HARDWARE")
        broken_hw = re.sub(
            r"## 8\. 可量化验收标准清单.*?(?=## 9\.)",
            "## 8. 可量化验收标准清单 (Acceptance Criteria)\n- 场景 1：Given 用户打开页面 When 点击按钮 Then 显示欢迎语。\n\n",
            hw_tpl,
            flags=re.S,
        )
        res_broken_hw = validate_requirement_spec(broken_hw)
        self.assertFalse(res_broken_hw.is_valid)
        self.assertTrue(any("RULE-07" in e and "HARDWARE" in e for e in res_broken_hw.errors))

    def test_rule_00_identity_validation(self):
        # 缺少归属项目
        no_project = VALID_SPEC_SAMPLE.replace("- **归属项目**：/tmp/project", "")
        res_no_proj = validate_requirement_spec(no_project)
        self.assertFalse(res_no_proj.is_valid)
        self.assertTrue(any("RULE-00" in e and "项目身份" in e for e in res_no_proj.errors))

        # 缺少需求编号
        no_id = VALID_SPEC_SAMPLE.replace("- **需求编号**：REQ-ORDER-PAY-20261107", "")
        res_no_id = validate_requirement_spec(no_id)
        self.assertFalse(res_no_id.is_valid)
        self.assertTrue(any("RULE-00" in e and "需求身份" in e for e in res_no_id.errors))

        # 验证 extract_srs_metadata 正常提取 id 与 project
        inspected = inspect_srs_document(VALID_SPEC_SAMPLE)
        self.assertEqual(inspected["metadata"]["id"], "REQ-ORDER-PAY-20261107")
        self.assertEqual(inspected["metadata"]["project"], "/tmp/project")


if __name__ == "__main__":
    unittest.main()
