import json
import tempfile
import unittest
from pathlib import Path

from driver.compare import diff
from driver.record import digest, parse_log


class ParseLogTest(unittest.TestCase):
    def test_claude_stream_json(self):
        text = '\n'.join([
            '{"type":"system","subtype":"init","model":"ai-code-with/claude-opus-5-5"}',
            '{"type":"result","usage":{"input_tokens":120,"output_tokens":30,"cache_read_input_tokens":20}}',
        ])
        self.assertEqual(parse_log(text), {"actual_model": "ai-code-with/claude-opus-5-5",
                                           "usage": {"input_tokens": 120, "output_tokens": 30,
                                                     "cached_input_tokens": 20, "total_tokens": 150}})

    def test_codex_exec_json(self):
        text = '{"type":"thread.started","model":"gpt-6-sol"}\n{"type":"turn.completed","usage":{"input_tokens":200,"cached_input_tokens":80,"output_tokens":40}}'
        parsed = parse_log(text)
        self.assertEqual(parsed["actual_model"], "gpt-6-sol")
        self.assertEqual(parsed["usage"]["total_tokens"], 240)
        self.assertEqual(parsed["usage"]["cached_input_tokens"], 80)


class DigestTest(unittest.TestCase):
    def make_run(self, root, rid, request_body="相同需求"):
        active = root / "workspace/requests/active"
        active.mkdir(parents=True, exist_ok=True)
        (active / f"{rid}.md").write_text(f"---\nid: {rid}\n---\n\n{request_body}\n")
        run = root / "workspace/runs" / rid / "S1-analysis/round-1"
        run.mkdir(parents=True, exist_ok=True)
        (run / "record-a1.json").write_text(json.dumps({"stage": "S1", "round": 1, "attempt": 1,
            "role": "analyst", "actual_model": "model-x", "usage": {"input_tokens": 10,
            "output_tokens": 2, "total_tokens": 12}}))
        state = {"id": rid, "kind": "pipeline/build", "status": "done", "stage": "S9", "round": 1,
                 "counters": {}, "workdir": ""}
        (run.parents[1] / "state.json").write_text(json.dumps(state))
        return run.parents[1]

    def test_identical_inputs_are_comparable_across_run_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "templates/pipeline").mkdir(parents=True)
            (root / "config.yaml").write_text("same")
            (root / "templates/pipeline/design.json").write_text("design")
            (root / "templates/pipeline/build.json").write_text("build")
            a = self.make_run(root, "R1")
            b = self.make_run(root, "R2")
            result = diff(a, b)
            self.assertTrue(result["comparable"], result["limitations"])
            self.assertEqual(digest(a)["usage_totals"]["total_tokens"], 12)

    def test_different_request_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "templates/pipeline").mkdir(parents=True)
            (root / "config.yaml").write_text("same")
            (root / "templates/pipeline/design.json").write_text("design")
            (root / "templates/pipeline/build.json").write_text("build")
            a = self.make_run(root, "R1")
            b = self.make_run(root, "R2", "不同需求")
            self.assertIn("需求正文不同", diff(a, b)["limitations"])


if __name__ == "__main__":
    unittest.main()
