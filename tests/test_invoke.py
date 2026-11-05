import json
import tempfile
import unittest
from pathlib import Path

from cockpit.invoke import invoke


class FakeHc:
    """模拟一个窗格。script: 发出启动命令后第几次 get 起 done.json 出现、Agent 何时退出。"""

    def __init__(self, run_dir, write_done_after=2, exits=True, lost_after=None):
        self.dir = Path(run_dir)
        self.fg = "zsh"
        self.sent, self.keyed, self.gets = [], [], 0
        self.write_done_after, self.exits, self.lost_after = write_done_after, exits, lost_after
        self.killed = False
        self.fg_name = None

    def get(self, pane):
        self.gets += 1
        if self.lost_after is not None and self.gets > self.lost_after:
            return None
        if self.fg == "agent" and self.gets >= self.write_done_after:
            (self.dir / "done.json").write_text('{"ok":true}')
        # 和真实 hc 一致：回到 shell 时前台 pid 等于窗格 pid；Agent 名字可以叫 bash
        return {"pid": 1, "foreground": {"name": self.fg_name or self.fg,
                                         "pid": 1 if self.fg == "zsh" else 2}}

    def send(self, pane, text):
        self.sent.append(text)
        if "agent" in text and self.fg == "zsh":
            self.fg = "agent"

    def keys(self, pane, *keys):
        self.keyed.append(keys)
        if self.exits:
            self.fg = "zsh"

    def kill(self, pane):
        self.killed = True


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def run(hc, d, timeout=60):
    c = Clock()
    return invoke(hc, "t18", d, "run agent {input}", "请读 input.md", timeout_s=timeout,
                  exit_keys=("ctrl+c", "ctrl+c"), clock=c.now, sleep=c.sleep)


class InvokeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        (self.d / "input.md").write_text("task")

    def tearDown(self):
        self.tmp.cleanup()

    def test_success(self):
        hc = FakeHc(self.d)
        r = run(hc, self.d)
        self.assertEqual(r, {"ok": True, "reason": None})
        self.assertIn("clear", hc.sent[0])
        self.assertIn(str(self.d / "input.md"), hc.sent[0])
        self.assertEqual(hc.sent[1], "请读 input.md")
        self.assertEqual(hc.keyed, [("ctrl+c", "ctrl+c")])
        self.assertEqual(hc.fg, "zsh")

    def test_stale_done_removed_first(self):
        (self.d / "done.json").write_text('{"ok":true}')
        hc = FakeHc(self.d, write_done_after=10**6)
        r = run(hc, self.d, timeout=5)
        self.assertEqual(r["reason"], "timeout")

    def test_timeout_still_exits_agent(self):
        hc = FakeHc(self.d, write_done_after=10**6)
        r = run(hc, self.d, timeout=5)
        self.assertEqual(r, {"ok": False, "reason": "timeout"})
        self.assertEqual(hc.fg, "zsh")

    def test_pane_lost(self):
        hc = FakeHc(self.d, write_done_after=10**6, lost_after=3)
        r = run(hc, self.d)
        self.assertEqual(r, {"ok": False, "reason": "pane_lost"})

    def test_cannot_exit_escalates_but_never_kills(self):
        hc = FakeHc(self.d, exits=False)
        r = run(hc, self.d)
        self.assertEqual(r, {"ok": False, "reason": "agent_blocked"})
        self.assertFalse(hc.killed)
        self.assertEqual(hc.keyed, [("ctrl+c", "ctrl+c"), ("esc", "ctrl+c", "ctrl+c"), ("ctrl+d",)])

    def test_exits_on_second_escalation(self):
        hc = FakeHc(self.d, exits=False)
        orig = hc.keys

        def keys(pane, *k):
            orig(pane, *k)
            if k[0] == "esc":
                hc.fg = "zsh"
        hc.keys = keys
        self.assertEqual(run(hc, self.d), {"ok": True, "reason": None})
        self.assertEqual(len(hc.keyed), 2)

    def test_agent_named_bash_is_not_a_shell(self):
        hc = FakeHc(self.d, exits=False)
        hc.fg_name = "bash"
        self.assertEqual(run(hc, self.d)["reason"], "agent_blocked")

    def test_bad_done_json(self):
        hc = FakeHc(self.d)
        orig = hc.get

        def get(p):
            res = orig(p)
            if (self.d / "done.json").exists():
                (self.d / "done.json").write_text("{oops")
            return res
        hc.get = get
        self.assertEqual(run(hc, self.d), {"ok": False, "reason": "invalid_output"})


if __name__ == "__main__":
    unittest.main()
