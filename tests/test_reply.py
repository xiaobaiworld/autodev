import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from cockpit.store import Run
from driver.reply import apply_reply, main
from cockpit.workdir import prepare


class ReplyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        shutil.copy(Path(__file__).resolve().parents[1] / "config.yaml", self.root / "config.yaml")
        self.run_dir = self.root / "workspace/runs/R1"
        self.state = {"id": "R1", "project": "toy", "kind": "pipeline/build", "status": "needs-human",
                      "stage": "S9", "round": 1, "counters": {}, "workdir": str(self.root / "project"),
                      "step": {"state": "pending", "role": "publisher", "agent": None, "model": None,
                               "dir": "S9-publish/round-1", "started_at": None,
                               "deadline_at": None, "attempt": 1, "fail_reason": None},
                      "human": {"waiting": True, "pending_decision": "gate:S9", "resume_to": "S9"}}
        Run(self.run_dir).commit(self.state, "human.gate")

    def tearDown(self):
        self.tmp.cleanup()

    def test_continue_releases_gate_without_new_attempt(self):
        state = apply_reply(self.root, "R1", "continue", "批准")
        self.assertEqual((state["status"], state["stage"], state["step"]["state"], state["step"]["attempt"]),
                         ("active", "S9", "pending", 1))
        self.assertFalse(state["human"]["waiting"])
        self.assertIn("批准", (self.run_dir / "human.md").read_text())

    def test_reject_ends_run(self):
        state = apply_reply(self.root, "R1", "reject")
        self.assertEqual(state["status"], "rejected")

    def test_rework_uses_bound_agent_for_target_role(self):
        state = apply_reply(self.root, "R1", "rework", "修复", "S4")
        self.assertEqual((state["stage"], state["round"], state["step"]["agent"]), ("S4", 2, "codex"))
        self.assertEqual(state["step"]["dir"], "S4-code/round-2")

    def test_cli_continue_runs_final_release(self):
        prepare(self.state["workdir"])
        result = main(["R1", "continue", "--note", "批准", "--root", str(self.root)])
        state = Run(self.run_dir).read()
        tags = subprocess.run(["git", "-C", state["workdir"], "tag", "--list"],
                              capture_output=True, text=True, check=True).stdout.splitlines()
        self.assertEqual(result, 0)
        self.assertEqual(state["status"], "done")
        self.assertIn("v0.1.0", tags)


if __name__ == "__main__":
    unittest.main()
