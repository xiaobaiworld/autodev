import json
import re
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from cockpit.agents import parse_agents, parse_roles
from cockpit.controller import Controller, start_run
from cockpit.store import Run

CFG = (Path(__file__).resolve().parents[1] / "config.yaml").read_text(encoding="utf-8")
LIMITS = {"design_review_rounds": 3, "check_rounds": 3, "step_retries": 2, "step_timeout_minutes": 60}
OUTS = {"S1": ["analysis.md"], "S2": ["design.md", "dev-plan.md"], "S3": ["review.md"], "S4": ["exec-report.md"]}


class Agent:
    """按 input.md 写产物。s4: 每次 S4 调用的结论列表（用完后给 DONE）。每次 S4 都往代码目录写一个文件。"""

    def __init__(self, root, s4):
        self.root, self.s4, self.inputs = Path(root), list(s4), []

    def __call__(self, sd, timeout_s):
        text = (Path(sd) / "input.md").read_text(encoding="utf-8")
        g = lambda k: re.search(rf"^{k}: (.+)$", text, re.M).group(1).strip()
        stage, rid = g("stage"), g("id")
        self.inputs.append((stage, int(g("round")), text))
        verdict = {"S1": "ACCEPT", "S2": "DONE", "S3": "PASS"}.get(stage)
        if stage == "S4":
            verdict = self.s4.pop(0) if self.s4 else "DONE"
            n = len([i for i in self.inputs if i[0] == "S4"])        # 每次内容不同，否则第 2 次在检查点之上“没有改动”会被判无效
            (self.root / "workspace" / "projects" / "toy" / rid / "todo.py").write_text(f"x = {n}\n")
        for f in OUTS[stage]:
            (Path(sd) / f).write_text("x")
        (Path(sd) / "done.json").write_text(json.dumps({
            "id": rid, "stage": stage, "round": int(g("round")), "role": g("role"), "outputs": OUTS[stage],
            "verdict": verdict, "summary": "测试"}))
        return {"ok": True, "reason": None}


class ResumeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def blocked_run(self, s4=("BLOCK",)):
        agent = Agent(self.root, s4)

        def passing_check(ctx):
            (Path(ctx["sd"]) / "check.log").write_text("ok")
            return {"verdict": "PASS", "summary": "假检查通过", "outputs": ["check.log"]}
        ctrl = Controller(self.root, parse_agents(CFG), parse_roles(CFG), LIMITS, invoke_fn=agent,
                          tools={"check": passing_check})
        rid = start_run(self.root, "做个待办", "toy", ctrl, today=datetime(2026, 11, 6), kind="pipeline/build")
        rd = self.root / "workspace" / "runs" / rid
        ctrl.run_all(rd, log=lambda m: None)
        return agent, ctrl, rd

    def events(self, rd):
        return [json.loads(l)["type"] for l in (rd / "events.jsonl").read_text().splitlines()]

    def test_rework_goes_back_to_design_carries_the_note_and_finishes(self):
        agent, ctrl, rd = self.blocked_run()
        self.assertEqual(Run(rd).read()["status"], "needs-human")
        ctrl.resume(rd, "rework", note="不要用 setuptools，用单文件脚本", stage="S2")
        st = Run(rd).read()
        self.assertEqual((st["status"], st["stage"], st["round"], st["human"]["waiting"]), ("active", "S2", 2, False))
        ctrl.run_all(rd, log=lambda m: None)
        self.assertEqual(Run(rd).read()["status"], "done")
        reply = (rd / "human" / "reply-1.md").read_text(encoding="utf-8")
        self.assertIn("不要用 setuptools", reply)
        s2_input = next(t for s, r, t in agent.inputs if s == "S2" and r == 2)
        self.assertIn("用户决定", s2_input)
        self.assertIn("reply-1.md", s2_input)
        s2_first = next(t for s, r, t in agent.inputs if s == "S2" and r == 1)
        self.assertNotIn("用户决定", s2_first)             # 没有回复时不列这一项
        self.assertIn("human.replied", self.events(rd))
        # 第二次进 S4 第 1 轮：上次 BLOCK 的那一份被归档保留，这次的是新做的 DONE
        old = json.loads((rd / "S4-code" / "round-1.prev-1" / "done.json").read_text())
        new = json.loads((rd / "S4-code" / "round-1" / "done.json").read_text())
        self.assertEqual((old["verdict"], new["verdict"]), ("BLOCK", "DONE"))
        self.assertEqual(len([i for i in agent.inputs if i[0] == "S4"]), 2)   # S4 真的跑了两次，没有被旧结果短路

    def test_continue_reruns_the_same_stage_in_a_new_round(self):
        agent, ctrl, rd = self.blocked_run()
        ctrl.resume(rd, "continue", note="环境已装好，继续")
        st = Run(rd).read()
        self.assertEqual((st["stage"], st["round"]), ("S4", 2))
        ctrl.run_all(rd, log=lambda m: None)
        self.assertEqual(Run(rd).read()["status"], "done")
        self.assertTrue((rd / "S4-code" / "round-1").exists() and (rd / "S4-code" / "round-2").exists())  # 旧一轮保留

    def test_resume_clears_counters(self):
        agent, ctrl, rd = self.blocked_run()
        state = Run(rd).read()
        state["counters"]["design_review_rounds"] = 3
        Run(rd).commit(state, "test.setup")
        ctrl.resume(rd, "continue")
        self.assertEqual(Run(rd).read()["counters"], {"design_review_rounds": 0, "check_rounds": 0})

    def test_reject_ends_the_request(self):
        agent, ctrl, rd = self.blocked_run()
        ctrl.resume(rd, "reject", note="不做了")
        st = Run(rd).read()
        self.assertEqual((st["status"], st["human"]["waiting"]), ("rejected", False))

    def test_second_reply_gets_its_own_number(self):
        agent, ctrl, rd = self.blocked_run(s4=("BLOCK", "BLOCK"))
        ctrl.resume(rd, "continue", note="第一次")
        ctrl.run_all(rd, log=lambda m: None)
        self.assertEqual(Run(rd).read()["status"], "needs-human")
        ctrl.resume(rd, "continue", note="第二次")
        self.assertTrue((rd / "human" / "reply-2.md").exists())
        self.assertIn("第一次", (rd / "human" / "reply-1.md").read_text(encoding="utf-8"))

    def test_bad_requests_change_nothing(self):
        agent, ctrl, rd = self.blocked_run()
        before = Run(rd).read()
        for args in (("rework", "", "S9"), ("explode", "", None)):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    ctrl.resume(rd, args[0], note=args[1], stage=args[2])
        self.assertEqual(Run(rd).read(), before)
        self.assertFalse((rd / "human").exists())           # 校验失败不能留下回复文件

    def test_cannot_resume_a_request_that_is_not_waiting(self):
        agent, ctrl, rd = self.blocked_run(s4=())
        self.assertEqual(Run(rd).read()["status"], "done")
        with self.assertRaisesRegex(ValueError, "不在等待人工"):
            ctrl.resume(rd, "continue")


if __name__ == "__main__":
    unittest.main()
