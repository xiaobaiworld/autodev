import tempfile
import unittest
from pathlib import Path

from cockpit.workdir import WorkdirError, checkpoint, fingerprint, full_patch, head, prepare, restore, tag


class WorkdirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.path = prepare(self.root / "project")

    def tearDown(self):
        self.tmp.cleanup()

    def test_checkpoint_and_patch(self):
        (self.path / "app.py").write_text("print('ok')\n")
        rev = checkpoint(self.path, "Add app")
        self.assertEqual(head(self.path), rev)
        self.assertIn("app.py", full_patch(self.path))

    def test_fingerprint_detects_content_and_mode_changes(self):
        app = self.path / "app.py"
        app.write_text("one")
        before = fingerprint(self.path)
        app.write_text("two")
        self.assertNotEqual(before, fingerprint(self.path))

    def test_restore_removes_untracked_reviewer_changes(self):
        rev = head(self.path)
        (self.path / "unexpected.py").write_text("changed")
        restore(self.path, rev)
        self.assertFalse((self.path / "unexpected.py").exists())

    def test_tag_is_local_and_cannot_be_overwritten(self):
        tag(self.path, "v0.1.0-rc.1")
        with self.assertRaises(WorkdirError):
            tag(self.path, "v0.1.0-rc.1")


if __name__ == "__main__":
    unittest.main()
