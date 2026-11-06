import unittest
from pathlib import Path

from cockpit.agents import parse_agents, parse_roles

CFG = Path(__file__).resolve().parents[1] / "config.yaml"


class AgentsTest(unittest.TestCase):
    def setUp(self):
        self.text = CFG.read_text(encoding="utf-8")

    def test_parse_real_config(self):
        a = parse_agents(self.text)
        self.assertEqual(a["claude-opus"]["model"], "ai-code-with/claude-opus-5-5")
        self.assertEqual(a["codex"]["effort"], "low")
        self.assertEqual(parse_roles(self.text)["design_reviewer"], "codex")


if __name__ == "__main__":
    unittest.main()
