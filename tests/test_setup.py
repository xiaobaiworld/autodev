import unittest

import json
import tempfile
from pathlib import Path

from driver.setup import build_rules, install_rules

AGENTS = {
    "claude-opus": {"cli": "claude", "vendor": "anthropic", "model": "ai-code-with/claude-opus-5-5", "effort": "high"},
    "codex": {"cli": "codex", "vendor": "openai", "model": "gpt-6-sol", "effort": "low"},
    "agy": {"cli": "agy", "vendor": "google", "model": "x"},
}
ROLES = {"analyst": "claude-opus", "designer": "claude-opus", "design_reviewer": "codex", "coder": "codex"}
BASE = {"sources": {"local": {"name": "本机"}}, "agents": {"agent": {"worker": "mac1"}}, "rules": [{"name": "old"}]}


class BuildRulesTest(unittest.TestCase):
    def build(self, **kw):
        return build_rules(BASE, AGENTS, ROLES, "/w/workspace", **kw)

    def test_only_used_agents_with_full_model_ids(self):
        r = self.build()
        self.assertEqual(sorted(r["agents"]), ["claude-opus", "codex"])
        self.assertEqual(r["agents"]["claude-opus"]["model"], "ai-code-with/claude-opus-5-5")
        self.assertEqual(r["agents"]["claude-opus"]["use"], "claude")
        self.assertEqual(r["agents"]["codex"]["use"], "codex")
        self.assertEqual(r["agents"]["codex"]["worker"], "mac1")

    def test_effort_override_for_cheap_runs(self):
        self.assertEqual(self.build(effort="low")["agents"]["claude-opus"]["effort"], "low")
        self.assertEqual(self.build()["agents"]["claude-opus"]["effort"], "high")

    def test_one_rule_per_stage_routed_by_role(self):
        r = self.build()
        by = {x["name"]: x for x in r["rules"]}
        self.assertEqual(sorted(by), ["s1-analyst", "s2-designer", "s3-design_reviewer", "s4-coder"])
        self.assertEqual(by["s3-design_reviewer"]["to"], "codex")
        self.assertEqual(by["s4-coder"]["when"], {"source": "local", "types": ["stage.s4"]})
        self.assertEqual(by["s1-analyst"]["when"], {"source": "local", "types": ["stage.s1"]})
        self.assertTrue(all(x["cwd"] == "/w/workspace" for x in r["rules"]))

    def test_does_not_mutate_base_and_drops_old_rules(self):
        r = self.build()
        self.assertEqual(BASE["rules"], [{"name": "old"}])
        self.assertNotIn("old", [x["name"] for x in r["rules"]])

    def test_fake_command_replaces_real_agents(self):
        r = self.build(fake_command=["python3", "fake.py", "{prompt}"])
        self.assertTrue(all(a["use"] == "command" for a in r["agents"].values()))
        self.assertEqual(r["agents"]["codex"]["command"], ["python3", "fake.py", "{prompt}"])

    def test_unsupported_cli_is_rejected(self):
        roles = dict(ROLES, design_reviewer="agy")
        with self.assertRaisesRegex(ValueError, "agy"):
            build_rules(BASE, AGENTS, roles, "/w")


class InstallRulesTest(unittest.TestCase):
    def test_backs_up_old_file_then_writes_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "rules.json").write_text('{"old": true}')
            backup = install_rules(home, {"new": True})
            self.assertEqual(json.loads((home / "rules.json").read_text()), {"new": True})
            self.assertEqual(json.loads(backup.read_text()), {"old": True})
            self.assertTrue(backup.name.startswith("rules.json.bak-"))

    def test_no_backup_when_no_old_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(install_rules(Path(tmp), {"new": True}))
            self.assertEqual(json.loads((Path(tmp) / "rules.json").read_text()), {"new": True})

    def test_same_second_installs_do_not_overwrite_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "rules.json").write_text('{"v": 0}')
            b1 = install_rules(home, {"v": 1})
            b2 = install_rules(home, {"v": 2})
            self.assertNotEqual(b1, b2)
            self.assertEqual(json.loads(b1.read_text()), {"v": 0})
            self.assertEqual(json.loads(b2.read_text()), {"v": 1})


if __name__ == "__main__":
    unittest.main()
