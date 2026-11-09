import json
import tempfile
import unittest
from pathlib import Path

from designsys import d0doc


def plan(**kw):
    base = dict(schema_version="1.0", project_type="script", design_level="D0", features=[], risks=[], required_artifacts=["A01", "A07", "A08"], mandatory_rules=["CODE-001", "SEC-001"], classification_rationale=["无功能特征与风险，需求明确"], open_questions=[])
    base.update(kw)
    return base


def handoff():
    task = dict(task_id="TASK-1", title="实现批量重命名脚本", requirement_ids=["REQ-1"], design_refs=[], mandatory_rule_ids=["CODE-001", "SEC-001"], acceptance_ids=["T-1"], dependencies=[])
    return dict(schema_version="1.0", design_version="1.0.0", requirements_baseline="B1", tasks=[task], blocking_issues=[], ready_for_coding=True)


class RenderTests(unittest.TestCase):
    def test_page_contains_the_four_required_parts(self):
        text = d0doc.render(plan(), handoff())
        for needle in ("D0", "功能特征", "适用的工程规则", "跳过", "开发交接"):
            self.assertIn(needle, text)

    def test_rules_come_from_the_plan_with_names_from_the_library(self):
        text = d0doc.render(plan(), handoff())
        self.assertIn("SEC-001", text)
        self.assertIn("密钥与凭证不得硬编码或提交", text)
        self.assertIn("CODE-001", text)

    def test_a_rule_not_in_the_plan_is_not_mentioned(self):
        text = d0doc.render(plan(), handoff())
        for rid in ("SEC-006", "SEC-007", "DATA-001", "UI-001"):
            self.assertNotIn(rid, text, rid)

    def test_rationale_and_open_questions_are_copied_verbatim(self):
        text = d0doc.render(plan(classification_rationale=["需求只是改一个文件名"], open_questions=["输出目录是否固定？"]), handoff())
        self.assertIn("需求只是改一个文件名", text)
        self.assertIn("输出目录是否固定？", text)

    def test_tasks_are_listed_from_the_handoff_file(self):
        text = d0doc.render(plan(), handoff())
        self.assertIn("TASK-1", text)
        self.assertIn("实现批量重命名脚本", text)

    def test_without_a_handoff_file_it_says_so_instead_of_inventing_tasks(self):
        text = d0doc.render(plan(), None)
        self.assertIn("尚未提供交接文件", text)
        self.assertNotIn("TASK-", text)

    def test_no_features_is_stated_not_left_blank(self):
        text = d0doc.render(plan(), handoff())
        self.assertIn("无功能特征", text)

    def test_features_and_risks_are_listed_when_present(self):
        text = d0doc.render(plan(features=["api"], risks=["cross_tenant"]), handoff())
        self.assertIn("api", text)
        self.assertIn("cross_tenant", text)

    def test_page_says_it_is_generated_and_that_r1_rules_are_not_program_enforced(self):
        text = d0doc.render(plan(), handoff())
        self.assertIn("由程序", text)
        self.assertIn("R1", text)

    def test_unknown_rule_is_flagged_visibly(self):
        text = d0doc.render(plan(mandatory_rules=["SEC-001", "NOPE-999"]), handoff())
        self.assertIn("NOPE-999", text)
        self.assertIn("规则库中不存在", text)

    def test_output_is_deterministic(self):
        self.assertEqual(d0doc.render(plan(), handoff()), d0doc.render(plan(), handoff()))


class RefusalTests(unittest.TestCase):
    def test_non_d0_plan_is_refused_not_rendered_as_if_it_were_d0(self):
        for level in ("D1", "D2", "D3"):
            with self.assertRaisesRegex(d0doc.D0Error, level):
                d0doc.render(plan(design_level=level), handoff())

    def test_plan_missing_a_needed_field_is_refused(self):
        bad = plan()
        del bad["classification_rationale"]
        with self.assertRaisesRegex(d0doc.D0Error, "classification_rationale"):
            d0doc.render(bad, handoff())


class WriteTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def put(self, rel, doc):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def test_write_reads_the_pack_and_creates_the_page(self):
        self.put("plan.json", plan())
        self.put("handoff.json", handoff())
        path = d0doc.write(self.root)
        self.assertEqual(path, self.root / "d0-summary.md")
        self.assertIn("TASK-1", path.read_text(encoding="utf-8"))

    def test_write_works_without_a_handoff_file(self):
        self.put("plan.json", plan())
        path = d0doc.write(self.root)
        self.assertIn("尚未提供交接文件", path.read_text(encoding="utf-8"))

    def test_write_refuses_a_pack_without_a_plan(self):
        with self.assertRaisesRegex(d0doc.D0Error, "plan.json"):
            d0doc.write(self.root)

    def test_write_refuses_an_unparseable_plan(self):
        (self.root / "plan.json").write_text("{bad", encoding="utf-8")
        with self.assertRaisesRegex(d0doc.D0Error, "plan.json"):
            d0doc.write(self.root)


if __name__ == "__main__":
    unittest.main()
