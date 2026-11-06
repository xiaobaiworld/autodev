import json
import tempfile
import unittest
from pathlib import Path

from cockpit.tools import run_release, run_usage
from cockpit.workdir import prepare


class ToolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.work = prepare(self.root / "work")
        self.run = self.root / "run"

    def tearDown(self):
        self.tmp.cleanup()

    def state(self, stage="S7U"):
        folder = self.run / stage
        return {"id": "R1", "project": "toy", "stage": stage, "round": 1,
                "workdir": str(self.work), "step": {"dir": stage, "role": "user-simulator"}}

    def test_usage_passes_and_records_original_output(self):
        state = self.state()
        script = [{"cmd": ["python3", "-c", "import os; print(os.environ['HOME'])"],
                   "contains": [str(self.run / "S7U/scratch")]}]
        template = {"stages": {"S7U": {"tool": "usage", "outputs": ["usage.log"], "script": script}}}
        self.assertEqual(run_usage(self.run, state, template["stages"]["S7U"]), "PASS")
        text = (self.run / "S7U/usage.log").read_text()
        self.assertIn("退出码：0", text)
        done = json.loads((self.run / "S7U/done.json").read_text())
        self.assertEqual(done["summary"], "使用验证通过")

    def test_usage_stops_after_first_failed_expectation(self):
        state = self.state()
        marker = self.work / "later"
        script = [
            {"cmd": ["python3", "-c", "print('unexpected')"], "contains": ["required-token"]},
            {"cmd": ["python3", "-c", f"open({str(marker)!r}, 'w').write('ran')"]},
        ]
        spec = {"tool": "usage", "outputs": ["usage.log"], "script": script}
        self.assertEqual(run_usage(self.run, state, spec), "FAIL")
        self.assertFalse(marker.exists())

    def test_release_tags_are_local_and_final_writes_changelog(self):
        (self.work / "main.py").write_text("print('ready')\n")
        from cockpit.workdir import checkpoint
        checkpoint(self.work, "Add product")
        s7 = self.state("S7")
        s7["step"]["role"] = "releaser"
        rc_spec = {"tool": "release", "outputs": ["release.log"], "tag": "rc", "version": "0.1.0"}
        self.assertEqual(run_release(self.run, s7, rc_spec), "PASS")
        s9 = self.state("S9")
        s9["step"]["role"] = "publisher"
        final_spec = dict(rc_spec, tag="final", note="demo todo")
        self.assertEqual(run_release(self.run, s9, final_spec), "PASS")
        tags = __import__("subprocess").run(["git", "-C", str(self.work), "tag", "--list"],
                                          text=True, capture_output=True, check=True).stdout.splitlines()
        self.assertEqual(tags, ["v0.1.0", "v0.1.0-rc.1"])
        self.assertTrue((self.work / "CHANGELOG.md").exists())
        self.assertNotIn("origin", __import__("subprocess").run(["git", "-C", str(self.work), "remote", "-v"],
                                          text=True, capture_output=True, check=True).stdout)


if __name__ == "__main__":
    unittest.main()
