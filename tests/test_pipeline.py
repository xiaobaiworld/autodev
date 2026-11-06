import json
import tempfile
import unittest
from pathlib import Path

from cockpit.pipeline import next_move, step_dir, validate_done

LIM = {"design_review_rounds": 3}


def st(stage="S3", rnd=1, used=0):
    return {"id": "R1", "stage": stage, "round": rnd,
            "counters": {"design_review_rounds": used},
            "step": {"role": {"S1": "analyst", "S2": "designer", "S3": "design_reviewer"}[stage],
                     "dir": step_dir(stage, rnd)}}


def done(stage="S3", rnd=1, **kw):
    role = {"S1": "analyst", "S2": "designer", "S3": "design_reviewer"}[stage]
    d = {"id": "R1", "stage": stage, "round": rnd, "role": role,
         "outputs": ["review.md"], "verdict": "PASS", "summary": "审查完成"}
    d.update(kw)
    return d


class ValidateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = Path(self.tmp.name)
        self.sd = self.run / step_dir("S3", 1)
        self.sd.mkdir(parents=True)
        (self.sd / "review.md").write_text("x")

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, d):
        (self.sd / "done.json").write_text(json.dumps(d))

    def test_ok(self):
        self.put(done())
        self.assertIsNone(validate_done(self.run, st()))

    def test_wrong_round(self):
        self.put(done(rnd=2))
        self.assertIn("round", validate_done(self.run, st()))

    def test_missing_or_blank_summary_is_refused(self):
        for bad in (None, "", "  "):
            d = done()
            d["summary"] = bad
            self.put(d)
            self.assertIn("summary", validate_done(self.run, st()))

    def test_bad_verdict(self):
        self.put(done(verdict="DONE"))
        self.assertIn("verdict", validate_done(self.run, st()))

    def test_missing_output_file(self):
        (self.sd / "review.md").unlink()
        self.put(done())
        self.assertIn("review.md", validate_done(self.run, st()))

    def test_output_not_listed(self):
        self.put(done(outputs=[]))
        self.assertIn("review.md", validate_done(self.run, st()))

    def test_broken_json(self):
        (self.sd / "done.json").write_text("{oops")
        self.assertIn("done.json", validate_done(self.run, st()))


class NextMoveTest(unittest.TestCase):
    def test_table(self):
        cases = [
            (st("S1"), "ACCEPT", ("goto", "S2", 1)),
            (st("S1"), "REJECT", ("rejected", "S1", 1)),
            (st("S1"), "CLARIFY", ("needs-human", "S1", 1)),
            (st("S1"), "BLOCK", ("needs-human", "S1", 1)),
            (st("S2", 2), "DONE", ("goto", "S3", 2)),
            (st("S2"), "BLOCK", ("needs-human", "S2", 1)),
            (st("S3"), "PASS", ("done", "S3", 1)),
            (st("S3"), "REWORK", ("goto", "S2", 2)),
            (st("S3", 2, used=1), "REWORK", ("goto", "S2", 3)),
            (st("S3", 3, used=2), "REWORK", ("limit", "S3", 3)),
            (st("S3"), "BLOCK", ("needs-human", "S3", 1)),
        ]
        for state, verdict, want in cases:
            with self.subTest(state["stage"], verdict=verdict, used=state["counters"]):
                self.assertEqual(next_move(state, verdict, LIM)[:3], want)


if __name__ == "__main__":
    unittest.main()
