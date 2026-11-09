import tempfile
import unittest
from pathlib import Path

from requirements import bots

GOOD = '[bots.a]\ndescription = "A"\nmodule = "m.a"\nconfig_file = "a.toml"\nconfig_env = "A_CFG"\nlabel = "com.x.a"\nstages = ["S1"]\nruns_on = "home-mac"\n'


class BotsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def write(self, name, body):
        p = self.dir / name
        p.write_text(body, encoding="utf-8")
        return p

    def test_repo_manifest_is_valid_and_labels_unique(self):
        loaded = bots.load_manifest()
        self.assertEqual(set(loaded), {"req", "design"})
        self.assertEqual(loaded["req"]["label"], "com.autodev.req-bot")

    def test_missing_field_is_rejected(self):
        p = self.write("m.toml", GOOD.replace('label = "com.x.a"\n', ""))
        with self.assertRaisesRegex(bots.BotError, "label"):
            bots.load_manifest(p)

    def test_duplicate_label_is_rejected(self):
        p = self.write("m.toml", GOOD + GOOD.replace("[bots.a]", "[bots.b]"))
        with self.assertRaisesRegex(bots.BotError, "标签重复"):
            bots.load_manifest(p)

    def test_select_refuses_other_environment(self):
        loaded = bots.load_manifest(self.write("m.toml", GOOD))
        self.assertEqual(bots.select(loaded, "a", env="home-mac")["label"], "com.x.a")
        with self.assertRaisesRegex(bots.BotError, "拒绝安装"):
            bots.select(loaded, "a", env="office-mac")
        with self.assertRaisesRegex(bots.BotError, "没有机器人"):
            bots.select(loaded, "nope", env="home-mac")

    def test_empty_whitelist_is_refused_unless_discover(self):
        empty = self.write("c1.toml", '[feishu]\napp_id = "x"\n[allow]\nusers = []\n')
        with self.assertRaisesRegex(bots.BotError, "不允许对所有人开放"):
            bots.require_whitelist(empty)
        absent = self.write("c2.toml", '[feishu]\napp_id = "x"\n')
        with self.assertRaises(bots.BotError):
            bots.require_whitelist(absent)
        disc = self.write("c3.toml", '[allow]\ndiscover = true\n')
        bots.require_whitelist(disc)
        ok = self.write("c4.toml", '[allow]\nusers = ["ou_1"]\n')
        bots.require_whitelist(ok)

    def test_missing_config_file_is_refused(self):
        with self.assertRaisesRegex(bots.BotError, "找不到本机配置文件"):
            bots.require_whitelist(self.dir / "nope.toml")


if __name__ == "__main__":
    unittest.main()
