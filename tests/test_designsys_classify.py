import tempfile
import unittest
from pathlib import Path

from designsys import classify as c


def case(features=(), risks=(), clear=True, multi_module=False):
    return {"features": set(features), "risks": set(risks), "requirements_clear": clear, "multi_module": multi_module}


class ClassifyTests(unittest.TestCase):
    def setUp(self):
        self.rules = c.load_rules()

    def level(self, **kw):
        return c.classify(self.rules, case(**kw))["level"]

    def test_nothing_special_and_clear_is_d0(self):
        self.assertEqual(self.level(), "D0")

    def test_unclear_requirements_are_never_d0(self):
        self.assertEqual(self.level(clear=False), "D1")

    def test_single_persistence_or_api_is_d1(self):
        for f in ("persistence", "api", "file_upload", "ai", "async_task", "external_integration"):
            self.assertEqual(self.level(features=[f]), "D1", f)

    def test_ui_auth_or_sensitive_data_is_d2(self):
        for f in ("ui", "auth", "sensitive_data"):
            self.assertEqual(self.level(features=[f]), "D2", f)

    def test_persistence_plus_api_together_is_d2(self):
        self.assertEqual(self.level(features=["persistence", "api"]), "D2")

    def test_multi_module_is_d2(self):
        self.assertEqual(self.level(multi_module=True), "D2")

    def test_cross_tenant_and_high_impact_are_d2_even_with_simple_ui(self):
        for r in ("cross_tenant", "high_impact_operation"):
            self.assertEqual(self.level(risks=[r]), "D2", r)

    def test_real_env_hardware_and_high_risk_are_d3(self):
        self.assertEqual(self.level(features=["real_env"]), "D3")
        self.assertEqual(self.level(features=["hardware_device"]), "D3")
        self.assertEqual(self.level(risks=["tech_uncertainty"]), "D3")
        self.assertEqual(self.level(risks=["high_risk_business"]), "D3")

    def test_highest_matching_level_wins(self):
        self.assertEqual(self.level(features=["ui", "real_env", "persistence"]), "D3")

    def test_security_override_applies_even_at_d0_or_d1(self):
        res = c.classify(self.rules, case(features=["persistence"]))
        self.assertFalse(res["security_override"])
        res = c.classify(self.rules, case(features=["auth"]))
        self.assertTrue(res["security_override"])
        res = c.classify(self.rules, case(risks=["cross_tenant"]))
        self.assertTrue(res["security_override"])

    def test_result_explains_why(self):
        res = c.classify(self.rules, case(features=["ui", "persistence"]))
        self.assertEqual(res["level"], "D2")
        self.assertTrue(any("ui" in r for r in res["reasons"]))

    def test_d0_reason_says_why_design_is_skipped(self):
        res = c.classify(self.rules, case())
        self.assertTrue(any("跳过" in r for r in res["reasons"]))

    def test_unknown_feature_or_risk_is_rejected_not_ignored(self):
        with self.assertRaisesRegex(c.ClassifyError, "teleporter"):
            c.classify(self.rules, case(features=["teleporter"]))
        with self.assertRaisesRegex(c.ClassifyError, "lava"):
            c.classify(self.rules, case(risks=["lava"]))

    def test_non_boolean_flags_are_rejected(self):
        bad = case()
        bad["requirements_clear"] = "yes"
        with self.assertRaisesRegex(c.ClassifyError, "requirements_clear"):
            c.classify(self.rules, bad)


class RuleFileTests(unittest.TestCase):
    def write(self, body):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p = Path(tmp.name) / "r.toml"
        p.write_text(body, encoding="utf-8")
        return p

    def test_rule_naming_an_unregistered_feature_is_rejected_at_load(self):
        body = Path(c.RULES).read_text(encoding="utf-8").replace('any_features = ["real_env", "hardware_device"]', 'any_features = ["nope"]')
        with self.assertRaisesRegex(c.ClassifyError, "nope"):
            c.load_rules(self.write(body))

    def test_missing_level_is_rejected_at_load(self):
        body = Path(c.RULES).read_text(encoding="utf-8").replace("[levels.D3]", "[levels.DX]")
        with self.assertRaisesRegex(c.ClassifyError, "D3"):
            c.load_rules(self.write(body))


if __name__ == "__main__":
    unittest.main()
