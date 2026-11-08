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
LIMITS = {"design_review_rounds": 3, "check_rounds": 3, "code_review_rounds": 3, "usage_rounds": 3,
          "acceptance_rounds": 2, "step_retries": 2, "step_timeout_minutes": 60}
OUTS = {"S1": ["analysis.md"], "S2": ["design.md", "dev-plan.md", "prototype.md"], "S3": ["review.md"], "S4": ["exec-report.md"],
        "S6": ["review.md"], "S8": ["acceptance.md"]}
VERDICT = {"S1": "ACCEPT", "S2": "DONE", "S3": "PASS", "S4": "DONE", "S8": "PASS"}
REVIEW_FILES = ("review.md", "acceptance.md")                          # 这两个产物必须有“原文对照”小节


def fake_usage(ctx):
    """假的使用验证：总是通过。真的使用验证在 test_tools.py 里测。"""
    (Path(ctx["sd"]) / "usage.log").write_text("假使用验证")
    return {"verdict": "PASS", "summary": "假使用验证通过", "outputs": ["usage.log"]}


def fake_release(ctx):
    """假的发布工具：不碰 git，只记下是哪个标签阶段调用的。"""
    tag = ctx["spec"]["tag"]
    (Path(ctx["sd"]) / "release.log").write_text(f"假发布 {tag}")
    return {"verdict": "PASS", "summary": f"假发布 {tag}", "outputs": ["release.log"]}


