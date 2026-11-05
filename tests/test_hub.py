import unittest

from driver.hub import RunTracker


def fact(seq, *changes):
    return {"seq": seq, "changes": [{"table": t, "key": str(r.get("id", "")), "row": r} for t, r in changes]}


EV = ("events", {"id": 1, "key": "R1-S1-1", "type": "stage.s1"})
LINK = ("run_events", {"event_id": 1, "run_id": 7})


def run(state, **kw):
    return ("runs", dict({"id": 7, "rule": "S1", "state": state, "attempts": 0, "error": None, "summary": None}, **kw))


class TrackerTest(unittest.TestCase):
    def feed(self, *facts):
        t = RunTracker()
        for f in facts:
            t.feed(f)
        return t

    def test_unknown_event_has_no_status(self):
        self.assertIsNone(RunTracker().status("R1-S1-1"))

    def test_event_without_run_yet(self):
        t = self.feed(fact(1, EV))
        self.assertIsNone(t.status("R1-S1-1"))

    def test_queued_then_claimed_is_running(self):
        t = self.feed(fact(1, EV, LINK, run("queued")), fact(2, run("claimed")))
        self.assertEqual(t.status("R1-S1-1")["state"], "running")

    def test_nothing_and_done_are_ended(self):
        for end in ("nothing", "done", "cancelled"):
            with self.subTest(end):
                t = self.feed(fact(1, EV, LINK, run("queued")), fact(2, run(end, summary="一句话")))
                s = t.status("R1-S1-1")
                self.assertEqual((s["state"], s["summary"]), ("ended", "一句话"))

    def test_failed_goes_back_to_queued_and_is_retrying_not_ended(self):
        t = self.feed(fact(1, EV, LINK, run("queued")), fact(2, run("claimed")),
                      fact(3, run("queued", attempts=1, error="超过 3 分钟还没结束，已停止")))
        s = t.status("R1-S1-1")
        self.assertEqual((s["state"], s["attempts"]), ("retrying", 1))
        self.assertIn("超过", s["error"])

    def test_retry_then_success_is_ended(self):
        t = self.feed(fact(1, EV, LINK, run("queued")), fact(2, run("queued", attempts=1, error="x")),
                      fact(3, run("claimed", attempts=1)), fact(4, run("nothing", attempts=1)))
        self.assertEqual(t.status("R1-S1-1")["state"], "ended")

    def test_rows_deleted_are_ignored_and_seq_advances(self):
        t = self.feed(fact(5, EV), {"seq": 6, "changes": [{"table": "due", "key": "x", "row": None}]})
        self.assertEqual(t.seq, 6)

    def test_other_event_not_confused(self):
        t = self.feed(fact(1, EV, LINK, run("nothing")),
                      fact(2, ("events", {"id": 2, "key": "R1-S2-1"}), ("run_events", {"event_id": 2, "run_id": 8}),
                           ("runs", {"id": 8, "state": "queued", "attempts": 0})))
        self.assertEqual(t.status("R1-S1-1")["state"], "ended")
        self.assertEqual(t.status("R1-S2-1")["state"], "running")


if __name__ == "__main__":
    unittest.main()
