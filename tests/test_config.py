import unittest
from cockpit.config import parse_cockpit, ConfigError

OK = """agents:
  x:
    cli: a
cockpit:
  claim: label
  refresh_seconds: 2   # 注释
  panes: [claude-opus, codex, agy]
limits:
  a: 1
"""


class ConfigTest(unittest.TestCase):
    def test_ok(self):
        c = parse_cockpit(OK)
        self.assertEqual(c, {"claim": "label", "refresh_seconds": 2,
                             "panes": ["claude-opus", "codex", "agy"]})

    def test_missing_section(self):
        with self.assertRaisesRegex(ConfigError, "cockpit"):
            parse_cockpit("agents:\n  x: 1\n")

    def test_bad_claim(self):
        with self.assertRaisesRegex(ConfigError, "claim"):
            parse_cockpit(OK.replace("claim: label", "claim: magic"))

    def test_missing_panes(self):
        with self.assertRaisesRegex(ConfigError, "panes"):
            parse_cockpit(OK.replace("  panes: [claude-opus, codex, agy]\n", ""))

    def test_bad_refresh(self):
        with self.assertRaisesRegex(ConfigError, "refresh_seconds"):
            parse_cockpit(OK.replace("refresh_seconds: 2", "refresh_seconds: 0"))


if __name__ == "__main__":
    unittest.main()
