import tempfile
import unittest
from pathlib import Path

from cockpit.workdir import GitError, head, prepare, reset, snapshot


class WorkdirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wd = Path(self.tmp.name) / "projects" / "demo" / "R1"

    def tearDown(self):
        self.tmp.cleanup()

    def test_prepare_creates_repo_with_seed_and_is_idempotent(self):
        base = prepare(self.wd, {"README.md": "hi\n", "pkg/a.py": "x = 1\n"})
        self.assertEqual((self.wd / "pkg" / "a.py").read_text(), "x = 1\n")
        (self.wd / "new.txt").write_text("没提交的改动")
        self.assertEqual(prepare(self.wd, {"README.md": "不该覆盖"}), base)   # 重复调用返回同一个起点
        self.assertEqual((self.wd / "README.md").read_text(), "hi\n")      # 也不覆盖已有文件
        self.assertTrue((self.wd / "new.txt").exists())                    # 也不清理改动

    def test_snapshot_lists_modified_new_and_deleted_files_and_writes_patch(self):
        base = prepare(self.wd, {"a.py": "x = 1\n", "gone.py": "bye\n"})
        (self.wd / "a.py").write_text("x = 2\n")
        (self.wd / "tests").mkdir()
        (self.wd / "tests" / "test_a.py").write_text("assert True\n")
        (self.wd / "gone.py").unlink()
        patch = Path(self.tmp.name) / "diff.patch"
        files = snapshot(self.wd, base, patch)
        self.assertEqual(files, ["a.py", "gone.py", "tests/test_a.py"])
        text = patch.read_text()
        self.assertIn("-x = 1", text)
        self.assertIn("+x = 2", text)
        self.assertIn("tests/test_a.py", text)
        self.assertEqual(head(self.wd), base)                              # snapshot 不产生提交

    def test_snapshot_does_not_leave_files_staged(self):
        base = prepare(self.wd, {"a.py": "1\n"})
        (self.wd / "b.py").write_text("2\n")
        snapshot(self.wd, base, Path(self.tmp.name) / "p.patch")
        status = (self.wd / ".git").exists() and __import__("subprocess").run(
            ["git", "status", "--porcelain"], cwd=self.wd, capture_output=True, text=True).stdout
        self.assertEqual(status.strip(), "?? b.py")

    def test_reset_returns_to_base_and_removes_untracked(self):
        base = prepare(self.wd, {"a.py": "x = 1\n"})
        (self.wd / "a.py").write_text("changed\n")
        (self.wd / "junk").mkdir()
        (self.wd / "junk" / "f.txt").write_text("x")
        reset(self.wd, base)
        self.assertEqual((self.wd / "a.py").read_text(), "x = 1\n")
        self.assertFalse((self.wd / "junk").exists())

    def test_no_changes_gives_empty_patch_and_no_files(self):
        base = prepare(self.wd, {"a.py": "1\n"})
        patch = Path(self.tmp.name) / "d.patch"
        self.assertEqual(snapshot(self.wd, base, patch), [])
        self.assertEqual(patch.read_text(), "")

    def test_reset_refuses_a_directory_that_is_not_a_repo(self):
        plain = Path(self.tmp.name) / "plain"
        plain.mkdir()
        (plain / "precious.txt").write_text("别删")
        with self.assertRaises(GitError):
            reset(plain, "HEAD")
        self.assertTrue((plain / "precious.txt").exists())


if __name__ == "__main__":
    unittest.main()
