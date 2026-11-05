import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cockpit.store import LockError, Run, StateError, acquire_lock, atomic_write

BASE = {"id": "R1", "stage": "S1", "round": 1, "seq": 0}


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_atomic_write_leaves_no_tmp(self):
        p = self.dir / "a" / "x.json"
        atomic_write(p, "hi")
        self.assertEqual(p.read_text(), "hi")
        self.assertEqual([f.name for f in p.parent.iterdir()], ["x.json"])

    def test_lock_second_holder_refused(self):
        lock = acquire_lock(self.dir / ".lock")
        with self.assertRaises(LockError):
            acquire_lock(self.dir / ".lock")
        lock.close()
        acquire_lock(self.dir / ".lock").close()

    def test_lock_released_when_holder_killed(self):
        code = f"import sys,time;sys.path.insert(0,'src');from cockpit.store import acquire_lock;" \
               f"f=acquire_lock({str(self.dir / '.lock')!r});print('ok',flush=True);time.sleep(60)"
        p = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
        self.assertEqual(p.stdout.readline().strip(), "ok")
        with self.assertRaises(LockError):
            acquire_lock(self.dir / ".lock")
        p.kill()
        p.wait()
        p.stdout.close()
        acquire_lock(self.dir / ".lock").close()

    def test_commit_increments_seq_and_matches_events(self):
        r = Run(self.dir / "R1")
        s = r.commit(BASE, "request.claimed")
        s = r.commit(s, "stage.entered")
        self.assertEqual(r.read()["seq"], 2)
        self.assertEqual(r.load()["seq"], 2)
        lines = r.events_path.read_text().splitlines()
        self.assertEqual([json.loads(x)["seq"] for x in lines], [1, 2])

    def test_repair_when_crash_between_event_and_state(self):
        r = Run(self.dir / "R1")
        s = r.commit(BASE, "request.claimed")
        # 模拟只写了事件、没写 state：手工追加 seq=2 的事件
        s2 = dict(s, seq=2, stage="S2")
        ev = {"seq": 2, "id": "R1", "type": "stage.entered", "stage": "S2", "round": 1,
              "data": {"state_after": s2}}
        with open(r.events_path, "a") as f:
            f.write(json.dumps(ev) + "\n")
        fixed = r.load()
        self.assertEqual(fixed["stage"], "S2")
        self.assertEqual(r.read()["seq"], fixed["seq"])
        self.assertEqual(json.loads(r.events_path.read_text().splitlines()[-1])["type"], "state.repaired")

    def test_gap_larger_than_one_is_error(self):
        r = Run(self.dir / "R1")
        s = r.commit(BASE, "request.claimed")
        with open(r.events_path, "a") as f:
            f.write(json.dumps({"seq": 5, "data": {}}) + "\n")
        with self.assertRaises(StateError):
            r.load()


if __name__ == "__main__":
    unittest.main()
