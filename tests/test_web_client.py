import json
import shutil
import tempfile
import unittest
from pathlib import Path

from cockpit.pipeline import SetupError
from cockpit.store import Run
from web.api import (
    AUTODEV_ROOT,
    evaluate_srs_rules_detail,
    get_config_view,
    get_run_detail,
    list_pipeline_runs,
    list_srs_documents,
    redact_secrets,
    submit_human_decision,
    update_roles_config,
)
from requirements.handoff import handoff_srs_to_pipeline


class TestWebUnifiedClient(unittest.TestCase):
    def test_web_srs_document_passes_all_9_rules_and_extracts_relations(self):
        srs_path = AUTODEV_ROOT / "docs" / "requirements" / "REQ-WEB-UNIFIED_CLIENT-20261107.md"
        self.assertTrue(srs_path.is_file())
        content = srs_path.read_text(encoding="utf-8")
        detail = evaluate_srs_rules_detail(content)

        self.assertTrue(detail["is_valid"], f"SRS 校验未通过: {detail['errors']}")
        self.assertEqual(detail["sections_ready_count"], 9)
        self.assertEqual(detail["scale"], "Epic")
        self.assertTrue(len(detail["relations"]) >= 3)
        self.assertIn("AutoDev 本机工作台", detail["wireframe"])
        self.assertTrue(all(r["passed"] for r in detail["rules"]))

    def test_handoff_to_s2_and_cockpit_run_detail_and_human_reply(self):
        srs_path = AUTODEV_ROOT / "docs" / "requirements" / "REQ-WEB-UNIFIED_CLIENT-20261107.md"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copy(AUTODEV_ROOT / "config.yaml", root / "config.yaml")
            req_dir = root / "docs" / "requirements"
            req_dir.mkdir(parents=True, exist_ok=True)
            local_srs = req_dir / srs_path.name
            shutil.copy(srs_path, local_srs)

            docs = list_srs_documents(root)
            self.assertEqual(len(docs), 1)
            self.assertTrue(docs[0]["is_valid"])

            # 1. 从 Web 触发直通 S2 架构设计（使用完整 S1~S9 的 pipeline/build 模板）
            info = handoff_srs_to_pipeline(local_srs, root=root, project="autodev", kind="pipeline/build")
            rid = info["run_id"]
            self.assertEqual(info["stage"], "S2")

            runs = list_pipeline_runs(root)
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["id"], rid)
            self.assertEqual(runs[0]["stage"], "S2")

            # 2. 读取 S1~S9 阶段详情，验证 S1 已完成、S2 处于 running
            detail = get_run_detail(root, rid)
            s1_info = next(s for s in detail["stages"] if s["code"] == "S1")
            s2_info = next(s for s in detail["stages"] if s["code"] == "S2")
            self.assertEqual(s1_info["ui_status"], "complete")
            self.assertEqual(s2_info["ui_status"], "running")
            self.assertIn("analysis.md", s1_info["rounds"][0]["artifacts"])

            # 3. 模拟进入 needs-human 状态并通过 Web 提交人工回复
            run = Run(root / "workspace" / "runs" / rid)
            st = run.load()
            st["status"] = "needs-human"
            st["human"] = {"waiting": True, "pending_decision": "gate:S9", "resume_to": None}
            st["stage"] = "S9"
            run.commit(st, "human.requested", data={"gate": "S9"})

            res = submit_human_decision(root, rid, action="continue", note="Web端批准发布", stage="S9")
            self.assertTrue(res["ok"])
            self.assertEqual(res["run"]["state"]["status"], "active")
            self.assertEqual(len(res["run"]["human_replies"]), 1)
            self.assertIn("Web端批准发布", res["run"]["human_replies"][0]["content"])

    def test_config_optimistic_lock_and_d008_vendor_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copy(AUTODEV_ROOT / "config.yaml", root / "config.yaml")
            cfg = get_config_view(root)

            # 违反 D008：将 designer 和 design_reviewer 设为同一厂商 (anthropic)
            with self.assertRaises(SetupError):
                update_roles_config(
                    root,
                    new_roles={"designer": "claude-opus", "design_reviewer": "claude-sonnet"},
                    expected_hash=cfg["version_hash"],
                )

            # 乐观锁哈希不匹配时拒绝保存
            with self.assertRaises(ValueError):
                update_roles_config(
                    root,
                    new_roles={"analyst": "claude-sonnet"},
                    expected_hash="wrong_hash_000",
                )

            # 合法更新（analyst 切换为 claude-sonnet）
            updated = update_roles_config(
                root,
                new_roles={"analyst": "claude-sonnet"},
                expected_hash=cfg["version_hash"],
            )
            self.assertEqual(updated["roles"]["analyst"], "claude-sonnet")

    def test_redact_secrets(self):
        raw = 'app_secret = "9f8e7d6c5b4a3210" and key sk-1234567890abcdefghij'
        clean = redact_secrets(raw)
        self.assertNotIn("9f8e7d6c5b4a3210", clean)
        self.assertNotIn("sk-1234567890abcdefghij", clean)
        self.assertIn("***REDACTED***", clean)

    def test_http_server_endpoints_end_to_end(self):
        import threading
        import urllib.request
        from http.server import ThreadingHTTPServer
        from web.server import make_handler

        srs_path = AUTODEV_ROOT / "docs" / "requirements" / "REQ-WEB-UNIFIED_CLIENT-20261107.md"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copy(AUTODEV_ROOT / "config.yaml", root / "config.yaml")
            req_dir = root / "docs" / "requirements"
            req_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(srs_path, req_dir / srs_path.name)

            httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(root))
            port = httpd.server_address[1]
            t = threading.Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            try:
                # 1. GET /
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
                    html = resp.read().decode("utf-8")
                    self.assertIn("AutoDev 统一网页工作台", html)
                    self.assertIn("S1~S9 流水线驾驶舱", html)

                # 2. GET /api/overview
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/overview") as resp:
                    ov = json.loads(resp.read().decode("utf-8"))
                    self.assertTrue(ov["ok"])
                    self.assertEqual(len(ov["srs_list"]), 1)

                # 3. POST /api/srs/handoff
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/srs/handoff",
                    data=json.dumps({"filename": srs_path.name, "project": "autodev"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req) as resp:
                    ho = json.loads(resp.read().decode("utf-8"))
                    self.assertTrue(ho["ok"])
                    rid = ho["handoff"]["run_id"]
                    self.assertEqual(ho["handoff"]["stage"], "S2")

                # 4. GET /api/run?id=...
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/run?id={rid}") as resp:
                    r_data = json.loads(resp.read().decode("utf-8"))
                    self.assertTrue(r_data["ok"])
                    self.assertEqual(r_data["run"]["state"]["stage"], "S2")
            finally:
                httpd.shutdown()
                httpd.server_close()


if __name__ == "__main__":
    unittest.main()
