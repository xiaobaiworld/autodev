import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from cockpit.agents import parse_agents, parse_roles
from cockpit.controller import Controller, start_run
from cockpit.kinds import DEFAULT_KIND, KINDS, UnknownKind, check_kind, kind_label, kind_matches, kind_of
from cockpit.store import Run

CFG = (Path(__file__).resolve().parents[1] / "config.yaml").read_text(encoding="utf-8")
LIMITS = {"design_review_rounds": 3, "step_retries": 2, "step_timeout_minutes": 60}


class KindTest(unittest.TestCase):
    def test_default_is_registered(self):
        self.assertEqual(DEFAULT_KIND, "pipeline/design")
        self.assertIn(DEFAULT_KIND, KINDS)

    def test_check_accepts_registered(self):
        self.assertEqual(check_kind("pipeline/design"), "pipeline/design")

    def test_check_rejects_unknown_with_hint(self):
        with self.assertRaisesRegex(UnknownKind, "pipeline/design"):
            check_kind("pipeline/code")

    def test_check_rejects_malformed_paths(self):
        for bad in ("", "Pipeline/design", "pipeline//design", "/pipeline", "pipeline/", "pipeline design", None):
            with self.subTest(bad):
                with self.assertRaises(UnknownKind):
                    check_kind(bad)

    def test_parent_matching_is_by_whole_segment(self):
        self.assertTrue(kind_matches("pipeline/design", "pipeline"))
        self.assertTrue(kind_matches("pipeline/design", "pipeline/design"))
        self.assertFalse(kind_matches("pipeline/design", "pipe"))
        self.assertFalse(kind_matches("pipeline", "pipeline/design"))
        self.assertFalse(kind_matches(None, "pipeline"))

    def test_kind_of_missing_is_none_not_a_guess(self):
        self.assertIsNone(kind_of({"id": "R1"}))
        self.assertEqual(kind_of({"kind": "pipeline/design"}), "pipeline/design")

    def test_label(self):
        self.assertIn("S1", kind_label("pipeline/design"))
        self.assertEqual(kind_label(None), "未分类")
        self.assertEqual(kind_label("zzz/unknown"), "zzz/unknown")  # 没登记的原样显示，不隐藏


class StartRunKindTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ctrl = Controller(self.root, parse_agents(CFG), parse_roles(CFG), LIMITS,
                               invoke_fn=lambda *a, **k: None)

    def tearDown(self):
        self.tmp.cleanup()

    def test_new_run_records_default_kind(self):
        rid = start_run(self.root, "需求", "toy", self.ctrl, today=datetime(2026, 11, 6))
        self.assertEqual(Run(self.root / "workspace" / "runs" / rid).read()["kind"], "pipeline/design")

    def test_unknown_kind_is_refused_before_anything_is_written(self):
        with self.assertRaises(UnknownKind):
            start_run(self.root, "需求", "toy", self.ctrl, kind="nope/x")
        self.assertFalse((self.root / "workspace").exists())

    def test_kind_survives_later_commits(self):
        rid = start_run(self.root, "需求", "toy", self.ctrl, today=datetime(2026, 11, 6))
        run = Run(self.root / "workspace" / "runs" / rid)
        run.commit(run.read(), "stage.entered")
        self.assertEqual(run.read()["kind"], "pipeline/design")


if __name__ == "__main__":
    unittest.main()