class CodingAgent:
    """所有阶段都按 input.md 写产物；S4 时按 on_s4(次数, 代码目录) 往代码目录写文件；
    S6 时按 s6 结论队列给结论（用完给 PASS），并调用 on_s6(次数, 代码目录)（用来模拟审查者越权改代码）。"""

    def __init__(self, root, on_s4, s6=("PASS",), on_s6=None, s8=("PASS",)):
        self.root, self.on_s4, self.s4_calls, self.inputs = Path(root), on_s4, 0, []
        self.s6, self.on_s6, self.s6_calls = list(s6), on_s6, 0
        self.s8, self.s8_calls = list(s8), 0

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
        if stage == "S8":
            self.s8_calls += 1
            verdict = self.s8.pop(0) if self.s8 else "PASS"
        for f in OUTS[stage]:
            (Path(sd) / f).write_text("## 原文对照\nx\n" if f in REVIEW_FILES else "x")   # 审查产物必须有这个小节
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

    def go(self, on_s4, check_verdicts=("PASS",), s6=("PASS",), on_s6=None, s8=("PASS",), approve=False):
        """check_verdicts: 每次 S5 的结论（用完后一直给最后一个）。假检查把调用次数记在 self.checks。
        s6 / s8: 每次 S6 / S8 的结论（用完给 PASS）；on_s6(次数, 代码目录)：模拟审查者的动作。
        默认跑到 S9 前的人工关口就停（needs-human），approve=True 则替人批准后继续跑完。"""
        agent = CodingAgent(self.root, on_s4, s6=s6, on_s6=on_s6, s8=s8)
        self.checks, queue = [], list(check_verdicts)

        def fake_check(ctx):
            v = queue.pop(0) if len(queue) > 1 else queue[0]
            self.checks.append((v, sorted(p.name for p in Path(ctx["workdir"]).iterdir() if p.name != ".git")))
            (Path(ctx["sd"]) / "check.log").write_text(f"假检查 {v}")
            return {"verdict": v, "summary": f"假检查 {v}", "outputs": ["check.log"]}
        self.releases = []
        ctrl = Controller(self.root, parse_agents(CFG), parse_roles(CFG), LIMITS, invoke_fn=agent,
                          tools={"check": fake_check, "usage": fake_usage,
                                 "release": lambda c: (self.releases.append(c["spec"]["tag"]) or fake_release(c))})
        rid = start_run(self.root, "做个待办", "toy", ctrl, today=datetime(2026, 11, 6), kind="pipeline/build")
        rd = self.root / "workspace" / "runs" / rid
        ctrl.run_all(rd, log=lambda m: None)
        if approve:
            ctrl.resume(rd, "continue", note="批准发布", stage="S9")
            ctrl.run_all(rd, log=lambda m: None)
        self.ctrl = ctrl
        return agent, rd

    def test_full_run_stops_at_the_s9_gate_with_patch_check_review_and_candidate(self):
        agent, rd = self.go(lambda n, wd: (wd / "todo.py").write_text("print('hi')\n"))
        st = Run(rd).read()
        self.assertEqual((st["status"], st["stage"]), ("needs-human", "S9"))     # 正式发布前停下等人
        self.assertEqual(st["human"]["pending_decision"], "gate:S9")
        self.assertTrue(st["human"]["waiting"])
        self.assertEqual(self.releases, ["rc"])                                  # 只打了候选，正式的还没有
        self.assertFalse((rd / "S9-publish").exists())
        self.assertIn("todo.py", (rd / "S4-code" / "round-1" / "diff.patch").read_text())
        self.assertTrue((rd / "S5-check" / "round-1" / "check.log").exists())
        self.assertIn("todo.py", (rd / "S6-code-review" / "round-1" / "full.patch").read_text())   # 审查者看完整改动
        s6_input = next(t for s, r, t in agent.inputs if s == "S6")
        self.assertIn("full.patch", s6_input)
        self.assertIn("本轮检查结果", s6_input)
        self.assertIn("只读", s6_input)
        events = [json.loads(l) for l in (rd / "events.jsonl").read_text().splitlines()]
        started = {e["stage"]: e["data"] for e in events if e["type"] == "step.started"}
        self.assertEqual((started["S6"]["role"], started["S6"]["agent"]), ("code_reviewer", "claude-opus"))   # 与编码者（codex）厂商不同
        self.assertEqual((started["S8"]["role"], started["S8"]["agent"]), ("acceptor", "claude-opus"))
        self.assertEqual(started["S7"]["agent"], "tool:release")       # 发布候选是程序步骤
        s8_input = next(t for s, r, t in agent.inputs if s == "S8")
        self.assertIn("full.patch", s8_input)
        self.assertIn("只读", s8_input)

    def test_approving_the_gate_publishes_once_and_finishes(self):
        agent, rd = self.go(lambda n, wd: (wd / "todo.py").write_text("print('hi')\n"), approve=True)
        st = Run(rd).read()
        self.assertEqual((st["status"], st["stage"]), ("done", "S9"))
        self.assertEqual(self.releases, ["rc", "final"])
        self.assertEqual(st["human"]["approved"], ["S9"])
        self.assertIn("批准发布", (rd / "human" / "reply-1.md").read_text(encoding="utf-8"))
        self.assertEqual(st["round"], 1)                                # 批准不开新一轮
        types = [json.loads(l)["type"] for l in (rd / "events.jsonl").read_text().splitlines()]
        self.assertEqual(types.count("human.replied"), 1)

    def test_rejecting_at_the_gate_never_publishes(self):
        agent, rd = self.go(lambda n, wd: (wd / "todo.py").write_text("print('hi')\n"))
        self.ctrl.resume(rd, "reject", note="先不发")
        self.assertEqual(Run(rd).read()["status"], "rejected")
        self.assertEqual(self.releases, ["rc"])

    def test_going_back_from_the_gate_does_not_count_as_approval(self):
        agent, rd = self.go(lambda n, wd: (wd / "todo.py").write_text(f"v{n}\n"))
        self.ctrl.resume(rd, "rework", note="再改改", stage="S4")
        st = Run(rd).read()
        self.assertEqual((st["status"], st["stage"]), ("active", "S4"))
        self.assertNotIn("S9", st["human"].get("approved", []))
        self.ctrl.run_all(rd, log=lambda m: None)                       # 重新走完 S4 到 S8，又会停在关口前
        self.assertEqual(Run(rd).read()["human"]["pending_decision"], "gate:S9")
        self.assertEqual(self.releases, ["rc", "rc"])

    def test_acceptance_rework_goes_back_to_s4_and_hits_its_limit(self):
        agent, rd = self.go(lambda n, wd: (wd / "todo.py").write_text(f"v{n}\n"), s8=("REWORK",) * 5)
        st = Run(rd).read()
        self.assertEqual((st["status"], st["stage"]), ("needs-human", "S8"))
        self.assertEqual(agent.s8_calls, LIMITS["acceptance_rounds"])    # 上限 2
        self.assertEqual(self.releases, ["rc"] * LIMITS["acceptance_rounds"])
        self.assertEqual(agent.s4_calls, LIMITS["acceptance_rounds"])

    def test_acceptance_rework_then_pass_reaches_the_gate(self):
        agent, rd = self.go(lambda n, wd: (wd / "todo.py").write_text(f"v{n}\n"), s8=("REWORK", "PASS"))
        st = Run(rd).read()
        self.assertEqual((st["status"], st["stage"], st["human"]["pending_decision"]), ("needs-human", "S9", "gate:S9"))
        self.assertEqual(agent.s8_calls, 2)

    def test_s5_is_a_tool_step_not_an_agent(self):
        agent, rd = self.go(lambda n, wd: (wd / "todo.py").write_text("print('hi')\n"))
        events = [json.loads(l) for l in (rd / "events.jsonl").read_text().splitlines()]
        started = [e for e in events if e["type"] == "step.started" and e["stage"] == "S5"]
        self.assertEqual(started[0]["data"]["agent"], "tool:check")    # S5 记成程序步骤，不是 Agent

    def test_code_review_rework_goes_back_to_s4_without_the_passing_check_log(self):
        agent, rd = self.go(lambda n, wd: (wd / "todo.py").write_text(f"v{n}\n"), s6=("REWORK", "PASS"))
        self.assertEqual((Run(rd).read()["status"], Run(rd).read()["stage"]), ("needs-human", "S9"))
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
        self.assertEqual((st["status"], st["stage"]), ("needs-human", "S9"))
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
        self.assertEqual((Run(rd).read()["status"], Run(rd).read()["stage"]), ("needs-human", "S9"))
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
        ctrl = Controller(self.root, parse_agents(CFG), parse_roles(CFG), LIMITS, invoke_fn=agent,
                          tools={"check": boom, "usage": fake_usage})
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
        self.assertEqual(Run(rd).read()["stage"], "S9")                  # 重试后顺利走到了正式发布前的关口
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
