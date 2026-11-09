import tempfile
import unittest
from pathlib import Path

from requirements import design_rules as dr


def facts(**kw):
    base = dict(reusable_verified_asset=False, changes_interface=False, changes_data_structure=False, has_ui=False, touches_real_env=False)
    base.update(kw)
    return base


class ComplexityTests(unittest.TestCase):
    def setUp(self):
        self.rules = dr.load_rules()

    def test_simple_needs_reusable_asset_and_nothing_else_changing(self):
        self.assertEqual(dr.classify(self.rules, facts(reusable_verified_asset=True)), "简单")

    def test_reusable_asset_alone_is_not_enough_when_anything_changes(self):
        for key in ("changes_interface", "changes_data_structure", "has_ui"):
            got = dr.classify(self.rules, facts(reusable_verified_asset=True, **{key: True}))
            self.assertEqual(got, "常规", key)

    def test_touching_real_environment_is_complex_even_with_reusable_asset(self):
        self.assertEqual(dr.classify(self.rules, facts(reusable_verified_asset=True, touches_real_env=True)), "复杂")

    def test_interface_and_data_structure_together_is_complex(self):
        self.assertEqual(dr.classify(self.rules, facts(changes_interface=True, changes_data_structure=True)), "复杂")

    def test_default_is_regular(self):
        self.assertEqual(dr.classify(self.rules, facts()), "常规")
        self.assertEqual(dr.classify(self.rules, facts(has_ui=True)), "常规")

    def test_missing_or_non_boolean_fact_is_rejected_not_guessed(self):
        bad = facts()
        del bad["has_ui"]
        with self.assertRaisesRegex(dr.RuleError, "has_ui"):
            dr.classify(self.rules, bad)
        with self.assertRaisesRegex(dr.RuleError, "has_ui"):
            dr.classify(self.rules, facts(has_ui="yes"))


class DeliverablesTests(unittest.TestCase):
    def setUp(self):
        self.rules = dr.load_rules()

    def test_backend_only_has_no_prototype_page_and_no_confirmation(self):
        plan = dr.plan(self.rules, "SOFTWARE", facts(changes_data_structure=True))
        self.assertIn("design.md", plan["deliverables"])
        self.assertIn("data-spec.md", plan["deliverables"])
        self.assertNotIn("prototype/index.html", plan["deliverables"])
        self.assertEqual(plan["confirmations"], [])

    def test_ui_software_needs_prototype_page_and_user_confirmation(self):
        plan = dr.plan(self.rules, "SOFTWARE", facts(has_ui=True, changes_data_structure=True))
        self.assertIn("prototype/index.html", plan["deliverables"])
        self.assertIn("data-spec.md", plan["deliverables"])
        self.assertTrue(any("原型" in c for c in plan["confirmations"]))

    def test_design_doc_is_always_delivered_even_for_simple(self):
        plan = dr.plan(self.rules, "SOFTWARE", facts(reusable_verified_asset=True))
        self.assertEqual(plan["complexity"], "简单")
        self.assertIn("design.md", plan["deliverables"])
        self.assertIn("简略", plan["design_detail"])

    def test_real_environment_requires_confirmation(self):
        plan = dr.plan(self.rules, "DEPLOYMENT", facts(touches_real_env=True))
        self.assertEqual(plan["complexity"], "复杂")
        self.assertTrue(any("真实环境" in c for c in plan["confirmations"]))

    def test_review_checklist_follows_type_not_complexity(self):
        simple = dr.plan(self.rules, "DEPLOYMENT", facts(reusable_verified_asset=True))
        regular = dr.plan(self.rules, "DEPLOYMENT", facts(changes_interface=True))
        self.assertEqual(simple["review"], regular["review"])
        self.assertTrue(any("回滚" in item for item in simple["review"]))
        sw = dr.plan(self.rules, "SOFTWARE", facts())
        self.assertFalse(any("回滚" in item for item in sw["review"]))

    def test_hybrid_unions_parts_and_adds_interface_check(self):
        plan = dr.plan(self.rules, "HYBRID", facts(), parts=["SOFTWARE", "DEPLOYMENT"])
        joined = " ".join(plan["review"])
        for needle in ("需求原文逐条", "回滚", "之间的接口"):
            self.assertIn(needle, joined)
        self.assertNotIn("断线", joined)

    def test_hybrid_without_parts_is_rejected(self):
        with self.assertRaisesRegex(dr.RuleError, "组成部分"):
            dr.plan(self.rules, "HYBRID", facts())
        with self.assertRaisesRegex(dr.RuleError, "HYBRID"):
            dr.plan(self.rules, "HYBRID", facts(), parts=["HYBRID"])

    def test_unknown_type_is_rejected(self):
        with self.assertRaisesRegex(dr.RuleError, "类型"):
            dr.plan(self.rules, "TOASTER", facts())


class RuleFileTests(unittest.TestCase):
    def write(self, body):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p = Path(tmp.name) / "r.toml"
        p.write_text(body, encoding="utf-8")
        return p

    def test_rule_referencing_unknown_fact_is_rejected_at_load(self):
        body = Path(dr.RULES).read_text(encoding="utf-8").replace('complex_if_any = ["touches_real_env"]', 'complex_if_any = ["no_such_fact"]')
        with self.assertRaisesRegex(dr.RuleError, "no_such_fact"):
            dr.load_rules(self.write(body))

    def test_missing_level_definition_is_rejected_at_load(self):
        body = Path(dr.RULES).read_text(encoding="utf-8").replace('[levels."复杂"]', '[levels."别的"]')
        with self.assertRaisesRegex(dr.RuleError, "复杂"):
            dr.load_rules(self.write(body))


if __name__ == "__main__":
    unittest.main()
