import json
import tempfile
import unittest
from pathlib import Path

from driver.compare import build_digest, diff_digests, render, write_digest


def make_run(root, rid, request, verdicts, tokens, template_kind="pipeline/design"):
    run = Path(root) / "workspace" / "runs" / rid
    (Path(root) / "workspace" / "requests" / "active").mkdir(parents=True, exist_ok=True)
    (Path(root) / "workspace" / "requests" / "active" / f"{rid}.md").write_text(f"---\nid: {rid}\nsubmitted_at: {rid}\n---\n\n{request}\n")
    run.mkdir(parents=True)
    (run / "state.json").write_text(json.dumps({"id": rid, "kind": template_kind, "status": "done"}))
    for i, (stage, verdict, inp) in enumerate(zip(("S1", "S2", "S3"), verdicts, tokens)):
        d = run / f"{stage}-x" / "round-1"
        d.mkdir(parents=True)
        (d / "record-a1.json").write_text(json.dumps({
            "stage": stage, "round": 1, "attempt": 1, "agent": "a", "actual_model": "m", "verdict": verdict,
            "recorded_at": f"2026-11-06T12:0{i}:00+08:00",
            "usage": {"input_tokens": inp, "cached_input_tokens": 0, "output_tokens": 10}}))
    return run


class CompareTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_digest_is_deterministic_and_ignores_ids_in_request_frontmatter(self):
        a = make_run(self.root, "R1", "做个东西", ("ACCEPT", "DONE", "PASS"), (100, 200, 300))
        b = make_run(self.root, "R2", "做个东西", ("ACCEPT", "DONE", "PASS"), (100, 200, 300))
        self.assertEqual(build_digest(a)["request_hash"], build_digest(b)["request_hash"])
        p = write_digest(a)
        first = p.read_text()
        write_digest(a)
        self.assertEqual(first, p.read_text())

    def test_different_request_is_flagged_as_not_comparable(self):
        a = build_digest(make_run(self.root, "R1", "甲", ("ACCEPT", "DONE", "PASS"), (1, 2, 3)))
        b = build_digest(make_run(self.root, "R2", "乙", ("ACCEPT", "DONE", "PASS"), (1, 2, 3)))
        self.assertTrue(any("需求文本不同" in i for i in diff_digests(a, b)["comparability"]))

    def test_token_change_by_stage(self):
        a = build_digest(make_run(self.root, "R1", "甲", ("ACCEPT", "DONE", "PASS"), (100, 200, 400)))
        b = build_digest(make_run(self.root, "R2", "甲", ("ACCEPT", "DONE", "PASS"), (100, 200, 100)))
        d = diff_digests(a, b)
        self.assertEqual(d["by_stage"]["S3"]["input"], (400, 100))
        self.assertEqual(d["total"]["input"], (700, 400))
        self.assertIn("-75%", render(a, b, d))

    def test_scope_note_difference_in_step_input_is_flagged(self):
        ra = make_run(self.root, "R1", "甲", ("ACCEPT", "DONE", "PASS"), (1, 2, 3))
        rb = make_run(self.root, "R2", "甲", ("ACCEPT", "DONE", "PASS"), (1, 2, 3))
        for d in rb.glob("S*-x/round-1"):
            (d / "input.md").write_text("## 任务\n...\n## 范围\n只读输入文件\n")
        for d in ra.glob("S*-x/round-1"):
            (d / "input.md").write_text("## 任务\n...\n")
        issues = diff_digests(build_digest(ra), build_digest(rb))["comparability"]
        self.assertTrue(any("范围说明 无 → 有" in i for i in issues), issues)

    def test_template_hash_comes_from_records_not_from_current_template(self):
        r = make_run(self.root, "R1", "甲", ("ACCEPT", "DONE", "PASS"), (1, 2, 3))
        self.assertIsNone(build_digest(r)["template_hash"])  # 老记录没有，不去猜
        for p in r.glob("S*-x/round-1/record-a1.json"):
            rec = json.loads(p.read_text())
            rec["template_hash"] = "abc123"
            p.write_text(json.dumps(rec))
        self.assertEqual(build_digest(r)["template_hash"], "abc123")
        p = next(r.glob("S3-x/round-1/record-a1.json"))
        rec = json.loads(p.read_text())
        rec["template_hash"] = "other"
        p.write_text(json.dumps(rec))
        self.assertEqual(build_digest(r)["template_hash"], "mixed")

    def test_missing_usage_is_flagged(self):
        r = make_run(self.root, "R1", "甲", ("ACCEPT", "DONE", "PASS"), (1, 2, 3))
        p = next(r.glob("S3-x/round-1/record-a1.json"))
        rec = json.loads(p.read_text())
        rec["usage"] = None
        p.write_text(json.dumps(rec))
        a = build_digest(r)
        b = build_digest(make_run(self.root, "R2", "甲", ("ACCEPT", "DONE", "PASS"), (1, 2, 3)))
        self.assertTrue(any("没有用量" in i for i in diff_digests(a, b)["comparability"]))


if __name__ == "__main__":
    unittest.main()
