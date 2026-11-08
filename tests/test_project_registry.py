import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cockpit import projects
from cockpit.pipeline import _snapshot_project_context
from web.api import list_projects


class ProjectRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / "README.md").write_text("test project", encoding="utf-8")
        self.config = self.root / "config.yaml"
        self.config.write_text("projects:\n\nagent_registry: config/agents.toml\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def register(self, name="demo", repo=None, **kwargs):
        return projects.register_project(self.root, name, repo or self.repo, **kwargs)

    def test_registered_entry_is_read_by_web_and_pipeline(self):
        result = self.register(init_git=True)
        self.assertEqual(result["status"], "registered")
        self.assertEqual(list_projects(self.root), [{"name": "demo", "repo": str(self.repo.resolve())}])
        out = self.root / "snapshot"
        _snapshot_project_context(self.root, {"project": "demo"}, out)
        self.assertIn("README.md", (out / "manifest.md").read_text(encoding="utf-8"))

    def test_rejects_invalid_or_duplicate_name_and_path(self):
        with self.assertRaises(projects.RegistryError):
            self.register("_bad")
        self.register(init_git=True)
        other = self.root / "other"
        other.mkdir()
        with self.assertRaises(projects.RegistryError):
            self.register("demo", other)
        with self.assertRaises(projects.RegistryError):
            self.register("other", self.repo)

    def test_missing_directory_asks_first_and_creates_nothing(self):
        original = self.config.read_text(encoding="utf-8")
        target = self.root / "new" / "app"
        result = self.register("fresh", target)
        self.assertEqual(result, {"status": "needs_init", "missing": True})
        self.assertFalse(target.exists())
        self.assertFalse(target.parent.exists())
        self.assertEqual(self.config.read_text(encoding="utf-8"), original)

    def test_missing_directory_is_created_locally_after_consent(self):
        target = self.root / "new" / "app"
        result = self.register("fresh", target, init_git=True)
        self.assertEqual(result["status"], "registered")
        self.assertTrue((target / ".git").is_dir())
        self.assertEqual(list_projects(self.root), [{"name": "fresh", "repo": str(target.resolve())}])
        remotes = subprocess.run(["git", "-C", str(target), "remote"], capture_output=True, text=True)
        self.assertEqual(remotes.stdout.strip(), "")

    def test_missing_directory_still_checks_name_and_duplicate_path_first(self):
        self.register(init_git=True)
        with self.assertRaises(projects.RegistryError):
            self.register("demo", self.root / "elsewhere", init_git=True)
        self.assertFalse((self.root / "elsewhere").exists())
        with self.assertRaises(projects.RegistryError):
            self.register("_bad", self.root / "elsewhere", init_git=True)
        self.assertFalse((self.root / "elsewhere").exists())

    def test_rejects_path_that_is_a_file(self):
        afile = self.root / "afile"
        afile.write_text("x", encoding="utf-8")
        with self.assertRaises(projects.RegistryError):
            self.register("filey", afile, init_git=True)

    def test_non_git_directory_waits_then_initializes(self):
        original = self.config.read_text(encoding="utf-8")
        result = self.register()
        self.assertEqual(result, {"status": "needs_init", "missing": False})
        self.assertEqual(self.config.read_text(encoding="utf-8"), original)
        result = self.register(init_git=True)
        self.assertEqual(result["status"], "registered")
        self.assertTrue((self.repo / ".git").exists())

    def test_optimistic_lock_conflict(self):
        with self.assertRaisesRegex(projects.RegistryError, "乐观锁"):
            self.register(init_git=True, expected_hash="stale")

    def test_post_write_verification_failure_restores_original(self):
        original = self.config.read_text(encoding="utf-8")
        with patch.object(projects, "_entries", side_effect=[[], []]):
            with self.assertRaisesRegex(projects.RegistryError, "写入后"):
                self.register(init_git=True)
        self.assertEqual(self.config.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
