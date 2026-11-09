import json
import unittest
from pathlib import Path

from designsys import schema as s

DIR = Path(__file__).resolve().parents[1] / "design-system" / "schemas"
NAMES = ("plan", "technical", "data", "security", "handoff")


def load(name):
    return json.loads((DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def good():
    rule = dict(rule_id="SEC-002", reason="受保护文档", targets=["api"], design_refs=["a"], implementation_tasks=["TASK-1"], verification_ids=["T-1"])
    task = dict(task_id="TASK-1", title="t", requirement_ids=["R1"], design_refs=["a"], mandatory_rule_ids=["SEC-002"], acceptance_ids=["T-1"], dependencies=[])
    mod = dict(id="M1", responsibility="r", inputs=[], outputs=[], dependencies=[], failure_handling="f")
    field = dict(name="id", type="string", nullable=False)
    ent = dict(id="Doc", primary_key=["id"], fields=[field])
    return {
        "plan": dict(schema_version="1.0", project_type="web", design_level="D2", features=["ui"], required_artifacts=["A01"], mandatory_rules=["SEC-001"], classification_rationale=["x"], open_questions=[]),
        "technical": dict(schema_version="1.0", modules=[mod], decisions=[], risks_to_verify=[]),
        "data": dict(schema_version="1.0", entities=[ent]),
        "security": dict(schema_version="1.0", applicable_rules=[rule], not_applicable=[]),
        "handoff": dict(schema_version="1.0", design_version="1.0.0", requirements_baseline="B1", tasks=[task], blocking_issues=[], ready_for_coding=True),
    }


class SchemaFileTests(unittest.TestCase):
    def test_every_schema_file_is_loadable_and_uses_only_supported_keywords(self):
        for name in NAMES:
            schema = load(name)
            self.assertEqual(s.validate(good()[name], schema), [], name)

    def test_good_documents_pass(self):
        docs = good()
        for name in NAMES:
            self.assertEqual(s.validate(docs[name], load(name)), [], name)

    def test_missing_required_field_is_rejected_for_every_schema(self):
        docs = good()
        for name in NAMES:
            doc = dict(docs[name])
            del doc["schema_version"]
            self.assertTrue(s.validate(doc, load(name)), name)

    def test_unknown_field_is_rejected_for_every_schema(self):
        docs = good()
        for name in NAMES:
            doc = dict(docs[name], surprise=1)
            self.assertTrue(s.validate(doc, load(name)), name)

    def test_bad_level_rule_id_version_and_empty_collections_are_rejected(self):
        docs = good()
        self.assertTrue(s.validate(dict(docs["plan"], design_level="D9"), load("plan")))
        self.assertTrue(s.validate(dict(docs["plan"], required_artifacts=["X1"]), load("plan")))
        self.assertTrue(s.validate(dict(docs["plan"], classification_rationale=[]), load("plan")))
        self.assertTrue(s.validate(dict(docs["handoff"], design_version="v1"), load("handoff")))
        self.assertTrue(s.validate(dict(docs["technical"], modules=[]), load("technical")))
        self.assertTrue(s.validate(dict(docs["data"], entities=[]), load("data")))

    def test_security_rule_id_format_is_enforced(self):
        doc = good()["security"]
        doc["applicable_rules"][0]["rule_id"] = "sec2"
        self.assertTrue(s.validate(doc, load("security")))

    def test_entity_without_primary_key_or_fields_is_rejected(self):
        doc = good()["data"]
        doc["entities"][0]["primary_key"] = []
        self.assertTrue(s.validate(doc, load("data")))


if __name__ == "__main__":
    unittest.main()
