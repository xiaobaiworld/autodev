import json
import tempfile
import unittest
from pathlib import Path

from requirements import design_view


def make_run(root, rid, project, stage, status, files=None, verdict=None):
    rd = Path(root) / "workspace" / "runs" / rid
    rd.mkdir(parents=True)
    state = {"id": rid, "project": project, "kind": "pipeline/design", "status": status, "stage": stage, "round": 1, "step": None, "human": {"waiting": status == "needs-human"}}
    (rd / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (rd / "events.jsonl").write_text("", encoding="utf-8")
    for rel, body in (files or {}).items():
        p = rd / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    if verdict:
        d = rd / "S3-design-review" / "round-1"
        d.mkdir(parents=True, exist_ok=True)
        (d / "done.json").write_text(json.dumps({"verdict": verdict, "summary": "审查结论摘要"}), encoding="utf-8")


class DesignViewTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        make_run(self.root, "R20261109-001", "alpha", "S3", "active")
        make_run(self.root, "R20261109-002", "beta", "S2", "needs-human")

    def test_list_shows_only_runs_of_the_project(self):
        text = design_view.render_list(self.root, "alpha")
        self.assertIn("R20261109-001", text)
        self.assertNotIn("R20261109-002", text)
        self.assertIn("alpha", text)

    def test_list_with_no_runs_says_so_and_does_not_guess_project(self):
        text = design_view.render_list(self.root, "gamma")
        self.assertIn("没有", text)
        self.assertNotIn("R2026", text)
        self.assertIn("未选择项目", design_view.render_list(self.root, ""))

    def test_status_reports_stage_and_waiting_reason(self):
        text = design_view.render_status(self.root, "R20261109-002", "beta")
        self.assertIn("S2", text)
        self.assertIn("等你决定", text)

    def test_status_refuses_a_run_from_another_project(self):
        text = design_view.render_status(self.root, "R20261109-002", "alpha")
        self.assertIn("不属于", text)
        self.assertNotIn("S2", text)

    def test_unknown_run_is_reported_not_raised(self):
        self.assertIn("找不到", design_view.render_status(self.root, "R20990101-001", "alpha"))
        self.assertIn("编号格式", design_view.render_status(self.root, "../etc/passwd", "alpha"))

    def test_design_package_lists_files_and_review_verdict(self):
        rd = "S2-design/round-1/"
        make_run(self.root, "R20261109-003", "alpha", "S3", "active", files={rd + "design.md": "# 设计稿\n正文A", rd + "dev-plan.md": "# 计划\n任务1", rd + "prototype.md": "# 原型\n不适用"}, verdict="PASS")
        text = design_view.render_design(self.root, "R20261109-003", "alpha")
        for needle in ("设计稿", "开发计划", "原型", "PASS", "审查结论摘要"):
            self.assertIn(needle, text)

    def test_design_package_marks_missing_files_instead_of_inventing(self):
        text = design_view.render_design(self.root, "R20261109-001", "alpha")
        self.assertIn("尚未生成", text)

    def test_long_files_are_truncated_and_secrets_redacted(self):
        rd = "S2-design/round-1/"
        make_run(self.root, "R20261109-004", "alpha", "S3", "active", files={rd + "design.md": "x" * 5000 + "\napi_key = sk-abcdefghijklmnop1234"})
        text = design_view.render_design(self.root, "R20261109-004", "alpha", limit=600)
        self.assertLess(len(text), 2500)
        self.assertIn("已截断", text)
        self.assertNotIn("sk-abcdefghijklmnop1234", text)


if __name__ == "__main__":
    unittest.main()
