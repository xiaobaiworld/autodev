import os
import shutil
import tempfile
import unittest

from requirements.context_detector import (
    build_project_context_summary,
    get_project_modules,
    get_recent_git_commits,
    get_recent_requirement_docs,
)


class TestRequirementsContext(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="autodev_test_ctx_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_get_project_modules(self):
        src_dir = os.path.join(self.test_dir, "src")
        os.makedirs(os.path.join(src_dir, "order"))
        os.makedirs(os.path.join(src_dir, "user"))
        os.makedirs(os.path.join(src_dir, "__pycache__"))
        os.makedirs(os.path.join(src_dir, "tests"))

        modules = get_project_modules(self.test_dir)
        self.assertIn("order", modules)
        self.assertIn("user", modules)
        self.assertNotIn("__pycache__", modules)
        self.assertNotIn("tests", modules)

    def test_get_recent_requirement_docs(self):
        req_dir = os.path.join(self.test_dir, "docs", "requirements")
        os.makedirs(req_dir)

        doc1 = os.path.join(req_dir, "REQ-001.md")
        with open(doc1, "w", encoding="utf-8") as f:
            f.write("# 需求标题\n\n这是用户登录核心目标。\n")

        docs = get_recent_requirement_docs(self.test_dir)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["filename"], "REQ-001.md")
        self.assertIn("这是用户登录核心目标", docs[0]["summary"])

    def test_build_project_context_summary(self):
        # 空目录无崩溃，返回空或极简
        summary_empty = build_project_context_summary(self.test_dir)
        self.assertIsInstance(summary_empty, str)

        # 构造模块与需求
        src_dir = os.path.join(self.test_dir, "src", "billing")
        os.makedirs(src_dir)
        req_dir = os.path.join(self.test_dir, "docs", "requirements")
        os.makedirs(req_dir)
        with open(os.path.join(req_dir, "REQ-2026.md"), "w", encoding="utf-8") as f:
            f.write("计费结算核心功能\n")

        summary = build_project_context_summary(self.test_dir)
        self.assertIn("billing", summary)
        self.assertIn("REQ-2026.md", summary)


if __name__ == "__main__":
    unittest.main()
