import tempfile
import unittest
from pathlib import Path

from designsys import rules as r


def case(features=(), risks=(), level="D1"):
    return {"features": set(features), "risks": set(risks), "level": level}


def ids(lib, **kw):
    return {x["rule_id"] for x in r.select(lib, case(**kw))["applicable"]}


class SelectTests(unittest.TestCase):
    def setUp(self):
        self.lib = r.load_library()

    def test_library_has_every_v21_baseline_rule(self):
        sec = ["SEC-00%d" % i for i in range(1, 9)]
        data = ["DATA-00%d" % i for i in range(1, 7)]
        want = set(sec + data + ["API-001", "ERR-001", "CODE-001", "UI-001"])
        self.assertEqual({x["rule_id"] for x in self.lib["rules"]}, want)

    def test_sec001_applies_to_every_project_even_d0(self):
        self.assertIn("SEC-001", ids(self.lib, level="D0"))

    def test_feature_triggers_the_matching_rules(self):
        pairs = [("file_upload", "SEC-006"), ("ai", "SEC-007"), ("api", "API-001"), ("ui", "UI-001"), ("persistence", "DATA-001"), ("sensitive_data", "SEC-004")]
        for feature, rid in pairs:
            self.assertIn(rid, ids(self.lib, features=[feature]), feature)

    def test_risk_triggers_the_matching_rules(self):
        self.assertIn("SEC-005", ids(self.lib, risks=["cross_tenant"]))
        self.assertIn("SEC-008", ids(self.lib, risks=["high_impact_operation"]))

    def test_untriggered_rules_are_not_selected(self):
        got = ids(self.lib, features=["api"])
        for rid in ("SEC-006", "SEC-007", "DATA-001", "UI-001"):
            self.assertNotIn(rid, got, rid)

    def test_content_based_rules_are_deferred_not_guessed(self):
        res = r.select(self.lib, case(features=["persistence"]))
        deferred = {x["rule_id"] for x in res["deferred"]}
        applicable = {x["rule_id"] for x in res["applicable"]}
        for rid in ("DATA-002", "DATA-003", "DATA-004"):
            self.assertIn(rid, deferred, rid)
            self.assertNotIn(rid, applicable, rid)

    def test_deferred_rules_only_appear_when_their_artifact_is_in_play(self):
        res = r.select(self.lib, case(features=["api"]))
        self.assertNotIn("DATA-002", {x["rule_id"] for x in res["deferred"]})

    def test_each_selected_rule_explains_why(self):
        res = r.select(self.lib, case(features=["file_upload"], risks=["cross_tenant"]))
        for x in res["applicable"]:
            self.assertTrue(x["why"], x["rule_id"])

    def test_selection_is_deterministic_and_sorted(self):
        a = r.select(self.lib, case(features=["api", "ui"], risks=["cross_tenant"]))
        b = r.select(self.lib, case(features=["ui", "api"], risks=["cross_tenant"]))
        self.assertEqual(a, b)
        order = [x["rule_id"] for x in a["applicable"]]
        self.assertEqual(order, sorted(order))

    def test_unknown_feature_is_rejected_not_ignored(self):
        with self.assertRaisesRegex(r.RuleLibraryError, "teleporter"):
            r.select(self.lib, case(features=["teleporter"]))


