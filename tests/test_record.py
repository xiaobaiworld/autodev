import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from cockpit.agents import parse_agents, parse_limits, parse_roles
from cockpit.controller import Controller, start_run
from cockpit.store import Run
from driver.record import codex_model_from_command, find_worker_run, normalize_usage, parse_log, summarize_run, write_record
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


class UsageTest(unittest.TestCase):
    def test_claude_total_includes_cache(self):
        u = {"input_tokens": 40, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 10, "output_tokens": 5}
        self.assertEqual(normalize_usage(u), {"input": 150, "cached": 100, "output": 5})

    def test_codex_input_already_includes_cached(self):
        u = {"input_tokens": 500, "cached_input_tokens": 400, "output_tokens": 7}
        self.assertEqual(normalize_usage(u), {"input": 500, "cached": 400, "output": 7})

    def test_missing_or_unknown_shape_is_none_not_zero(self):
        for bad in (None, {}, {"output_tokens": 3}, "x"):
            self.assertIsNone(normalize_usage(bad))

    def test_summary_counts_steps_without_usage(self):
        with tempfile.TemporaryDirectory() as d:
            for i, (stage, agent, usage) in enumerate((("S1", "a", {"input_tokens": 1, "cache_read_input_tokens": 9, "output_tokens": 2}),
                                                       ("S3", "b", None))):
                p = Path(d) / f"{stage}-x" / "round-1"
                p.mkdir(parents=True)
                (p / "record-a1.json").write_text(json.dumps({"stage": stage, "round": 1, "agent": agent, "usage": usage}))
            s = summarize_run(d)
            self.assertEqual((s["total"]["input"], s["total"]["output"], s["total"]["no_usage"], s["total"]["steps"]), (10, 2, 1, 2))
            self.assertEqual(s["by_agent"]["b"]["no_usage"], 1)


class FlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, on_finish):
        return Controller(self.root, parse_agents(CFG), parse_roles(CFG), parse_limits(CFG),
                          invoke_fn=FakeAgent({"S1": ["ACCEPT"], "S2": ["DONE"], "S3": ["PASS"]}), on_finish=on_finish)

    def test_tool_step_record_has_no_hub_lookup_and_no_misleading_note(self):
        sd = self.root / "workspace" / "runs" / "R1" / "S5-check" / "round-1"
        sd.mkdir(parents=True)
        (sd / "done.json").write_text(json.dumps({"outputs": ["check.log"], "verdict": "PASS", "summary": "ok"}))
        state = {"id": "R1", "kind": "pipeline/build", "stage": "S5", "round": 1,
                 "step": {"agent": "tool:check", "role": "checker", "dir": "S5-check/round-1", "attempt": 1,
                          "model": None, "started_at": None}}
        rec = json.loads(write_record(self.root / "nohome", self.root / "workspace" / "runs" / "R1", state).read_text())
        self.assertEqual((rec["tool"], rec["notes"], rec["verdict"]), ("check", [], "PASS"))
        self.assertNotIn("hub_run", rec)

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
        self.assertTrue(rec["template_hash"])  # 运行当时的模板版本，比对时靠它判断模板是否相同
        self.assertTrue(any("没有找到" in n for n in rec["notes"]))


if __name__ == "__main__":
    unittest.main()
