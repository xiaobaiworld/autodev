# 定位: server.py AutoDev 全系统统一本机网页客户端 HTTP 服务入口（仅监听 127.0.0.1，遵循 D010 与设计 9.4）。
from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from cockpit.store import atomic_write
from requirements.handoff import HandoffVerificationError, handoff_srs_to_pipeline
from requirements.llm_provider import load_model_registry
from requirements.session import ReqSessionStore
from web.api import (
    AUTODEV_ROOT,
    WEB_CHAT_ID,
    evaluate_srs_rules_detail,
    generate_srs_template,
    get_config_view,
    get_run_detail,
    list_pipeline_runs,
    list_srs_documents,
    load_audit_log,
    redact_secrets,
    run_web_req_turn,
    set_web_req_type,
    submit_human_decision,
    update_roles_config,
)

UI_HTML_PATH = Path(__file__).resolve().parent / "ui.html"


def make_handler(root_dir: Path):
    class AutoDevWebHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            pass

        def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def _read_body_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            qs = parse_qs(parsed.query)

            if path in ("/", "/index.html"):
                html_bytes = UI_HTML_PATH.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html_bytes)))
                self.end_headers()
                self.wfile.write(html_bytes)
                return

            try:
                if path == "/api/overview":
                    registry = load_model_registry(root_dir / "config.yaml")
                    models = [
                        {
                            "name": s.name,
                            "cli": s.cli,
                            "vendor": s.vendor,
                            "full_model_id": s.full_model_id,
                            "effort": s.effort,
                            "supported_tasks": s.supported_tasks,
                            "unsupported_tasks": s.unsupported_tasks,
                            "unverified_tasks": s.unverified_tasks,
                            "capability_notes": s.capability_notes,
                            "invocation_mode": s.invocation_mode,
                        }
                        for s in registry.values()
                    ]
                    store = ReqSessionStore(str(root_dir / ".req_session.json"), str(root_dir), "claude-sonnet")
                    active_cid = store.get_active_chat_id(WEB_CHAT_ID)
                    self._send_json({
                        "ok": True,
                        "srs_list": list_srs_documents(root_dir),
                        "runs": list_pipeline_runs(root_dir),
                        "models": models,
                        "session": store.get(active_cid),
                        "active_chat_id": active_cid,
                        "audit_log": load_audit_log(root_dir, limit=20),
                        "config": get_config_view(root_dir),
                    })
                    return

                if path == "/api/srs":
                    fname = (qs.get("file") or [""])[0]
                    if not fname or "/" in fname or "\\" in fname or not fname.endswith(".md"):
                        self._send_json({"ok": False, "error": "非法文件名"}, status=400)
                        return
                    fpath = root_dir / "docs" / "requirements" / fname
                    if not fpath.is_file():
                        self._send_json({"ok": False, "error": f"找不到需求文件: {fname}"}, status=404)
                        return
                    content = redact_secrets(fpath.read_text(encoding="utf-8"))
                    self._send_json({
                        "ok": True,
                        "filename": fname,
                        "content": content,
                        "validation": evaluate_srs_rules_detail(content),
                    })
                    return

                if path == "/api/srs/template":
                    req_type = (qs.get("type") or ["SOFTWARE"])[0]
                    self._send_json(generate_srs_template(root_dir, req_type=req_type))
                    return

                if path == "/api/run":
                    rid = (qs.get("id") or [""])[0]
                    if not rid or "/" in rid or "\\" in rid:
                        self._send_json({"ok": False, "error": "非法运行编号"}, status=400)
                        return
                    detail = get_run_detail(root_dir, rid)
                    self._send_json({"ok": True, "run": detail})
                    return

                self._send_json({"ok": False, "error": f"未知接口: {path}"}, status=404)
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, status=500)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            try:
                body = self._read_body_json()

                if path == "/api/srs/validate":
                    content = str(body.get("content") or "")
                    self._send_json({
                        "ok": True,
                        "validation": evaluate_srs_rules_detail(content),
                    })
                    return

                if path == "/api/srs/save":
                    fname = str(body.get("filename") or "").strip()
                    content = str(body.get("content") or "").strip()
                    if not fname or "/" in fname or "\\" in fname or not fname.startswith("REQ-") or not fname.endswith(".md"):
                        self._send_json({"ok": False, "error": "文件名必须符合 REQ-*.md 规范"}, status=400)
                        return
                    detail = evaluate_srs_rules_detail(content)
                    clean = content.rstrip()
                    if "<!-- SPEC-VALIDATED:" not in clean:
                        if detail["is_valid"]:
                            clean += "\n\n<!-- SPEC-VALIDATED: PASS -->\n"
                        else:
                            clean += f"\n\n<!-- SPEC-VALIDATED: FAIL - {'; '.join(detail['errors'])} -->\n"
                    req_dir = root_dir / "docs" / "requirements"
                    req_dir.mkdir(parents=True, exist_ok=True)
                    atomic_write(req_dir / fname, clean)
                    self._send_json({
                        "ok": True,
                        "filename": fname,
                        "validation": detail,
                        "srs_list": list_srs_documents(root_dir),
                    })
                    return

                if path == "/api/srs/handoff":
                    fname = str(body.get("filename") or "").strip()
                    project = str(body.get("project") or "").strip() or None
                    kind = str(body.get("kind") or "pipeline/build").strip()
                    if not fname or "/" in fname or "\\" in fname:
                        self._send_json({"ok": False, "error": "请指定有效的 REQ-*.md 文件名"}, status=400)
                        return
                    fpath = root_dir / "docs" / "requirements" / fname
                    try:
                        info = handoff_srs_to_pipeline(
                            srs_path=fpath,
                            root=root_dir,
                            project=project,
                            kind=kind,
                        )
                        self._send_json({
                            "ok": True,
                            "handoff": info,
                            "runs": list_pipeline_runs(root_dir),
                        })
                    except HandoffVerificationError as e:
                        self._send_json({"ok": False, "error": f"移交被程序强核验拦截（拒绝交接 S2，D016）：{e}"}, status=400)
                    except Exception as e:
                        self._send_json({"ok": False, "error": f"移交异常：{e}"}, status=500)
                    return

                if path == "/api/req/type":
                    req_type = str(body.get("req_type") or "AUTO").strip()
                    res = set_web_req_type(root_dir, req_type=req_type)
                    self._send_json(res)
                    return

                if path == "/api/req/chat":
                    user_text = str(body.get("message") or "").strip()
                    agent_name = str(body.get("agent") or "").strip() or None
                    mode = str(body.get("mode") or "").strip() or None
                    req_type = str(body.get("req_type") or "").strip() or None
                    if not user_text:
                        self._send_json({"ok": False, "error": "消息不能为空"}, status=400)
                        return
                    res = run_web_req_turn(
                        root_dir,
                        user_text,
                        agent_name=agent_name,
                        mode=mode,
                        req_type=req_type,
                    )
                    self._send_json(res)
                    return

                if path == "/api/run/reply":
                    run_id = str(body.get("run_id") or "").strip()
                    action = str(body.get("action") or "").strip()
                    note = str(body.get("note") or "").strip()
                    stage = str(body.get("stage") or "").strip() or None
                    res = submit_human_decision(root_dir, run_id=run_id, action=action, note=note, stage=stage)
                    self._send_json(res)
                    return

                if path == "/api/config/roles":
                    new_roles = dict(body.get("roles") or {})
                    expected_hash = str(body.get("version_hash") or "")
                    updated = update_roles_config(root_dir, new_roles=new_roles, expected_hash=expected_hash)
                    self._send_json({"ok": True, "config": updated})
                    return

                self._send_json({"ok": False, "error": f"未知接口: {path}"}, status=404)
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, status=400)

    return AutoDevWebHandler


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="启动 AutoDev 全系统统一本机网页客户端 (仅监听 127.0.0.1)")
    ap.add_argument("--port", type=int, default=int(os.environ.get("AUTODEV_WEB_PORT", "8765")), help="监听端口 (默认 8765)")
    ap.add_argument("--root", default=str(AUTODEV_ROOT), help="AutoDev 根目录")
    args = ap.parse_args(argv)

    root_dir = Path(args.root).resolve()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(root_dir))
    print(f"🌐 AutoDev 统一网页客户端已启动: http://127.0.0.1:{args.port} (root={root_dir})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
