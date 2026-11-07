# 定位: service.py 飞书端与 Web 客户端共享的需求澄清单轮编排、定稿校验归档与原始交互耗时审计服务（O1 收敛）。
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cockpit.store import atomic_write, now_iso
from requirements.agent_runner import run_agent_turn
from requirements.context_detector import build_project_context_summary
from requirements.flow import build_req_prompt, is_finalize_request, normalize_user_input
from requirements.llm_provider import resolve_model_spec
from requirements.presentation import RequirementResponse, extract_semantic_response
from requirements.session import ReqSessionStore
from requirements.validator import ValidationResult, validate_requirement_spec

log = logging.getLogger("autodev.req")


@dataclass(frozen=True)
class ClarificationTurnOutcome:
    ok: bool
    chat_id: str
    reply_text: str
    semantic: RequirementResponse
    duration_sec: float
    model_name: str
    full_model_id: str
    vendor: str
    mode: str
    is_final: bool
    archived_path: str = ""
    archived_filename: str = ""
    validation: ValidationResult | None = None
    error: str = ""


def append_audit_entry(root: str | Path, entry: dict[str, Any]) -> None:
    """将每轮需求澄清的外部输入、模型原始输出、完整模型 ID 与调用耗时追加写入 workspace/requirements/audit.jsonl。"""
    audit_dir = Path(root) / "workspace" / "requirements"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_file = audit_dir / "audit.jsonl"
    with open(audit_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_audit_log(root: str | Path, limit: int = 30) -> list[dict[str, Any]]:
    """读取 workspace/requirements/ 下的原始交互与耗时审计记录（兼容旧文件名 web_audit.jsonl）。"""
    req_ws = Path(root) / "workspace" / "requirements"
    rows: list[dict[str, Any]] = []
    for fname in ("web_audit.jsonl", "audit.jsonl"):
        fpath = req_ws / fname
        if not fpath.is_file():
            continue
        for line in fpath.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    return rows[-limit:]


def execute_clarification_turn(
    store: ReqSessionStore,
    chat_id: str,
    user_text: str,
    timeout: int = 600,
    agent_override: str | None = None,
    mode_override: str | None = None,
    channel: str = "feishu",
) -> ClarificationTurnOutcome:
    """统一执行一轮需求澄清对话（供 feishu_daemon.py 与 web/api.py 共同调用）：
    1. 同步可选的 agent / mode 变更；
    2. 标准化用户输入并探测目标项目模块、近期 Git 提交与历史需求上下文；
    3. 调用底层只读大模型（支持 cli_session / cli_stateless）；
    4. 更新会话 session_id 与问答 history；
    5. 若为定稿指令，自动运行 validate_requirement_spec 并落盘 docs/requirements/REQ-{ts}.md；
    6. 记录本轮调用的开始/结束时间、耗时与原始输入输出审计。
    """
    if agent_override:
        spec = resolve_model_spec(agent_override)
        store.set_agent(chat_id, spec.name)
    if mode_override:
        store.set_mode(chat_id, mode_override)

    sess = store.get(chat_id)
    cwd = sess["cwd"]
    clean_text = user_text.strip()
    current_session_id = sess.get("session_id") or None
    current_mode = sess.get("mode", "cli_session")
    current_history = sess.get("history") or []
    is_new = (current_session_id is None) and (len(current_history) == 0)
    is_final = is_finalize_request(clean_text)

    normalized_input = normalize_user_input(clean_text)
    project_context = build_project_context_summary(cwd)
    agent_prompt = build_req_prompt(
        normalized_input,
        is_new=is_new,
        project_context_summary=project_context,
    )

    started_iso = now_iso()
    t0 = time.monotonic()
    result = run_agent_turn(
        sess["agent"],
        agent_prompt,
        cwd,
        session_id=current_session_id,
        timeout=timeout,
        mode=current_mode,
        history=current_history,
    )
    duration_s = round(time.monotonic() - t0, 2)
    ended_iso = now_iso()

    if not result.ok:
        err_msg = result.parsed.error or "未知调用错误"
        append_audit_entry(
            cwd,
            {
                "channel": channel,
                "chat_id": chat_id,
                "turn": len(current_history) + 1,
                "started_at": started_iso,
                "ended_at": ended_iso,
                "duration_sec": duration_s,
                "ok": False,
                "agent": result.model_name,
                "full_model_id": result.full_model_id,
                "vendor": result.vendor,
                "mode": result.mode,
                "user_input": clean_text,
                "raw_output": "",
                "error": err_msg,
            },
        )
        return ClarificationTurnOutcome(
            ok=False,
            chat_id=chat_id,
            reply_text=f"⚠️ 需求分析中断：{err_msg}",
            semantic=extract_semantic_response(f"⚠️ 需求分析中断：{err_msg}", is_finalize=False),
            duration_sec=duration_s,
            model_name=result.model_name,
            full_model_id=result.full_model_id,
            vendor=result.vendor,
            mode=result.mode,
            is_final=is_final,
            error=err_msg,
        )

    new_session_id = result.parsed.session_id
    if new_session_id and new_session_id != current_session_id and current_mode == "cli_session":
        store.update_session_id(chat_id, new_session_id)

    reply_text = result.parsed.reply.strip() or "（已完成分析，但未捕获到文本回复）"
    store.append_history(chat_id, clean_text, reply_text)

    archived_path = ""
    archived_filename = ""
    v_res: ValidationResult | None = None
    if is_final and len(reply_text) > 100:
        try:
            v_res = validate_requirement_spec(reply_text)
            req_dir = os.path.join(cwd, "docs", "requirements")
            os.makedirs(req_dir, exist_ok=True)
            ts = time.strftime("%Y%m%d-%H%M%S")
            archived_filename = f"REQ-{ts}.md"
            archived_path = os.path.join(req_dir, archived_filename)
            suffix = (
                "\n<!-- SPEC-VALIDATED: PASS -->\n"
                if v_res.is_valid
                else f"\n<!-- SPEC-VALIDATED: FAIL - {'; '.join(v_res.errors)} -->\n"
            )
            atomic_write(archived_path, reply_text + "\n" + suffix)
            store.set_last_archived_req(chat_id, archived_path)
            log.info("需求定稿文件已落盘: %s (valid=%s)", archived_path, v_res.is_valid)
        except Exception as e:
            log.warning("定稿文件写入失败: %s", e)

    append_audit_entry(
        cwd,
        {
            "channel": channel,
            "chat_id": chat_id,
            "turn": len(current_history) + 1,
            "started_at": started_iso,
            "ended_at": ended_iso,
            "duration_sec": duration_s,
            "ok": True,
            "agent": result.model_name,
            "full_model_id": result.full_model_id,
            "vendor": result.vendor,
            "mode": result.mode,
            "user_input": clean_text,
            "raw_output": reply_text,
            "archived_file": archived_filename,
        },
    )

    semantic = extract_semantic_response(reply_text, is_finalize=is_final)
    return ClarificationTurnOutcome(
        ok=True,
        chat_id=chat_id,
        reply_text=reply_text,
        semantic=semantic,
        duration_sec=duration_s,
        model_name=result.model_name,
        full_model_id=result.full_model_id,
        vendor=result.vendor,
        mode=result.mode,
        is_final=is_final,
        archived_path=archived_path,
        archived_filename=archived_filename,
        validation=v_res,
    )
