import json
import tempfile
import unittest
from pathlib import Path

from designsys import rules as rl, validate as v


LIB = rl.load_library()
APPLICABLE = [x["rule_id"] for x in rl.select(LIB, dict(features={"api", "persistence"}, risks=set(), level="D2"))["applicable"]]


def plan(**kw):
    base = dict(schema_version="1.0", project_type="web_application", design_level="D2", features=["api", "persistence"], risks=[], required_artifacts=["A01", "A04", "A05", "A07", "A08"], mandatory_rules=list(APPLICABLE), classification_rationale=["有持久化与接口"], open_questions=[])
    base.update(kw)
    return base


def technical():
    mod = dict(id="M1", responsibility="文档访问", inputs=["请求"], outputs=["文档"], dependencies=[], failure_handling="返回 404")
    return dict(schema_version="1.0", modules=[mod], decisions=[], risks_to_verify=[])


def data():
    field = dict(name="id", type="string", nullable=False)
    ent = dict(id="Document", primary_key=["id"], fields=[field])
    return dict(schema_version="1.0", entities=[ent])


def security():
    rules = []
    for rid in APPLICABLE:
        rules.append(dict(rule_id=rid, reason="适用", targets=["system"], design_refs=["artifacts/technical.json"], implementation_tasks=["TASK-1"], verification_ids=["T-" + rid]))
    return dict(schema_version="1.0", applicable_rules=rules, not_applicable=[])


def handoff(**kw):
    task = dict(task_id="TASK-1", title="实现", requirement_ids=["REQ-1"], design_refs=["artifacts/technical.json", "artifacts/data.json"], mandatory_rule_ids=list(APPLICABLE), acceptance_ids=["T-" + x for x in APPLICABLE], dependencies=[])
    base = dict(schema_version="1.0", design_version="1.0.0", requirements_baseline="B1", tasks=[task], blocking_issues=[], ready_for_coding=True)
    base.update(kw)
    return base


