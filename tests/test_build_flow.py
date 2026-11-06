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
LIMITS = {"design_review_rounds": 3, "check_rounds": 3, "code_review_rounds": 3, "step_retries": 2,
          "step_timeout_minutes": 60}
OUTS = {"S1": ["analysis.md"], "S2": ["design.md", "dev-plan.md"], "S3": ["review.md"], "S4": ["exec-report.md"],
        "S6": ["review.md"]}
VERDICT = {"S1": "ACCEPT", "S2": "DONE", "S3": "PASS", "S4": "DONE"}


class CodingAgent:
    """所有阶段都按 input.md 写产物；S4 时按 on_s4(次数, 代码目录) 往代码目录写文件；
    S6 时按 s6 结论队列给结论（用完给 PASS），并调用 on_s6(次数, 代码目录)（用来模拟审查者越权改代码）。"""

    def __init__(self, root, on_s4, s6=("PASS",), on_s6=None):
        self.root, self.on_s4, self.s4_calls, self.inputs = Path(root), on_s4, 0, []
        self.s6, self.on_s6, self.s6_calls = list(s6), on_s6, 0

    def __call__(self, sd, timeout_s):
        fm = (Path(sd) / "input.md").read_text(encoding="utf-8")
        g = lambda k: re.search(rf"^{k}: (.+)$", fm, re.M).group(1).strip()
        stage, rid = g("stage"), g("id")
        self.inputs.append((stage, int(g("round")), fm))
        wd = self.root / "workspace" / "projects" / "toy" / rid
        verdict = VERDICT.get(stage)
        if stage == "S4":
            self.s4_calls += 1
            self.on_s4(self.s4_calls, wd)
        if stage == "S6":
            self.s6_calls += 1
            verdict = self.s6.pop(0) if self.s6 else "PASS"
            if self.on_s6:
                self.on_s6(self.s6_calls, wd)
        for f in OUTS[stage]:
            (Path(sd) / f).write_text("## 原文对照\nx\n" if f == "review.md" else "x")   # 审查产物必须有这个小节
        (Path(sd) / "done.json").write_text(json.dumps({
            "id": rid, "stage": stage, "round": int(g("round")), "role": g("role"), "outputs": OUTS[stage],
            "verdict": verdict, "summary": "测试"}))
        return {"ok": True, "reason": None}


class BuildFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def go(self, on_s4, check_verdicts=("PASS",), s6=("PASS",), on_s6=None):
        """check_verdicts: 每次 S5 的结论（用完后一直给最后一个）。假检查把调用次数记在 self.checks。
        s6: 每次 S6 的结论（用完给 PASS）；on_s6(次数, 代码目录)：模拟审查者的动作。"""
        agent = CodingAgent(self.root, on_s4, s6=s6, on_s6=on_s6)
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

    def test_full_run_ends_after_s6_with_patch_check_and_review(self):
        agent, rd = self.go(lambda n, wd: (wd / "todo.py").write_text("print('hi')\n"))
        st = Run(rd).read()
        self.assertEqual((st["status"], st["stage"]), ("done", "S6"))
        self.assertIn("todo.py", (rd / "S4-code" / "round-1" / "diff.patch").read_text())
        self.assertTrue((rd / "S5-check" / "round-1" / "check.log").exists())
        self.assertIn("todo.py", (rd / "S6-code-review" / "round-1" / "full.patch").read_text())   # 审查者看完整改动
        s6_input = next(t for s, r, t in agent.inputs if s == "S6")
        self.assertIn("full.patch", s6_input)
        self.assertIn("本轮检查结果", s6_input)
        self.assertIn("只读", s6_input)
        self.assertEqual(st["step"]["role"], "code_reviewer")
        self.assertEqual(st["step"]["agent"], "claude-opus")           # 审查者与编码者（codex）厂商不同

    def test_s5_is_a_tool_step_not_an_agent(self):
        agent, rd = self.go(lambda n, wd: (wd / "todo.py").write_text("print('hi')\n"))
        events = [json.loads(l) for l in (rd / "events.jsonl").read_text().splitlines()]
        started = [e for e in events if e["type"] == "step.started" and e["stage"] == "S5"]
        self.assertEqual(started[0]["data"]["agent"], "tool:check")    # S5 记成程序步骤，不是 Agent

    def test_code_review_rework_goes_back_to_s4_without_the_passing_check_log(self):
        agent, rd = self.go(lambda n, wd: (wd / "todo.py").write_text(f"v{n}\n"), s6=("REWORK", "PASS"))
        self.assertEqual((Run(rd).read()["status"], Run(rd).read()["stage"]), ("done", "S6"))
        self.assertEqual((agent.s4_calls, agent.s6_calls), (2, 2))
        s4_round2 = next(t for s, r, t in agent.inputs if s == "S4" and r == 2)
        self.assertIn("上轮代码审查意见", s4_round2)                     # 要处理审查意见
        self.assertIn("S6-code-review/round-1/review.md", s4_round2)
        self.assertNotIn("上轮检查结果（由程序运行测试得到", s4_round2)    # S5 上一轮是通过的，不能当作“没通过”的结果塞给编码者
        # 第 2 轮审查看到的是从最初起点到现在的完整改动，不只是增量
        full2 = (rd / "S6-code-review" / "round-2" / "full.patch").read_text()
        self.assertIn("+v2", full2)
        self.assertNotIn("+v1", full2)                                 # 起点到现在，v1 已被改成 v2，最终内容只有 v2

    def test_code_review_every_time_rework_hits_the_round_limit(self):
        agent, rd = self.go(lambda n, wd: (wd / "todo.py").write_text(f"v{n}\n"), s6=("REWORK",) * 5)
        st = Run(rd).read()
        self.assertEqual((st["status"], st["stage"]), ("needs-human", "S6"))
        self.assertEqual(agent.s6_calls, LIMITS["code_review_rounds"])

    def test_reviewer_that_edits_code_is_caught_and_the_code_restored(self):
        def meddle(n, wd):
            if n == 1:
                (wd / "todo.py").write_text("被审查者改过\n")              # 审查者越权改代码，然后放行
        agent, rd = self.go(lambda n, wd: (wd / "todo.py").write_text("原始\n"), on_s6=meddle)
        st = Run(rd).read()
        self.assertEqual(agent.s6_calls, 2)                              # 第 1 次作废，重试了一次
        self.assertEqual((st["status"], st["stage"]), ("done", "S6"))
        self.assertEqual((workdir_of(self.root, {"id": rd.name, "project": "toy"}) / "todo.py").read_text(), "原始\n")
        types = [json.loads(l)["type"] for l in (rd / "events.jsonl").read_text().splitlines()]
        self.assertIn("step.failed", types)
        detail = [json.loads(l)["data"].get("detail") for l in (rd / "events.jsonl").read_text().splitlines()
                  if json.loads(l)["type"] == "step.failed"]
        self.assertTrue(any("审查者修改了代码目录" in (d or "") for d in detail))

    def test_check_failure_goes_back_to_s4_and_fixes_on_top_of_existing_code(self):
        def on_s4(n, wd):
            if n == 1:
                (wd / "todo.py").write_text("bug\n")
            else:
                (wd / "todo.py").write_text("fixed\n")                # 第 2 轮在已有代码上改
        agent, rd = self.go(on_s4, check_verdicts=("FAIL", "PASS"))
        self.assertEqual((Run(rd).read()["status"], Run(rd).read()["stage"]), ("done", "S6"))
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
