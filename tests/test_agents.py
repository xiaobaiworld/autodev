import unittest
from pathlib import Path

from cockpit.agents import launch_cmd, parse_agents, parse_roles

CFG = Path(__file__).resolve().parents[1] / "config.yaml"


class AgentsTest(unittest.TestCase):
    def setUp(self):
        self.text = CFG.read_text(encoding="utf-8")

    def test_parse_real_config(self):
        a = parse_agents(self.text)
        self.assertEqual(a["claude-opus"]["model"], "ai-code-with/claude-opus-5-5")
        self.assertEqual(a["codex"]["effort"], "low")
        self.assertEqual(parse_roles(self.text)["design_reviewer"], "codex")

    def test_codex_readonly_vs_writable(self):
        a = parse_agents(self.text)["codex"]
        self.assertIn("--sandbox read-only", launch_cmd(a, "/x", writable=False))
        self.assertIn("--sandbox workspace-write", launch_cmd(a, "/x"))
        self.assertIn("-c model_reasoning_effort=low", launch_cmd(a, "/x"))

    def test_claude_uses_full_id_never_alias(self):
        cmd = launch_cmd(parse_agents(self.text)["claude-opus"], "/x")
        self.assertIn("--model ai-code-with/claude-opus-5-5", cmd)

    def test_unknown_cli(self):
        with self.assertRaises(ValueError):
            launch_cmd({"cli": "agy", "model": "m"}, "/x")


if __name__ == "__main__":
    unittest.main()
