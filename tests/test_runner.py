import json
import tempfile
import unittest
from pathlib import Path

from cockpit.store import Run
from driver.hub import HubError
from driver.runner import event_id, make_invoke, subject_of

STATE = {"schema_version": 1, "id": "R20261105-001", "stage": "S1", "round": 1, "seq": 0,
         "step": {"role": "analyst", "dir": "S1-analysis/round-1", "attempt": 1}}


def fact(seq, *changes):
    return {"seq": seq, "changes": [{"table": t, "key": "", "row": r} for t, r in changes]}


def run_row(state, **kw):
    return ("runs", dict({"id": 7, "state": state, "attempts": 0, "error": None, "summary": None}, **kw))


EV = ("events", {"id": 1, "key": event_id(STATE)})
LINK = ("run_events", {"event_id": 1, "run_id": 7})


class FakeHub:
    def __init__(self, batches, emit_error=None):
        self.batches, self.emitted, self.cancelled, self.emit_error = list(batches), [], [], emit_error

    def emit(self, *a):
        if self.emit_error:
            raise HubError(self.emit_error)
        self.emitted.append(a)

    def cancel(self, run):
        self.cancelled.append(run)

    def facts(self, after=0, timeout=60):
        if self.batches:
            yield from self.batches.pop(0)


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.tmp.name) / STATE["id"]
        Run(self.run_dir).commit(STATE, "request.claimed")
        self.sd = self.run_dir / STATE["step"]["dir"]
        self.clock = Clock()

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, hub, timeout_s=100, retries=2):
        # 每次读空批次要推进时钟，否则超时测试会死循环
        orig = hub.facts

        def facts(after=0, timeout=60):
            self.clock.sleep(30)
            yield from orig(after, timeout)
        hub.facts = facts
        inv = make_invoke(hub, retries, clock=self.clock.now, sleep=self.clock.sleep)
        return inv(None, "x", self.sd, "", "", timeout_s=timeout_s, exit_keys=("ctrl+c",))

    def test_subject_and_event_id_shape(self):
        s = subject_of(Run(self.run_dir).read())
        self.assertEqual(s, "R20261105-001/S1-analysis/round-1")
        self.assertRegex(s, r"^[A-Za-z0-9#._:/@-]{1,100}$")
        self.assertEqual(event_id(STATE), "R20261105-001-S1-r1-a1")

    def test_success(self):
        hub = FakeHub([[fact(1, EV, LINK, run_row("queued")), fact(2, run_row("claimed")),
                        fact(3, run_row("nothing", summary="ok"))]])
        self.assertEqual(self.call(hub), {"ok": True, "reason": None})
        self.assertEqual(hub.emitted[0][:3], (event_id(STATE), "stage.s1", subject_of(STATE)))

    def test_hub_gave_up_is_command_failed(self):
        hub = FakeHub([[fact(1, EV, LINK, run_row("queued")),
                        fact(2, run_row("cancelled", summary="连续 10 次没跑成，不再自动重试"))]])
        r = self.call(hub)
        self.assertEqual((r["ok"], r["reason"]), (False, "command_failed"))
        self.assertIn("连续 10 次", r["detail"])

    def test_retries_beyond_limit_cancel_the_run(self):
        hub = FakeHub([[fact(1, EV, LINK, run_row("queued")), fact(2, run_row("queued", attempts=3, error="boom"))]])
        r = self.call(hub, retries=2)
        self.assertEqual((r["ok"], r["reason"], hub.cancelled), (False, "command_failed", [7]))

    def test_within_retry_limit_keeps_waiting_until_success(self):
        hub = FakeHub([[fact(1, EV, LINK, run_row("queued")), fact(2, run_row("queued", attempts=1, error="x"))],
                       [fact(3, run_row("claimed", attempts=1)), fact(4, run_row("nothing", attempts=1))]])
        self.assertEqual(self.call(hub), {"ok": True, "reason": None})
        self.assertEqual(hub.cancelled, [])

    def test_timeout_cancels_and_reports(self):
        hub = FakeHub([[fact(1, EV, LINK, run_row("claimed"))]])
        r = self.call(hub, timeout_s=60)
        self.assertEqual((r["ok"], r["reason"], hub.cancelled), (False, "timeout", [7]))

    def test_emit_failure_is_command_failed(self):
        r = self.call(FakeHub([], emit_error="连不上中台"))
        self.assertEqual((r["ok"], r["reason"]), (False, "command_failed"))


if __name__ == "__main__":
    unittest.main()
