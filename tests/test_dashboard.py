import unittest
from datetime import datetime, timezone

from dashboard.render import render, fmt_elapsed

NOW = datetime(2026, 11, 5, 16, 10, 0, tzinfo=timezone.utc)


def state(**kw):
    base = {"now": "2026-11-05T16:10:00.000Z",
            "totals": {"running": 0, "queued": 0, "retrying": 0, "attention": 0},
            "cards": [], "agents": [], "runs": [], "spending": {"today": {"rounds": 0, "cost": 0, "missingCost": 0}}}
    base.update(kw)
    return base


def run(rid, rule, agent, st, **kw):
    r = {"id": rid, "rule": rule, "agent": agent, "state": st, "attempts": 0, "createdAt": "2026-11-05T16:00:00.000Z",
         "claimedAt": None, "finishedAt": None, "summary": None, "error": None}
    r.update(kw)
    return r


PIPE = {"id": "R20261105-001", "status": "active", "stage": "S3", "round": 2,
        "step": {"state": "running", "role": "design_reviewer", "agent": "codex"},
        "counters": {"design_review_rounds": 1}, "human": {"waiting": False}}


class ElapsedTest(unittest.TestCase):
    def test_values(self):
        self.assertEqual(fmt_elapsed("2026-11-05T16:08:48.000Z", NOW), "01:12")
        self.assertEqual(fmt_elapsed("2026-11-05T14:08:00.000Z", NOW), "2:02:00")
        self.assertEqual(fmt_elapsed(None, NOW), "-")
        self.assertEqual(fmt_elapsed("坏的", NOW), "-")
        self.assertEqual(fmt_elapsed("2026-11-05T16:30:00.000Z", NOW), "00:00")  # 未来时间不出负数


class RenderTest(unittest.TestCase):
    def test_no_hub(self):
        out = render(None, [], NOW, error="连不上中台：refused")
        self.assertIn("连不上中台", out)
        self.assertNotIn("Traceback", out)

    def test_empty_hub(self):
        out = render(state(), [], NOW)
        self.assertIn("没有进行中的需求", out)
        self.assertIn("待你决定：0", out)

    def test_pipeline_line(self):
        out = render(state(), [PIPE], NOW)
        self.assertIn("R20261105-001", out)
        self.assertIn("S3", out)
        self.assertIn("第 2 轮", out)
        self.assertIn("design_reviewer", out)

    def test_runs_listed_with_state_and_elapsed(self):
        runs = [run(1, "s3-design_reviewer", "codex", "claimed", claimedAt="2026-11-05T16:08:48.000Z"),
                run(2, "s1", "claude-opus", "nothing", finishedAt="2026-11-05T16:01:00.000Z", summary="ok")]
        out = render(state(runs=runs, totals={"running": 1, "queued": 0, "retrying": 0, "attention": 0}), [], NOW)
        self.assertRegex(out, r"codex\s+运行中\s+01:12")
        self.assertRegex(out, r"claude-opus\s+已结束")
        self.assertIn("运行中 1", out)

    def test_retrying_shows_attempts_and_error(self):
        runs = [run(3, "s2", "claude-opus", "queued", attempts=2, error="超过 15 分钟还没结束，已停止")]
        out = render(state(runs=runs), [], NOW)
        self.assertIn("重试中", out)
        self.assertIn("第 2 次", out)
        self.assertIn("超过 15 分钟", out)

    def test_cards_count_and_titles(self):
        cards = [{"id": 5, "title": "要不要继续", "kind": "ask", "state": "open"},
                 {"id": 6, "title": "已处理的", "kind": "notice", "state": "done"}]
        out = render(state(cards=cards), [], NOW)
        self.assertIn("待你决定：1", out)
        self.assertIn("要不要继续", out)
        self.assertNotIn("已处理的", out)

    def test_offline_agent_flagged(self):
        agents = [{"id": "codex", "name": "codex", "online": False, "seenAt": "2026-11-05T15:00:00.000Z"}]
        self.assertIn("离线", render(state(agents=agents), [], NOW))

    def test_long_error_is_truncated_to_one_line(self):
        runs = [run(4, "s1", "a", "queued", attempts=1, error="x" * 400 + "\n第二行")]
        out = render(state(runs=runs), [], NOW)
        self.assertTrue(all(len(l) < 160 for l in out.splitlines()))

    def test_only_recent_runs_shown(self):
        runs = [run(i, "s1", "a", "nothing", finishedAt="2026-11-05T16:01:00.000Z") for i in range(1, 40)]
        out = render(state(runs=runs), [], NOW, max_runs=10)
        self.assertEqual(out.count("已结束"), 10)


if __name__ == "__main__":
    unittest.main()