def write_pack(root, **over):
    docs = {
        "plan.json": plan(), "artifacts/technical.json": technical(), "artifacts/data.json": data(),
        "artifacts/security.json": security(), "handoff.json": handoff(),
    }
    docs.update(over)
    for rel, body in docs.items():
        if body is None:
            continue
        p = Path(root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
        p.write_text(text, encoding="utf-8")


class PackTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def run_pack(self, **over):
        write_pack(self.root, **over)
        return v.validate_pack(self.root)

    def failed(self, report, rule_id=None):
        rows = [x for x in report["results"] if x["status"] == "failed"]
        if rule_id:
            rows = [x for x in rows if x["rule_id"] == rule_id]
        return rows


class HappyPathTests(PackTestCase):
    def test_a_consistent_pack_is_ready_for_coding(self):
        report = self.run_pack()
        self.assertEqual(self.failed(report), [])
        self.assertTrue(report["ready_for_coding"], report["blocking"])

    def test_every_result_follows_the_unified_contract(self):
        report = self.run_pack()
        keys = {"validator_id", "validator_version", "rule_id", "rule_version", "artifact", "status", "severity", "location", "message", "evidence", "repair_hint"}
        for row in report["results"]:
            self.assertEqual(set(row), keys)
            self.assertIn(row["status"], ("passed", "failed", "not_applicable", "error"))

    def test_not_applicable_results_state_why(self):
        report = self.run_pack()
        for row in report["results"]:
            if row["status"] == "not_applicable":
                self.assertTrue(row["message"], row["rule_id"])


class V1FileTests(PackTestCase):
    def test_missing_required_file_fails_and_blocks(self):
        report = self.run_pack(**{"artifacts/security.json": None})
        rows = self.failed(report, "V1-FILE")
        self.assertTrue(rows)
        self.assertFalse(report["ready_for_coding"])

    def test_unparseable_json_is_reported_not_crashed(self):
        report = self.run_pack(**{"handoff.json": "{not json"})
        self.assertTrue(self.failed(report, "V1-PARSE"))
        self.assertFalse(report["ready_for_coding"])

    def test_schema_violation_is_reported_with_location(self):
        bad = plan(design_level="D9")
        report = self.run_pack(**{"plan.json": bad})
        rows = self.failed(report, "V1-SCHEMA")
        self.assertTrue(rows)
        self.assertTrue(any("design_level" in x["location"] for x in rows))

    def test_artifact_not_required_by_the_plan_is_not_demanded(self):
        api_only = [x["rule_id"] for x in rl.select(LIB, dict(features={"api"}, risks=set(), level="D1"))["applicable"]]
        only = plan(design_level="D1", features=["api"], required_artifacts=["A01", "A04", "A07", "A08"], mandatory_rules=api_only)
        rules = [r for r in security()["applicable_rules"] if r["rule_id"] in api_only]
        sec = dict(security(), applicable_rules=rules)
        task = dict(handoff()["tasks"][0], mandatory_rule_ids=api_only, acceptance_ids=["T-" + x for x in api_only], design_refs=["artifacts/technical.json"])
        report = self.run_pack(**{"plan.json": only, "artifacts/data.json": None, "artifacts/security.json": sec, "handoff.json": handoff(tasks=[task])})
        self.assertEqual(self.failed(report, "V1-FILE"), [])


class V2ReferenceTests(PackTestCase):
    def test_task_citing_a_missing_design_file_fails(self):
        task = dict(handoff()["tasks"][0], design_refs=["artifacts/nowhere.json"])
        report = self.run_pack(**{"handoff.json": handoff(tasks=[task])})
        self.assertTrue(self.failed(report, "V2-REF"))
        self.assertFalse(report["ready_for_coding"])

    def test_task_depending_on_an_unknown_task_fails(self):
        task = dict(handoff()["tasks"][0], dependencies=["TASK-99"])
        report = self.run_pack(**{"handoff.json": handoff(tasks=[task])})
        self.assertTrue(self.failed(report, "V2-REF"))

    def test_task_citing_a_rule_not_in_the_library_fails(self):
        task = dict(handoff()["tasks"][0], mandatory_rule_ids=APPLICABLE + ["NOPE-999"])
        report = self.run_pack(**{"handoff.json": handoff(tasks=[task])})
        self.assertTrue(self.failed(report, "V2-REF"))

    def test_security_rule_pointing_at_an_unknown_task_fails(self):
        sec = security()
        sec["applicable_rules"][0]["implementation_tasks"] = ["TASK-404"]
        report = self.run_pack(**{"artifacts/security.json": sec})
        self.assertTrue(self.failed(report, "V2-REF"))

    def test_duplicate_task_ids_fail(self):
        t = handoff()["tasks"][0]
        report = self.run_pack(**{"handoff.json": handoff(tasks=[t, dict(t)])})
        self.assertTrue(self.failed(report, "V2-REF"))


class RuleCoverageTests(PackTestCase):
    def test_plan_may_not_drop_a_rule_the_library_says_applies(self):
        fewer = [x for x in APPLICABLE if x != "SEC-001"]
        report = self.run_pack(**{"plan.json": plan(mandatory_rules=fewer)})
        rows = self.failed(report, "V2-RULES")
        self.assertTrue(rows)
        self.assertTrue(any("SEC-001" in x["message"] for x in rows))
        self.assertFalse(report["ready_for_coding"])

    def test_plan_may_not_add_a_rule_that_does_not_apply(self):
        report = self.run_pack(**{"plan.json": plan(mandatory_rules=APPLICABLE + ["SEC-006"])})
        self.assertTrue(self.failed(report, "V2-RULES"))

    def test_a_rule_applying_but_not_bound_to_any_task_fails_coverage(self):
        task = dict(handoff()["tasks"][0], mandatory_rule_ids=[x for x in APPLICABLE if x != "SEC-001"], acceptance_ids=["T-" + x for x in APPLICABLE if x != "SEC-001"])
        report = self.run_pack(**{"handoff.json": handoff(tasks=[task])})
        rows = self.failed(report, "V2-COVERAGE")
        self.assertTrue(rows)
        self.assertIn("SEC-001", rows[0]["evidence"]["missing"])

    def test_coverage_is_reported_with_the_real_denominator(self):
        report = self.run_pack()
        cov = report["metrics"]["mandatory_rule_coverage"]
        self.assertEqual(cov["denominator"], len(APPLICABLE))
        self.assertEqual(cov["bound"], len(APPLICABLE))

    def test_security_json_must_account_for_every_applicable_rule_or_say_why_not(self):
        sec = security()
        sec["applicable_rules"] = [r for r in sec["applicable_rules"] if r["rule_id"] != "SEC-001"]
        report = self.run_pack(**{"artifacts/security.json": sec})
        rows = self.failed(report, "V2-SECURITY")
        self.assertTrue(rows)

    def test_security_rule_may_be_marked_not_applicable_only_with_a_reason(self):
        sec = security()
        sec["applicable_rules"] = [r for r in sec["applicable_rules"] if r["rule_id"] != "SEC-001"]
        sec["not_applicable"] = [dict(rule_id="SEC-001", reason="")]
        report = self.run_pack(**{"artifacts/security.json": sec})
        self.assertTrue(self.failed(report))


class V3ConsistencyTests(PackTestCase):
    def isolation_pack(self):
        ids = [x["rule_id"] for x in rl.select(LIB, dict(features={"api", "persistence"}, risks={"cross_tenant"}, level="D2"))["applicable"]]
        rules = [dict(rule_id=i, reason="适用", targets=["system"], design_refs=["artifacts/technical.json"], implementation_tasks=["TASK-1"], verification_ids=["T-" + i]) for i in ids]
        sec = dict(schema_version="1.0", applicable_rules=rules, not_applicable=[])
        task = dict(handoff()["tasks"][0], mandatory_rule_ids=ids, acceptance_ids=["T-" + i for i in ids])
        return ids, dict(plan=plan(risks=["cross_tenant"], mandatory_rules=ids), sec=sec, handoff=handoff(tasks=[task]))

    def test_isolation_rule_with_a_project_owner_field_passes(self):
        ids, docs = self.isolation_pack()
        ent = dict(id="Document", primary_key=["id"], fields=[dict(name="id", type="string", nullable=False), dict(name="project_id", type="string", nullable=False)])
        report = self.run_pack(**{"plan.json": docs["plan"], "artifacts/security.json": docs["sec"], "handoff.json": docs["handoff"], "artifacts/data.json": dict(schema_version="1.0", entities=[ent])})
        self.assertEqual(self.failed(report, "V3-ISOLATION"), [], report["blocking"])

    def test_isolation_rule_without_any_owner_field_fails(self):
        ids, docs = self.isolation_pack()
        report = self.run_pack(**{"plan.json": docs["plan"], "artifacts/security.json": docs["sec"], "handoff.json": docs["handoff"]})
        rows = self.failed(report, "V3-ISOLATION")
        self.assertTrue(rows)
        self.assertIn("Document", rows[0]["location"])
        self.assertFalse(report["ready_for_coding"])

    def test_isolation_rule_not_in_play_makes_the_check_not_applicable(self):
        report = self.run_pack()
        rows = [x for x in report["results"] if x["rule_id"] == "V3-ISOLATION"]
        self.assertTrue(rows)
        self.assertEqual({x["status"] for x in rows}, {"not_applicable"})

    def test_isolation_rule_not_bound_to_a_task_fails(self):
        ids, docs = self.isolation_pack()
        ent = dict(id="Document", primary_key=["id"], fields=[dict(name="id", type="string", nullable=False), dict(name="project_id", type="string", nullable=False)])
        task = dict(docs["handoff"]["tasks"][0], mandatory_rule_ids=[i for i in ids if i != "SEC-005"], acceptance_ids=["T-" + i for i in ids if i != "SEC-005"])
        report = self.run_pack(**{"plan.json": docs["plan"], "artifacts/security.json": docs["sec"], "handoff.json": handoff(tasks=[task]), "artifacts/data.json": dict(schema_version="1.0", entities=[ent])})
        self.assertTrue(self.failed(report, "V2-COVERAGE"))


class ErrorIsNeverPassTests(PackTestCase):
    def test_a_crashing_check_becomes_error_and_blocks_acceptance(self):
        write_pack(self.root)
        original = v.CHECKS[-1]
        def boom(pack, ctx):
            raise RuntimeError("校验器自己出错了")
        v.CHECKS[-1] = (original[0], boom)
        self.addCleanup(lambda: v.CHECKS.__setitem__(-1, original))
        report = v.validate_pack(self.root)
        errors = [x for x in report["results"] if x["status"] == "error"]
        self.assertTrue(errors)
        self.assertFalse(report["ready_for_coding"])
        self.assertIn("校验器自己出错了", errors[0]["message"])

    def test_error_is_not_counted_as_passed_in_the_metrics(self):
        write_pack(self.root)
        original = v.CHECKS[-1]
        v.CHECKS[-1] = (original[0], lambda pack, ctx: 1 / 0)
        self.addCleanup(lambda: v.CHECKS.__setitem__(-1, original))
        report = v.validate_pack(self.root)
        self.assertGreaterEqual(report["metrics"]["checks_error"], 1)


class BlockingIssuesTests(PackTestCase):
    def test_declared_blocking_issues_stop_ready_for_coding_even_if_everything_else_passes(self):
        report = self.run_pack(**{"handoff.json": handoff(blocking_issues=["业务规则 X 未确认"])})
        self.assertFalse(report["ready_for_coding"])
        self.assertTrue(any("业务规则 X" in b for b in report["blocking"]))

    def test_handoff_claiming_ready_while_validation_fails_is_overruled(self):
        task = dict(handoff()["tasks"][0], design_refs=["artifacts/nowhere.json"])
        report = self.run_pack(**{"handoff.json": handoff(tasks=[task], ready_for_coding=True)})
        self.assertFalse(report["ready_for_coding"])

    def test_open_questions_in_the_plan_are_surfaced_not_hidden(self):
        report = self.run_pack(**{"plan.json": plan(open_questions=["谁来审批？"])})
        self.assertIn("谁来审批？", report["open_questions"])


class MetricsTests(PackTestCase):
    def test_required_artifact_completeness_is_computed_from_the_plan(self):
        report = self.run_pack()
        m = report["metrics"]["required_artifacts"]
        self.assertEqual(m["denominator"], len(plan()["required_artifacts"]))
        self.assertEqual(m["passed"], m["denominator"])

    def test_a_missing_required_artifact_lowers_the_completeness_ratio(self):
        report = self.run_pack(**{"artifacts/data.json": None})
        m = report["metrics"]["required_artifacts"]
        self.assertLess(m["passed"], m["denominator"])
        self.assertEqual(m["status"], "incomplete")

    def test_zero_denominator_is_not_reported_as_one_hundred_percent(self):
        report = self.run_pack()
        ui = report["metrics"]["core_interactions"]
        self.assertIsNone(ui["ratio"])
        self.assertEqual(ui["status"], "not_applicable")
class D0ConsistencyTests(PackTestCase):
    def d0_plan(self, **kw):
        base = dict(design_level="D0", project_type="script", features=[], risks=[], required_artifacts=["A01", "A07", "A08"], mandatory_rules=["CODE-001", "SEC-001"], classification_rationale=["需求明确"], open_questions=[])
        base.update(kw)
        return plan(**base)

    def d0_pack(self, p):
        ids = ["CODE-001", "SEC-001"]
        rules = [dict(rule_id=i, reason="适用", targets=["s"], design_refs=[], implementation_tasks=["TASK-1"], verification_ids=["T-" + i]) for i in ids]
        sec = dict(schema_version="1.0", applicable_rules=rules, not_applicable=[])
        task = dict(task_id="TASK-1", title="t", requirement_ids=["R1"], design_refs=[], mandatory_rule_ids=ids, acceptance_ids=["T-1"], dependencies=[])
        ho = handoff(tasks=[task])
        return {"plan.json": p, "artifacts/security.json": sec, "handoff.json": ho, "artifacts/technical.json": None, "artifacts/data.json": None}

    def test_a_clean_d0_pack_passes(self):
        report = self.run_pack(**self.d0_pack(self.d0_plan()))
        self.assertEqual(self.failed(report), [], report["blocking"])

    def test_d0_with_open_questions_fails_because_the_requirement_is_not_clear(self):
        p = self.d0_plan(open_questions=["输出目录是否固定？"])
        report = self.run_pack(**self.d0_pack(p))
        rows = self.failed(report, "V2-D0")
        self.assertTrue(rows)
        self.assertIn("输出目录是否固定？", rows[0]["evidence"]["open_questions"])
        self.assertFalse(report["ready_for_coding"])

    def test_open_questions_do_not_fail_a_non_d0_pack(self):
        report = self.run_pack(**{"plan.json": plan(open_questions=["谁来审批？"])})
        self.assertEqual(self.failed(report, "V2-D0"), [])

    def test_d0_check_is_not_applicable_for_other_levels(self):
        report = self.run_pack()
        rows = [x for x in report["results"] if x["rule_id"] == "V2-D0"]
        self.assertEqual({x["status"] for x in rows}, {"not_applicable"})




if __name__ == "__main__":
    unittest.main()
