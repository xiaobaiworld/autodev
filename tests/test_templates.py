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

    def test_build_template_resolves_all_stages_and_routes(self):
        template = pipeline.load_template("pipeline/build")
        self.assertEqual(template["order"], ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S7U", "S8", "S9"])
        state = {"stage": "S8", "round": 1, "counters": {"acceptance_rounds": 0}}
        self.assertEqual(pipeline.next_move(state, "PASS", {"acceptance_rounds": 2}, template)[:3], ("goto", "S9", 1))
        self.assertEqual(template["stages"]["S9"]["gate"], "human")

    def test_rules_are_derived_from_the_template(self):
        self.assertEqual([r for _, r in RULE_STAGES], [pipeline.STAGES[k]["role"] for k in pipeline.ORDER])

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
