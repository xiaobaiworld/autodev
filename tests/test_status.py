import unittest
from datetime import datetime, timezone, timedelta

from cockpit.status import pane_state, render, elapsed

NOW = datetime(2026, 11, 5, 9, 41, 12, tzinfo=timezone(timedelta(hours=8)))


def term(fg="zsh", status=None):
    return {"address": "t18", "foreground": {"name": fg}, "status": status}


def step(state="running", agent="codex", role="design_reviewer",
         started="2026-11-05T09:40:00+08:00"):
    return {"state": state, "agent": agent, "role": role, "started_at": started}


# (说明, 角色, 窗格, 步骤, 期望)
CASES = [
    ("hc 工作中且步骤运行", "codex", term("codex", {"state": "working"}), step("running"), "运行中"),
    ("步骤运行但 hc 已报 done（等主控收尾）", "codex", term("codex", {"state": "done"}), step("running"), "运行中"),
    ("步骤待启动", "codex", term("zsh"), step("pending"), "等待"),
    ("步骤结束且窗格回到 shell", "codex", term("zsh"), step("finished"), "已结束"),
    ("步骤失败且窗格回到 shell", "codex", term("zsh"), step("failed"), "已结束"),
    ("步骤结束但 Agent 还没退出", "codex", term("codex", {"state": "done"}), step("finished"), "运行中"),
    ("窗格不在 hc ls 里", "codex", None, step("running"), "丢失"),
    ("窗格消失且无步骤", "agy", None, None, "丢失"),
    ("当前步骤是别的 Agent", "agy", term("zsh"), step("running", agent="codex"), "空闲"),
    ("没有进行中的需求", "agy", term("zsh"), None, "空闲"),
]


class StateTest(unittest.TestCase):
    def test_table(self):
        for name, role, t, s, want in CASES:
            with self.subTest(name):
                self.assertEqual(pane_state(role, t, s), want)


class ElapsedTest(unittest.TestCase):
    def test_elapsed(self):
        self.assertEqual(elapsed("2026-11-05T09:40:00+08:00", NOW), "01:12")

    def test_missing_or_future(self):
        self.assertEqual(elapsed(None, NOW), "-")
        self.assertEqual(elapsed("2026-11-05T09:50:00+08:00", NOW), "00:00")

    def test_bad_value(self):
        self.assertEqual(elapsed("not-a-time", NOW), "-")


SNAPSHOT = """\
AutoDev  R20261105-001  S3  第 1 轮
──────────────────────────────────────────────
 窗格   Agent        角色             状态    用时
 t1b    claude-opus  -                空闲    -
 t18    codex        design_reviewer  运行中  01:12
 t19    agy          -                丢失    -
待你决定：0
"""


class RenderTest(unittest.TestCase):
    def test_snapshot(self):
        run = {"id": "R20261105-001", "stage": "S3", "round": 1,
               "step": step("running"), "human": {"waiting": False}}
        panes = {"claude-opus": "t1b", "codex": "t18", "agy": "t19"}
        terms = {"t1b": term("zsh"), "t18": term("codex", {"state": "working"})}
        self.assertEqual(render(run, panes, terms, NOW), SNAPSHOT)

    def test_no_run(self):
        out = render(None, {"codex": "t18"}, {"t18": term()}, NOW)
        self.assertIn("没有进行中的需求", out)
        self.assertIn("空闲", out)

    def test_waiting_count(self):
        run = {"id": "R1", "stage": "S2", "round": 1, "step": None,
               "human": {"waiting": True, "pending_decision": "decision-1"}}
        out = render(run, {"codex": "t18"}, {"t18": term()}, NOW)
        self.assertIn("待你决定：1", out)


if __name__ == "__main__":
    unittest.main()
