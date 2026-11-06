import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cockpit import pipeline
from cockpit.pipeline import counters_for, load_template, next_move, write_input

LIM = {"design_review_rounds": 3}


def st(kind, stage, rnd=1, used=0):
    return {"id": "R1", "kind": kind, "stage": stage, "round": rnd, "project": "toy",
            "counters": {"design_review_rounds": used}}


class BuildTransitionTest(unittest.TestCase):
    def test_table(self):
        b, d = "pipeline/build", "pipeline/design"
        cases = [
            (st(b, "S3"), "PASS", ("goto", "S4", 1)),        # build：审查通过后进编码
            (st(d, "S3"), "PASS", ("done", "S3", 1)),        # design：仍然到此结束（回归）
            (st(b, "S3"), "REWORK", ("goto", "S2", 2)),
            (st(b, "S3", 3, used=2), "REWORK", ("limit", "S3", 3)),
            (st(b, "S4"), "DONE", ("done", "S4", 1)),
            (st(b, "S4"), "BLOCK", ("needs-human", "S4", 1)),
            (st(b, "S1"), "ACCEPT", ("goto", "S2", 1)),
            (st(b, "S1"), "REJECT", ("rejected", "S1", 1)),
            (st(None, "S3"), "PASS", ("done", "S3", 1)),     # 老记录没有 kind，按 design 处理
        ]
        for state, verdict, want in cases:
            with self.subTest(kind=state["kind"], stage=state["stage"], verdict=verdict):
                self.assertEqual(next_move(state, verdict, LIM)[:3], want)

    def test_build_extends_design(self):
        b, d = load_template("pipeline/build"), load_template("pipeline/design")
        self.assertEqual(b["order"], ["S1", "S2", "S3", "S4"])
        self.assertEqual(b["stages"]["S1"], d["stages"]["S1"])           # 没覆盖的阶段原样继承
        self.assertEqual(b["stages"]["S3"]["role"], d["stages"]["S3"]["role"])  # 覆盖 on 不丢 role
        self.assertEqual(b["stages"]["S4"]["role"], "coder")
        self.assertEqual(b["scope"], d["scope"])

    def test_counters_follow_template(self):
        self.assertEqual(counters_for("pipeline/build"), {"design_review_rounds": 0})


class BrokenTemplateTest(unittest.TestCase):
    def load_with(self, mutate):
        t = load_template("pipeline/design")
        mutate(t)
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "design.json").write_text(json.dumps(t, ensure_ascii=False))
            with mock.patch.object(pipeline, "TEMPLATES", Path(d)):
                return load_template("pipeline/design")

    def test_verdict_without_destination_is_refused(self):
        with self.assertRaisesRegex(ValueError, "没有写去哪"):
            self.load_with(lambda t: t["stages"]["S3"]["on"].pop("REWORK"))

    def test_destination_to_unknown_stage_is_refused(self):
        with self.assertRaisesRegex(ValueError, "去向不合法"):
            self.load_with(lambda t: t["stages"]["S3"]["on"].update(REWORK={"goto": "S9", "round": 1}))

    def test_on_with_disallowed_verdict_is_refused(self):
        with self.assertRaisesRegex(ValueError, "不允许的结论"):
            self.load_with(lambda t: t["stages"]["S2"]["on"].update(PASS="done"))


class InputTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def state(self, stage, rnd=1):
        d = pipeline.step_dir(stage, rnd, "pipeline/build")
        return {"id": "R1", "kind": "pipeline/build", "project": "todo-demo", "stage": stage, "round": rnd,
                "step": {"role": "coder", "dir": d}}

    def test_s4_input_names_the_workdir_and_forbids_git(self):
        s = self.state("S4")
        text = write_input(self.root, self.root / "workspace" / "runs" / "R1", s).read_text(encoding="utf-8")
        self.assertIn(str(self.root / "workspace" / "projects" / "todo-demo" / "R1"), text)
        self.assertIn("不要执行 git", text)
        self.assertNotIn("上轮审查意见", text)

    def test_s2_later_round_points_at_previous_review(self):
        s = self.state("S2", 2)
        text = write_input(self.root, self.root / "workspace" / "runs" / "R1", s).read_text(encoding="utf-8")
        self.assertIn("上轮审查意见", text)
        self.assertIn("round-1", text)

    def test_s4_reads_the_latest_design_round(self):
        run = self.root / "workspace" / "runs" / "R1"
        for r in (1, 2, 3):
            (run / pipeline.step_dir("S2", r, "pipeline/build")).mkdir(parents=True)
        text = write_input(self.root, run, self.state("S4")).read_text(encoding="utf-8")
        self.assertIn("S2-design/round-3/design.md", text)
        self.assertNotIn("S2-design/round-1/design.md", text)


if __name__ == "__main__":
    unittest.main()
