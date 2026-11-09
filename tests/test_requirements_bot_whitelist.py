import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RequirementsBotWhitelistTests(unittest.TestCase):
    def run_daemon(self, body):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "config.req.toml"
            cfg.write_text(body, encoding="utf-8")
            env = {**os.environ, "AUTODEV_REQ_CONFIG": str(cfg), "PYTHONPATH": str(ROOT / "src")}
            return subprocess.run([sys.executable, "-m", "requirements.feishu_daemon"], env=env, cwd=tmp, capture_output=True, text=True, timeout=30)

    def test_empty_whitelist_refuses_before_connecting(self):
        r = self.run_daemon('[feishu]\napp_id = "cli_x"\napp_secret = "s"\n[allow]\nusers = []\n')
        self.assertEqual(r.returncode, 1)
        self.assertIn("不允许对所有人开放", r.stderr)
        self.assertNotIn("正在连接飞书", r.stderr)


if __name__ == "__main__":
    unittest.main()
