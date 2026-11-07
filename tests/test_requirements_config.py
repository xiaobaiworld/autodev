import os
import tempfile
import unittest
from requirements.config import load_req_config
from requirements.session import ReqSessionStore


class TestRequirementsConfig(unittest.TestCase):
    def test_load_req_config(self):
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
            f.write("""
default_agent = "cc"
task_timeout = 600
output_limit = 2000
default_cwd = "/tmp/test"

[feishu]
app_id = "test_app"
app_secret = "test_sec"

[allow]
users = ["user1"]
dirs = ["/tmp"]
""")
            path = f.name

        try:
            cfg = load_req_config(path)
            self.assertEqual(cfg.app_id, "test_app")
            self.assertEqual(cfg.app_secret, "test_sec")
            self.assertEqual(cfg.default_agent, "cc")
            self.assertEqual(cfg.task_timeout, 600)
            self.assertIn("user1", cfg.allow_users)
        finally:
            os.unlink(path)

    def test_session_store(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            store = ReqSessionStore(path, "/tmp/default", "cc")
            s = store.get("c1")
            self.assertEqual(s["cwd"], "/tmp/default")
            store.update_session_id("c1", "sid-1")
            self.assertEqual(store.get("c1")["session_id"], "sid-1")
            store.reset_session("c1")
            self.assertEqual(store.get("c1")["session_id"], "")
        finally:
            if os.path.exists(path):
                os.unlink(path)


if __name__ == "__main__":
    unittest.main()
