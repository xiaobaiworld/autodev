import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cockpit import pipeline
from cockpit.agents import parse_roles
from cockpit.kinds import KINDS
from driver.setup import STAGES as RULE_STAGES

CFG = (Path(__file__).resolve().parents[1] / "config.yaml").read_text(encoding="utf-8")


class TemplateTest(unittest.TestCase):
    def test_every_registered_pipeline_kind_has_a_template(self):
        for kind in KINDS:
            if kind.startswith("pipeline/"):
                self.assertEqual(pipeline.load_template(kind)["kind"], kind)

    def test_template_roles_exist_in_config(self):
        roles = parse_roles(CFG)
        for s in pipeline.STAGES.values():
            self.assertIn(s["role"], roles)

    def test_rules_are_derived_from_the_template(self):
        self.assertEqual(dict(RULE_STAGES), {k.lower(): r for k, r in pipeline.stage_roles().items()})
        self.assertIn("s4", dict(RULE_STAGES))  # pipeline/build 的 S4 也要有规则

    def test_inconsistent_template_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "design.json").write_text(json.dumps({"kind": "pipeline/design", "order": ["S1"], "stages": {}}))
            with mock.patch.object(pipeline, "TEMPLATES", Path(d)):
                with self.assertRaises(ValueError):
                    pipeline.load_template("pipeline/design")

    def test_editing_template_changes_next_input(self):
        with tempfile.TemporaryDirectory() as d:
            t = pipeline.load_template("pipeline/design")
            t["stages"]["S1"]["task"] = "新的任务说明XYZ"
            (Path(d) / "design.json").write_text(json.dumps(t, ensure_ascii=False))
            with mock.patch.object(pipeline, "TEMPLATES", Path(d)):
                self.assertEqual(pipeline.load_template("pipeline/design")["stages"]["S1"]["task"], "新的任务说明XYZ")


if __name__ == "__main__":
    unittest.main()
