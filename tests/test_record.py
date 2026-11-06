import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from cockpit.agents import parse_agents, parse_limits, parse_roles
from cockpit.controller import Controller, start_run
from cockpit.store import Run
from driver.record import codex_model_from_command, find_worker_run, parse_log, write_record
from test_controller import FakeAgent

CFG = (Path(__file__).resolve().parents[1] / "config.yaml").read_text(encoding="utf-8")
CLAUDE = [{"type": "system", "subtype": "init", "model": "m/claude-x"},
          {"type": "result", "usage": {"output_tokens": 5}, "total_cost_usd": 0.5, "duration_ms": 900, "result": "做完了"}]
CODEX = [{"type": "thread.started"},
         {"type": "item.completed", "item": {"type": "reasoning", "text": "想一想"}},
         {"type": "item.completed", "item": {"type": "command_execution"}},
         {"type": "item.completed", "item": {"type": "file_change", "changes": [{"path": "/a/b.md"}]}},
         {"type": "item.completed", "item": {"type": "agent_message", "text": "结论"}},
         {"type": "turn.completed", "usage": {"output_tokens": 7}}]


def jl(items):
    return "\n".join(json.dumps(i) for i in items) + "\nnot json\n"


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_claude_log(self):
        (self.d / "l").write_text(jl(CLAUDE))
        p = parse_log(self.d / "l")
        self.assertEqual((p["cli"], p["model"], p["cost_usd"], p["final_message"]), ("claude", "m/claude-x", 0.5, "做完了"))

    def test_codex_log(self):
        (self.d / "l").write_text(jl(CODEX))
        p = parse_log(self.d / "l")
        self.assertEqual((p["cli"], p["commands"], p["files_changed"], p["reasoning"], p["usage"]["output_tokens"]),
                         ("codex", 1, ["/a/b.md"], ["想一想"], 7))
        self.assertIsNone(p["model"])  # Codex 日志里没有模型名，要从命令里取

    def test_codex_model_from_command(self):
        (self.d / "c.sh").write_text("codex exec '-m' 'gpt-6-sol' '-c' 'x'")
        self.assertEqual(codex_model_from_command(self.d / "c.sh"), "gpt-6-sol")

    def test_find_worker_run_picks_latest_and_ignores_others(self):
        for name, key in (("3-1", "K"), ("3-2", "K"), ("4-1", "OTHER")):
            (self.d / "worker" / "runs" / name).mkdir(parents=True)
            (self.d / "worker" / "runs" / name / "context.json").write_text(json.dumps({"events": [{"id": key}]}))
        self.assertEqual(find_worker_run(self.d, "K").name, "3-2")
        self.assertIsNone(find_worker_run(self.d, "NONE"))


class FlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, on_finish):
        return Controller(self.root, parse_agents(CFG), parse_roles(CFG), parse_limits(CFG),
                          invoke_fn=FakeAgent({"S1": ["ACCEPT"], "S2": ["DONE"], "S3": ["PASS"]}), on_finish=on_finish)

    def test_record_failure_does_not_stop_the_pipeline(self):
        def boom(rd, st):
            raise RuntimeError("坏了")
        ctrl = self.make(boom)
        rid = start_run(self.root, "需求", "toy", ctrl, today=datetime(2026, 11, 6))
        rd = self.root / "workspace" / "runs" / rid
        ctrl.run_all(rd, log=lambda m: None)
        types = [json.loads(l)["type"] for l in (rd / "events.jsonl").read_text().splitlines()]
        self.assertEqual(Run(rd).read()["status"], "done")
        self.assertIn("record.failed", types)

    def test_record_without_hub_log_says_so(self):
        ctrl = self.make(lambda rd, st: write_record(self.root / "nohome", rd, st))
        rid = start_run(self.root, "需求", "toy", ctrl, today=datetime(2026, 11, 6))
        rd = self.root / "workspace" / "runs" / rid
        ctrl.run_all(rd, log=lambda m: None)
        rec = json.loads(next((rd / "S1-analysis" / "round-1").glob("record-a1.json")).read_text())
        self.assertEqual((rec["verdict"], rec["summary"]), ("ACCEPT", "测试"))
        self.assertTrue(any("没有找到" in n for n in rec["notes"]))


if __name__ == "__main__":
    unittest.main()
