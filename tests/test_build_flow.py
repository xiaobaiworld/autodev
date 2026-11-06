import json
import re
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from cockpit.agents import parse_agents, parse_roles
from cockpit.controller import Controller, start_run
from cockpit.pipeline import workdir_of
from cockpit.store import Run

CFG = (Path(__file__).resolve().parents[1] / "config.yaml").read_text(encoding="utf-8")
LIMITS = {"design_review_rounds": 3, "check_rounds": 3, "step_retries": 2, "step_timeout_minutes": 60}
OUTS = {"S1": ["analysis.md"], "S2": ["design.md", "dev-plan.md"], "S3": ["review.md"], "S4": ["exec-report.md"]}
VERDICT = {"S1": "ACCEPT", "S2": "DONE", "S3": "PASS", "S4": "DONE"}


class CodingAgent:
    """所有阶段都按 input.md 写产物；S4 时按 on_s4(次数, 代码目录) 往代码目录写文件。"""

    def __init__(self, root, on_s4):
        self.root, self.on_s4, self.s4_calls, self.inputs = Path(root), on_s4, 0, []

    def __call__(self, sd, timeout_s):
        fm = (Path(sd) / "input.md").read_text(encoding="utf-8")
        g = lambda k: re.search(rf"^{k}: (.+)$", fm, re.M).group(1).strip()
        stage, rid = g("stage"), g("id")
        self.inputs.append((stage, int(g("round")), fm))
        if stage == "S4":
            self.s4_calls += 1
            self.on_s4(self.s4_calls, self.root / "workspace" / "projects" / "toy" / rid)
        for f in OUTS[stage]:
            (Path(sd) / f).write_text("x")
        (Path(sd) / "done.json").write_text(json.dumps({
            "id": rid, "stage": stage, "round": int(g("round")), "role": g("role"), "outputs": OUTS[stage],
            "verdict": VERDICT[stage], "summary": "测试"}))
        return {"ok": True, "reason": None}


class BuildFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def go(self, on_s4, check_verdicts=("PASS",)):
        """check_verdicts: 每次 S5 的结论（用完后一直给最后一个）。假检查把调用次数记在 self.checks。"""
        agent = CodingAgent(self.root, on_s4)
        self.checks, queue = [], list(check_verdicts)

        def fake_check(ctx):
            v = queue.pop(0) if len(queue) > 1 else queue[0]
            self.checks.append((v, sorted(p.name for p in Path(ctx["workdir"]).iterdir() if p.name != ".git")))
            (Path(ctx["sd"]) / "check.log").write_text(f"假检查 {v}")
            return {"verdict": v, "summary": f"假检查 {v}", "outputs": ["check.log"]}
        ctrl = Controller(self.root, parse_agents(CFG), parse_roles(CFG), LIMITS, invoke_fn=agent,
                          tools={"check": fake_check})
        rid = start_run(self.root, "做个待办", "toy", ctrl, today=datetime(2026, 11, 6), kind="pipeline/build")
        rd = self.root / "workspace" / "runs" / rid
        ctrl.run_all(rd, log=lambda m: None)
        return agent, rd

    def test_full_run_ends_after_s5_with_patch_and_base_commit(self):
        agent, rd = self.go(lambda n, wd: (wd / "todo.py").write_text("print('hi')\n"))
        st = Run(rd).read()
        self.assertEqual((st["status"], st["stage"]), ("done", "S5"))
        self.assertIn("todo.py", (rd / "S4-code" / "round-1" / "diff.patch").read_text())
        self.assertTrue((rd / "S5-check" / "round-1" / "check.log").exists())
        self.assertEqual(st["step"]["agent"], "tool:check")           # S5 记成程序步骤，不是 Agent
        self.assertIsNone(st["step"]["model"])

    def test_check_failure_goes_back_to_s4_and_fixes_on_top_of_existing_code(self):
        def on_s4(n, wd):
            if n == 1:
                (wd / "todo.py").write_text("bug\n")
            else:
                (wd / "todo.py").write_text("fixed\n")                # 第 2 轮在已有代码上改
        agent, rd = self.go(on_s4, check_verdicts=("FAIL", "PASS"))
        self.assertEqual((Run(rd).read()["status"], Run(rd).read()["stage"]), ("done", "S5"))
        self.assertEqual(agent.s4_calls, 2)
        # 第 2 轮 S4 开始时，第 1 轮的代码还在（检查点），不是被清空
        self.assertIn("todo.py", self.checks[0][1])
        self.assertTrue((rd / "S4-code" / "round-2" / "diff.patch").exists())
        patch2 = (rd / "S4-code" / "round-2" / "diff.patch").read_text()
        self.assertIn("-bug", patch2)                                 # 第 2 轮的补丁是相对第 1 轮的修改
        self.assertIn("+fixed", patch2)
        s4_round2_input = next(t for s, r, t in agent.inputs if s == "S4" and r == 2)
        self.assertIn("上轮检查结果（由程序运行测试得到", s4_round2_input)
        self.assertIn("round-1/check.log", s4_round2_input)
        s4_round1_input = next(t for s, r, t in agent.inputs if s == "S4" and r == 1)
        self.assertNotIn("check.log", s4_round1_input)                # 第 1 轮没有上轮检查结果这个输入文件

    def test_check_failing_every_time_hits_the_round_limit(self):
        agent, rd = self.go(lambda n, wd: (wd / f"f{n}.py").write_text("x\n"), check_verdicts=("FAIL",))
        st = Run(rd).read()
        self.assertEqual((st["status"], st["stage"]), ("needs-human", "S5"))
        self.assertEqual(agent.s4_calls, LIMITS["check_rounds"])      # 上限 3：编码 3 轮、检查 3 次
        types = [json.loads(l)["type"] for l in (rd / "events.jsonl").read_text().splitlines()]
        self.assertIn("limit.exceeded", types)

    def test_a_tool_that_crashes_is_retried_then_needs_human(self):
        agent = CodingAgent(self.root, lambda n, wd: (wd / "a.py").write_text("x\n"))
        calls = []

        def boom(ctx):
            calls.append(1)
            raise OSError("磁盘满了")
        ctrl = Controller(self.root, parse_agents(CFG), parse_roles(CFG), LIMITS, invoke_fn=agent, tools={"check": boom})
        rid = start_run(self.root, "x", "toy", ctrl, today=datetime(2026, 11, 6), kind="pipeline/build")
        rd = self.root / "workspace" / "runs" / rid
        ctrl.run_all(rd, log=lambda m: None)
        self.assertEqual(Run(rd).read()["status"], "needs-human")
        self.assertEqual(len(calls), LIMITS["step_retries"] + 1)
        self.assertEqual(agent.s4_calls, 1)                           # 工具自己坏了不该让编码白做一遍

    def test_done_without_any_change_is_invalid_then_needs_human(self):
        agent, rd = self.go(lambda n, wd: None)                     # 每次都不写任何文件
        st = Run(rd).read()
        self.assertEqual(st["status"], "needs-human")
        self.assertEqual(agent.s4_calls, LIMITS["step_retries"] + 1)  # 重试用完
        types = [json.loads(l)["type"] for l in (rd / "events.jsonl").read_text().splitlines()]
        self.assertEqual(types.count("step.retried"), LIMITS["step_retries"])

    def test_retry_starts_from_a_clean_workdir(self):
        seen = []

        def on_s4(n, wd):
            seen.append(sorted(p.name for p in wd.iterdir() if p.name != ".git"))
            if n == 1:
                (wd / "junk.txt").write_text("上次的半成品，没有产生有效改动之外的东西")
                # 第一次只留垃圾文件会算有改动；为了触发重试，这里让第一次什么都不算：删掉它再返回
                (wd / "junk.txt").unlink()
            else:
                (wd / "real.py").write_text("x = 1\n")
        agent, rd = self.go(on_s4)
        self.assertEqual(Run(rd).read()["status"], "done")
        self.assertEqual(seen[1], [".gitignore"])                      # 第 2 次开始时只有起点自带的 .gitignore

    def test_design_kind_never_touches_a_workdir(self):
        agent = CodingAgent(self.root, lambda n, wd: None)
        ctrl = Controller(self.root, parse_agents(CFG), parse_roles(CFG), LIMITS, invoke_fn=agent)
        rid = start_run(self.root, "只要设计", "toy", ctrl, today=datetime(2026, 11, 6))
        ctrl.run_all(self.root / "workspace" / "runs" / rid, log=lambda m: None)
        self.assertFalse((self.root / "workspace" / "projects").exists())

    def test_workdir_stays_inside_workspace(self):
        wd = workdir_of(self.root, {"id": "R1", "project": "toy"})
        self.assertTrue(str(wd).startswith(str(self.root / "workspace")))


if __name__ == "__main__":
    unittest.main()
