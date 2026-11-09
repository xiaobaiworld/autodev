import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from requirements import bots


class BotsCliTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def cli(self, *args, env=None):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, env or {}, clear=False):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = bots.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def config(self, users):
        body = '[feishu]\napp_id = "x"\napp_secret = "s"\n[allow]\nusers = ' + users + "\n"
        (self.dir / "config.req.toml").write_text(body, encoding="utf-8")

    def test_list_prints_every_bot(self):
        code, out, _ = self.cli("list")
        self.assertEqual(code, 0)
        self.assertIn("com.autodev.req-bot", out)
        self.assertIn("com.autodev.design-bot", out)

    def test_show_prints_shell_variables_when_allowed(self):
        self.config('["ou_1"]')
        code, out, _ = self.cli("show", "req", "--root", str(self.dir))
        self.assertEqual(code, 0)
        self.assertIn("BOT_MODULE=requirements.feishu_daemon", out)
        self.assertIn("BOT_LABEL=com.autodev.req-bot", out)
        self.assertIn("BOT_CONFIG_ENV=AUTODEV_REQ_CONFIG", out)

    def test_show_refuses_missing_config_empty_whitelist_other_env_unknown_bot(self):
        code, out, err = self.cli("show", "req", "--root", str(self.dir))
        self.assertEqual((code, out), (1, ""))
        self.assertIn("找不到本机配置文件", err)
        self.config("[]")
        code, out, err = self.cli("show", "req", "--root", str(self.dir))
        self.assertEqual((code, out), (1, ""))
        self.assertIn("不允许对所有人开放", err)
        self.config('["ou_1"]')
        code, out, err = self.cli("show", "req", "--root", str(self.dir), env={"AUTODEV_ENV": "office-mac"})
        self.assertEqual((code, out), (1, ""))
        self.assertIn("拒绝安装", err)
        code, out, err = self.cli("show", "nope", "--root", str(self.dir))
        self.assertEqual((code, out), (1, ""))
        self.assertIn("没有机器人", err)

    def test_no_whitelist_check_allows_uninstall_without_config(self):
        code, out, _ = self.cli("show", "design", "--root", str(self.dir), "--no-whitelist-check")
        self.assertEqual(code, 0)
        self.assertIn("BOT_LABEL=com.autodev.design-bot", out)


if __name__ == "__main__":
    unittest.main()
