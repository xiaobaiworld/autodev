import json
import re
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from cockpit.agents import parse_agents, parse_roles
from cockpit.controller import Controller, SetupError, check_vendors, start_run
from cockpit.store import Run

CFG = (Path(__file__).resolve().parents[1] / "config.yaml").read_text(encoding="utf-8")
LIMITS = {"design_review_rounds": 3, "step_retries": 2, "step_timeout_minutes": 60}
OUTS = {"S1": ["analysis.md"], "S2": ["design.md", "dev-plan.md"], "S3": ["review.md"]}


class CrashError(Exception):
    pass


class FakeAgent:
    """按 input.md 的 frontmatter 写产物和 done.json。verdicts: {阶段: [每次调用的结论]}。"""

    def __init__(self, verdicts, fail_first=None, crash_on=None):
        self.verdicts = {k: list(v) for k, v in verdicts.items()}
        self.fail_first, self.crash_on = fail_first, crash_on
        self.calls = []

    def __call__(self, sd, timeout_s):
        fm = (Path(sd) / "input.md").read_text(encoding="utf-8")
        g = lambda k: re.search(rf"^{k}: (.+)$", fm, re.M).group(1)
        stage, rnd = g("stage"), int(g("round"))
        self.calls.append((stage, rnd))
        if self.crash_on == (stage, rnd) and len(self.calls) and self.calls.count((stage, rnd)) == 1:
            raise CrashError()
        if self.fail_first == stage and self.calls.count((stage, rnd)) == 1:
            return {"ok": False, "reason": "timeout"}
        for f in OUTS[stage]:
            (Path(sd) / f).write_text("## 原文对照\nx\n" if f == "review.md" else "x")   # 审查产物必须有这个小节
        v = self.verdicts[stage].pop(0)
        (Path(sd) / "done.json").write_text(json.dumps({
            "id": g("id"), "stage": stage, "round": rnd, "role": g("role"),
            "outputs": OUTS[stage], "verdict": v, "summary": "测试"}))
        return {"ok": True, "reason": None}


class ControllerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, agent):
        return Controller(self.root, parse_agents(CFG), parse_roles(CFG), LIMITS, invoke_fn=agent)

    def go(self, ctrl):
        rid = start_run(self.root, "给 calc 加 divide", "toy", ctrl, today=datetime(2026, 11, 5))
        return rid, self.root / "workspace" / "runs" / rid

    def test_s1_to_s3_pass(self):
        ag = FakeAgent({"S1": ["ACCEPT"], "S2": ["DONE"], "S3": ["PASS"]})
        ctrl = self.make(ag)
        rid, rd = self.go(ctrl)
        ctrl.run_all(rd, log=lambda m: None)
        st = Run(rd).read()
        self.assertEqual((rid, st["status"], st["stage"]), ("R20261105-001", "done", "S3"))
        self.assertEqual([c[0] for c in ag.calls], ["S1", "S2", "S3"])
        seqs = [json.loads(x)["seq"] for x in (rd / "events.jsonl").read_text().splitlines()]
        self.assertEqual(seqs, list(range(1, len(seqs) + 1)))
        self.assertEqual(Run(rd).load()["seq"], seqs[-1])

    def test_rework_loop_then_pass(self):
        ag = FakeAgent({"S1": ["ACCEPT"], "S2": ["DONE", "DONE"], "S3": ["REWORK", "PASS"]})
        ctrl = self.make(ag)
        _, rd = self.go(ctrl)
        ctrl.run_all(rd, log=lambda m: None)
        st = Run(rd).read()
        self.assertEqual(st["status"], "done")
        self.assertEqual([(c[0], c[1]) for c in ag.calls],
                         [("S1", 1), ("S2", 1), ("S3", 1), ("S2", 2), ("S3", 2)])
        self.assertEqual(st["counters"]["design_review_rounds"], 1)

    def test_rework_limit_goes_to_needs_human(self):
        ag = FakeAgent({"S1": ["ACCEPT"], "S2": ["DONE"] * 3, "S3": ["REWORK"] * 3})
        ctrl = self.make(ag)
        _, rd = self.go(ctrl)
        ctrl.run_all(rd, log=lambda m: None)
        st = Run(rd).read()
        self.assertEqual(st["status"], "needs-human")
        self.assertTrue(st["human"]["waiting"])
        last = json.loads((rd / "events.jsonl").read_text().splitlines()[-1])
        self.assertEqual(last["type"], "limit.exceeded")

    def test_clarify_stops_for_human(self):
        ag = FakeAgent({"S1": ["CLARIFY"]})
        ctrl = self.make(ag)
        _, rd = self.go(ctrl)
        ctrl.run_all(rd, log=lambda m: None)
        self.assertEqual(Run(rd).read()["status"], "needs-human")

    def test_failure_retries_then_succeeds(self):
        ag = FakeAgent({"S1": ["ACCEPT"], "S2": ["DONE"], "S3": ["PASS"]}, fail_first="S1")
        ctrl = self.make(ag)
        _, rd = self.go(ctrl)
        ctrl.run_all(rd, log=lambda m: None)
        types = [json.loads(x)["type"] for x in (rd / "events.jsonl").read_text().splitlines()]
        self.assertIn("step.failed", types)
        self.assertIn("step.retried", types)
        self.assertEqual(Run(rd).read()["status"], "done")

    def test_crash_mid_step_then_restart_continues(self):
        ag = FakeAgent({"S1": ["ACCEPT"], "S2": ["DONE"], "S3": ["PASS"]}, crash_on=("S2", 1))
        ctrl = self.make(ag)
        _, rd = self.go(ctrl)
        with self.assertRaises(CrashError):
            ctrl.run_all(rd, log=lambda m: None)
        st = Run(rd).read()
        self.assertEqual((st["stage"], st["step"]["state"]), ("S2", "running"))
        ctrl2 = self.make(ag)  # 新进程：只靠文件恢复
        ctrl2.run_all(rd, log=lambda m: None)
        self.assertEqual(Run(rd).read()["status"], "done")
        self.assertEqual([c[:2] for c in ag.calls].count(("S1", 1)), 1)  # S1 不重做
        self.assertEqual([c[:2] for c in ag.calls].count(("S2", 1)), 2)  # S2 只重做一次

    def test_vendor_check_rejects_same_vendor(self):
        agents = parse_agents(CFG)
        roles = dict(parse_roles(CFG), design_reviewer="claude-opus")
        with self.assertRaises(SetupError):
            check_vendors(agents, roles)


if __name__ == "__main__":
    unittest.main()
