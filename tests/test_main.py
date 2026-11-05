import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cockpit import main as m
from cockpit.claim import ClaimError


def put(root, rid, status, updated):
    d = root / "workspace" / "runs" / rid
    d.mkdir(parents=True)
    (d / "state.json").write_text(json.dumps(
        {"id": rid, "status": status, "updated_at": updated}), encoding="utf-8")


class LoadRunTest(unittest.TestCase):
    def test_picks_latest_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            put(root, "R1", "active", "2026-11-05T09:00:00+08:00")
            put(root, "R2", "active", "2026-11-05T10:00:00+08:00")
            put(root, "R3", "done", "2026-11-05T11:00:00+08:00")
            self.assertEqual(m.load_run(root)["id"], "R2")

    def test_none_when_no_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(m.load_run(Path(tmp)))

    def test_skips_broken_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            put(root, "R1", "active", "2026-11-05T09:00:00+08:00")
            bad = root / "workspace" / "runs" / "R2"
            bad.mkdir()
            (bad / "state.json").write_text("{not json", encoding="utf-8")
            self.assertEqual(m.load_run(root)["id"], "R1")


class FrameTest(unittest.TestCase):
    def test_hc_failure_becomes_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(m, "hc_json", side_effect=ClaimError("hc 连不上")):
                out = m.frame({"codex": "t18"}, Path(tmp))
        self.assertIn("读取失败", out)
        self.assertIn("hc 连不上", out)


if __name__ == "__main__":
    unittest.main()
