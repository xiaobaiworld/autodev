import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from cockpit.agents import parse_agents, parse_limits, parse_roles
from cockpit.controller import Controller, start_run
from cockpit.store import Run, acquire_lock
from driver import reply

CFG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"
CFG = CFG_PATH.read_text(encoding="utf-8")


def fake_tool(name, log):
    def run(ctx):
        (Path(ctx["sd"]) / log).write_text(name)
        return {"verdict": "PASS", "summary": f"假 {name}", "outputs": [log]}
    return run


class ReplyCommandTest(unittest.TestCase):
    """driver.reply 的命令行入口。控制器里的人工逻辑在 test_resume / test_build_flow 里测，这里测入口本身：
    参数、锁、错误提示、退出码，以及批准后确实接着往下跑。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "root"
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        (self.home / "config.json").write_text(json.dumps(
            {"url": "http://127.0.0.1:1", "owner": "k", "source": {"key": "s"}}))
        (self.root / "workspace").mkdir(parents=True)
        self.releases = []

        def agent(sd, timeout_s):                                         # 不应被调用：回复之后只剩程序步骤
            raise AssertionError("回复之后不该再调用 Agent")
        self.tools = {"check": fake_tool("check", "check.log"),
                      "release": lambda ctx: (self.releases.append(ctx["spec"]["tag"]) or
                                              fake_tool("release", "release.log")(ctx))}
        ctrl = Controller(self.root, parse_agents(CFG), parse_roles(CFG), parse_limits(CFG), invoke_fn=agent,
                          tools=self.tools)
        rid = start_run(self.root, "x", "toy", ctrl, today=datetime(2026, 11, 7), kind="pipeline/build")
        self.rid, self.rd = rid, self.root / "workspace" / "runs" / rid
        # 直接把需求放到 S9 前的关口，省得跑一遍 S1 到 S8
        st = Run(self.rd).read()
        st = dict(st, stage="S9", round=1, status="needs-human",
                  human={"waiting": True, "pending_decision": "gate:S9", "resume_to": None})
        st["step"] = ctrl._new_step(st, 1)
        Run(self.rd).commit(st, "test.setup")
        (self.root / "workspace" / "projects" / "toy" / rid).mkdir(parents=True)
        self.ctrl = ctrl

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        patched = mock.patch.object(reply, "Controller", lambda *a, **k: self.ctrl)
        hub = mock.patch.object(reply, "Hub", lambda cfg: object())
        with patched, hub, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = reply.main(["--home", str(self.home), "--root", str(self.root), "--config", str(CFG_PATH), *args])
        return code, out.getvalue(), err.getvalue()

    def test_continue_approves_the_gate_and_runs_to_done(self):
        code, out, err = self.run_cli(self.rid, "continue", "--note", "批准")
        self.assertEqual((code, err), (0, ""))
        self.assertIn("现在：needs-human S9 第 1 轮（gate:S9）", out)
        self.assertIn("批准通过 S9", out)
        self.assertIn("结束：done S9", out)
        self.assertEqual(self.releases, ["final"])
        self.assertIn("批准", (self.rd / "human" / "reply-1.md").read_text(encoding="utf-8"))

    def test_reject_exits_zero_and_never_publishes(self):
        code, out, _ = self.run_cli(self.rid, "reject", "--note", "不发")
        self.assertEqual(code, 0)
        self.assertEqual(Run(self.rd).read()["status"], "rejected")
        self.assertEqual(self.releases, [])

    def test_unknown_request_fails_with_a_message_and_nonzero_exit(self):
        code, out, err = self.run_cli("R9999", "continue")
        self.assertEqual(code, 1)
        self.assertIn("失败", err)

    def test_request_that_is_not_waiting_is_refused_and_left_alone(self):
        self.run_cli(self.rid, "reject")
        before = Run(self.rd).read()
        code, out, err = self.run_cli(self.rid, "continue")
        self.assertEqual(code, 1)
        self.assertIn("不在等待人工", err)
        self.assertEqual(Run(self.rd).read(), before)

    def test_a_running_pipeline_holding_the_lock_blocks_the_reply(self):
        held = acquire_lock(self.root / "workspace" / ".lock")           # 模拟流水线正在跑
        try:
            code, out, err = self.run_cli(self.rid, "continue")
        finally:
            held.close()
        self.assertEqual(code, 1)
        self.assertEqual(Run(self.rd).read()["status"], "needs-human")   # 什么都没动
        self.assertEqual(self.releases, [])

    def test_bad_action_is_rejected_by_the_argument_parser(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                self.run_cli(self.rid, "explode")


if __name__ == "__main__":
    unittest.main()
