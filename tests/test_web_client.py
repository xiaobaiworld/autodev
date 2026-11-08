import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from cockpit.controller import allocate_run_id
from cockpit.pipeline import SetupError, step_dir, wait_reason
from cockpit.store import LockError, Run, acquire_lock
from web.api import (
    AUTODEV_ROOT,
    evaluate_srs_rules_detail,
    generate_srs_template,
    get_config_view,
    get_run_detail,
    list_pipeline_runs,
    list_srs_documents,
    redact_secrets,
    set_web_req_type,
    submit_human_decision,
    update_roles_config,
)
from requirements.handoff import handoff_srs_to_pipeline
from requirements.session import ReqSessionStore


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
            s2_output = root / "workspace" / "runs" / rid / step_dir("S2", 1, "pipeline/build")
            s2_output.mkdir(parents=True, exist_ok=True)
            (s2_output / "prototype.md").write_text("# 原型\n不适用：无 GUI\n", encoding="utf-8")
            refreshed = get_run_detail(root, rid)
            refreshed_s2 = next(s for s in refreshed["stages"] if s["code"] == "S2")
            self.assertIn("prototype.md", refreshed_s2["rounds"][0]["artifacts"])

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

            # C2: 尝试将流水线角色绑定到尚未接入 autoloop 规则生成器的 agy 时明确拦截
            with self.assertRaises(SetupError) as agy_ctx:
                update_roles_config(
                    root,
                    new_roles={"acceptor": "agy"},
                    expected_hash=cfg["version_hash"],
                )
            self.assertIn("仅支持", str(agy_ctx.exception))

            # 合法更新（analyst 切换为 claude-sonnet）
            updated = update_roles_config(
                root,
                new_roles={"analyst": "claude-sonnet"},
                expected_hash=cfg["version_hash"],
            )
            self.assertEqual(updated["roles"]["analyst"], "claude-sonnet")

    def test_o1_o3_o4_c3_optimizations(self):
        from datetime import datetime

        srs_path = AUTODEV_ROOT / "docs" / "requirements" / "REQ-WEB-UNIFIED_CLIENT-20261107.md"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copy(AUTODEV_ROOT / "config.yaml", root / "config.yaml")
            req_dir = root / "docs" / "requirements"
            req_dir.mkdir(parents=True, exist_ok=True)
            local_srs = req_dir / srs_path.name
            shutil.copy(srs_path, local_srs)

            # O1: ReqSessionStore 自动将历史遗留 "cc" 归一为 "claude-sonnet" 并返回活跃飞书会话 ID
            sfile = root / ".req_session.json"
            sfile.write_text(
                json.dumps({"oc_feishu_123": {"cwd": str(root), "agent": "cc", "session_id": "sid-999"}}),
                encoding="utf-8",
            )
            store = ReqSessionStore(str(sfile), str(root), "claude-sonnet")
            self.assertEqual(store.get_active_chat_id(), "oc_feishu_123")
            self.assertEqual(store.get("oc_feishu_123")["agent"], "claude-sonnet")

            # O3: 删除中间编号目录后 allocate_run_id 不会撞号
            fixed_day = datetime(2026, 11, 7)
            (root / "workspace" / "runs" / "R20261107-002").mkdir(parents=True, exist_ok=True)
            next_rid = allocate_run_id(root, today=fixed_day)
            self.assertEqual(next_rid, "R20261107-003")

            # C3: 当 workspace/.lock 被占用时，handoff_srs_to_pipeline 拒绝并发写入
            held_lock = acquire_lock(root / "workspace" / ".lock")
            try:
                with self.assertRaises(LockError):
                    handoff_srs_to_pipeline(local_srs, root=root, project="autodev")
            finally:
                held_lock.close()

            # O4: wait_reason 在看板与 Web 端保持一致
            sample_waiting = {
                "stage": "S9",
                "status": "needs-human",
                "human": {"waiting": True, "pending_decision": "gate:S9"},
                "step": {"state": "pending"},
            }
            self.assertEqual(wait_reason(sample_waiting), "要你批准才进 S9")

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

                # 5. GET /api/srs/template?type=DEPLOYMENT
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/srs/template?type=DEPLOYMENT") as resp:
                    tpl_data = json.loads(resp.read().decode("utf-8"))
                    self.assertTrue(tpl_data["ok"])
                    self.assertEqual(tpl_data["req_type"], "DEPLOYMENT")
                    self.assertTrue(tpl_data["validation"]["is_valid"])

                # 6. POST /api/req/type (人工指定 DEPLOYMENT 与恢复 AUTO)
                req_t = urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/req/type",
                    data=json.dumps({"req_type": "DEPLOYMENT"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req_t) as resp:
                    t_res = json.loads(resp.read().decode("utf-8"))
                    self.assertTrue(t_res["ok"])
                    self.assertEqual(t_res["req_type"], "DEPLOYMENT")
                    self.assertEqual(t_res["req_type_source"], "manual")
            finally:
                httpd.shutdown()
                httpd.server_close()

    def test_deployment_srs_document_and_handoff_to_s2(self):
        deploy_srs_path = AUTODEV_ROOT / "docs" / "requirements" / "REQ-DEPLOY-WEB_DAEMON-20261108.md"
        self.assertTrue(deploy_srs_path.is_file())
        content = deploy_srs_path.read_text(encoding="utf-8")
        detail = evaluate_srs_rules_detail(content)
        self.assertTrue(detail["is_valid"], f"部署 SRS 校验失败: {detail['errors']}")
        self.assertEqual(detail["req_type"], "DEPLOYMENT")
        self.assertIn("deploy/install-web-client.sh", detail["deliverables"])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copy(AUTODEV_ROOT / "config.yaml", root / "config.yaml")
            req_dir = root / "docs" / "requirements"
            req_dir.mkdir(parents=True, exist_ok=True)
            local_srs = req_dir / deploy_srs_path.name
            shutil.copy(deploy_srs_path, local_srs)

            info = handoff_srs_to_pipeline(local_srs, root=root, project="autodev", kind="pipeline/build")
            self.assertEqual(info["req_type"], "DEPLOYMENT")
            self.assertIn("deploy/install-web-client.sh", info["deliverables"])
            s1_text = Path(info["s1_analysis_file"]).read_text(encoding="utf-8")
            self.assertIn("req_type: DEPLOYMENT", s1_text)
            self.assertIn("部署工程与脚本交付指令（DEPLOYMENT）", s1_text)
            self.assertIn("deploy/install-web-client.sh", s1_text)

    def test_web_server_port_and_env(self):
        orig = os.environ.get("AUTODEV_WEB_PORT")
        try:
            os.environ["AUTODEV_WEB_PORT"] = "8999"
            from web.server import main as web_main
            from unittest.mock import patch
            # 验证端口冲突时安全返回退出码 1，不崩溃
            with patch("web.server.ThreadingHTTPServer") as mock_srv:
                err = OSError("Address already in use")
                err.errno = 48
                mock_srv.side_effect = err
                code = web_main(["--root", str(AUTODEV_ROOT)])
                self.assertEqual(code, 1)
                # 验证 mock_srv 收到的端口是环境变量设置的 8999
                mock_srv.assert_called_with(("127.0.0.1", 8999), unittest.mock.ANY)
        finally:
            if orig is not None:
                os.environ["AUTODEV_WEB_PORT"] = orig
            else:
                os.environ.pop("AUTODEV_WEB_PORT", None)


class TestListProjects(unittest.TestCase):
    """网页项目选择器读取 config.yaml 的 projects 列表。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_reads_names_and_repos(self):
        Path(self.tmp, "config.yaml").write_text(
            "projects:\n"
            "  - name: alpha\n"
            "    repo: ~/code/alpha\n"
            "  - name: beta\n"
            "    repo: ~/code/beta\n"
            "limits:\n  check_rounds: 3\n",
            encoding="utf-8",
        )
        from web.api import list_projects
        self.assertEqual(
            list_projects(self.tmp),
            [{"name": "alpha", "repo": "~/code/alpha"}, {"name": "beta", "repo": "~/code/beta"}],
        )

    def test_missing_config_returns_empty(self):
        from web.api import list_projects
        self.assertEqual(list_projects(self.tmp), [])


if __name__ == "__main__":
    unittest.main()
