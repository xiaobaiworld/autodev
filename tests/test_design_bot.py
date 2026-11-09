import tempfile
import unittest
from pathlib import Path

from requirements import design_bot


class DesignBotConfigTests(unittest.TestCase):
    def write(self, body):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "config.design.toml"
        path.write_text(body, encoding="utf-8")
        return path

    def test_loads_credentials_and_whitelist(self):
        path = self.write('[feishu]\napp_id = "cli_x"\napp_secret = "s"\n[allow]\nusers = ["ou_1"]\n')
        cfg = design_bot.load_design_config(path)
        self.assertEqual((cfg.app_id, cfg.app_secret, cfg.allow_users), ("cli_x", "s", {"ou_1"}))
        self.assertFalse(cfg.discover_mode)

    def test_empty_whitelist_is_rejected(self):
        path = self.write('[feishu]\napp_id = "cli_x"\napp_secret = "s"\n')
        with self.assertRaisesRegex(design_bot.DesignBotError, "白名单"):
            design_bot.load_design_config(path)

    def test_discover_mode_allows_empty_whitelist(self):
        path = self.write('[feishu]\napp_id = "cli_x"\napp_secret = "s"\n[allow]\ndiscover = true\n')
        cfg = design_bot.load_design_config(path)
        self.assertTrue(cfg.discover_mode)
        self.assertEqual(cfg.allow_users, set())

    def test_missing_credentials_are_rejected(self):
        path = self.write('[allow]\nusers = ["ou_1"]\n')
        with self.assertRaisesRegex(design_bot.DesignBotError, "app_id"):
            design_bot.load_design_config(path)


class DesignBotDecisionTests(unittest.TestCase):
    def test_discover_mode_never_replies(self):
        cfg = design_bot.DesignConfig("a", "b", set(), True)
        self.assertEqual(design_bot.decide(cfg, "ou_x", "你好"), ("record", "ou_x"))

    def test_unauthorized_user_is_refused(self):
        cfg = design_bot.DesignConfig("a", "b", {"ou_1"}, False)
        action, text = design_bot.decide(cfg, "ou_other", "/help")
        self.assertEqual(action, "reply")
        self.assertIn("授权", text)

    def test_authorized_help_and_unknown_command(self):
        cfg = design_bot.DesignConfig("a", "b", {"ou_1"}, False)
        self.assertIn("/help", design_bot.decide(cfg, "ou_1", "/help")[1])
        self.assertIn("/help", design_bot.decide(cfg, "ou_1", "随便说点什么")[1])

    def test_blank_message_is_ignored(self):
        cfg = design_bot.DesignConfig("a", "b", {"ou_1"}, False)
        self.assertEqual(design_bot.decide(cfg, "ou_1", "   "), ("ignore", ""))


if __name__ == "__main__":
    unittest.main()