class SecurityOverrideTests(unittest.TestCase):
    def setUp(self):
        self.lib = r.load_library()

    def test_override_forces_security_rules_even_at_d0(self):
        res = r.select(self.lib, case(features=["auth"], level="D0"), security_override=True)
        got = {x["rule_id"] for x in res["applicable"]}
        for rid in ("SEC-001", "SEC-002"):
            self.assertIn(rid, got, rid)
        self.assertNotIn("SEC-004", got, "认证只关联 SEC-002，与敏感数据保护无关（V2.1 3.2 节：启用“相关”安全规则）")

    def test_without_override_a_d0_project_gets_only_unconditional_rules(self):
        res = r.select(self.lib, case(level="D0"))
        got = {x["rule_id"] for x in res["applicable"]}
        self.assertEqual(got, {"SEC-001", "CODE-001"})


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.lib = r.load_library()

    def test_coverage_denominator_is_all_applicable_rules(self):
        res = r.select(self.lib, case(features=["api", "file_upload"]))
        names = [x["rule_id"] for x in res["applicable"]]
        cov = r.coverage(res, names[:-1])
        self.assertEqual(cov["denominator"], len(names))
        self.assertEqual(cov["bound"], len(names) - 1)
        self.assertFalse(cov["complete"])
        self.assertEqual(len(cov["missing"]), 1)

    def test_full_binding_is_complete(self):
        res = r.select(self.lib, case(features=["api"]))
        cov = r.coverage(res, [x["rule_id"] for x in res["applicable"]])
        self.assertTrue(cov["complete"])

    def test_binding_unknown_or_inapplicable_rule_does_not_inflate_coverage(self):
        res = r.select(self.lib, case(features=["api"]))
        cov = r.coverage(res, ["SEC-006", "NOPE-999"])
        self.assertEqual(cov["bound"], 0)
        self.assertEqual(sorted(cov["ignored"]), ["NOPE-999", "SEC-006"])

    def test_zero_denominator_is_not_applicable_not_one_hundred_percent(self):
        empty = dict(applicable=[], deferred=[])
        cov = r.coverage(empty, [])
        self.assertIsNone(cov["ratio"])
        self.assertEqual(cov["status"], "not_applicable")


class OverrideScopeTests(unittest.TestCase):
    def setUp(self):
        self.lib = r.load_library()

    def sec_ids(self, **kw):
        res = r.select(self.lib, case(**kw), security_override=True)
        return {x["rule_id"] for x in res["applicable"] if x["rule_id"].startswith("SEC-")}

    def test_override_does_not_pull_in_unrelated_security_rules(self):
        got = self.sec_ids(features=["ui"], risks=["cross_tenant"], level="D2")
        self.assertIn("SEC-005", got)
        for rid in ("SEC-006", "SEC-007", "SEC-008"):
            self.assertNotIn(rid, got, rid + " 与该项目无关，不应被覆盖强制拉入")

    def test_override_at_d0_with_auth_adds_only_the_authorization_rule(self):
        got = self.sec_ids(features=["auth"], level="D0")
        self.assertEqual(got, {"SEC-001", "SEC-002"})

    def test_override_with_sensitive_data_adds_only_the_data_protection_rule(self):
        got = self.sec_ids(features=["sensitive_data"], level="D0")
        self.assertEqual(got, {"SEC-001", "SEC-004"})

    def test_override_with_high_impact_adds_only_the_audit_rule(self):
        got = self.sec_ids(risks=["high_impact_operation"], level="D0")
        self.assertEqual(got, {"SEC-001", "SEC-008"})


class LibraryFileTests(unittest.TestCase):
    def write(self, body):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p = Path(tmp.name) / "lib.toml"
        p.write_text(body, encoding="utf-8")
        return p

    def test_duplicate_rule_id_is_rejected_at_load(self):
        body = Path(r.LIBRARY).read_text(encoding="utf-8")
        extra = "\n[[rules]]\nrule_id = \"SEC-001\"\nversion = \"1.0.0\"\nname = \"x\"\ncategory = \"security\"\nmaturity = \"R1\"\nseverity = \"blocking\"\nalways = true\nrequirement = \"x\"\nverification = \"x\"\n"
        dup = body + extra
        with self.assertRaisesRegex(r.RuleLibraryError, "重复"):
            r.load_library(self.write(dup))

    def test_rule_naming_an_unregistered_feature_is_rejected_at_load(self):
        body = Path(r.LIBRARY).read_text(encoding="utf-8")
        bad = body.replace('features = ["file_upload"]', 'features = ["nope"]')
        with self.assertRaisesRegex(r.RuleLibraryError, "nope"):
            r.load_library(self.write(bad))

    def test_rule_without_required_field_is_rejected_at_load(self):
        body = Path(r.LIBRARY).read_text(encoding="utf-8")
        bad = body.replace("requirement = ", "requirementX = ", 1)
        with self.assertRaisesRegex(r.RuleLibraryError, "requirement"):
            r.load_library(self.write(bad))


if __name__ == "__main__":
    unittest.main()
