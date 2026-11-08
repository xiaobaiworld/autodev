# 定位: service.py 飞书端与 Web 客户端共享的需求澄清单轮编排、Agent自动/人工双轨需求分类、定稿校验归档与原始交互耗时审计服务（O1 收敛）。
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
from requirements.flow import (
    build_req_prompt,
    classify_requirement_type,
    detect_manual_type_override,
    extract_agent_classified_type,
    is_finalize_request,
    normalize_req_type,
    normalize_user_input,
)
from requirements.llm_provider import resolve_model_spec
from requirements.presentation import RequirementResponse, extract_semantic_response
from requirements.session import ReqSessionStore
from requirements.validator import (
    ValidationResult,
    extract_req_id,
    extract_req_type,
    validate_requirement_spec,
)

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
    req_type: str
    req_type_source: str
    req_type_reason: str
    is_final: bool
    archived_path: str = ""
    archived_filename: str = ""
    validation: ValidationResult | None = None
    error: str = ""


def append_audit_entry(root: str | Path, entry: dict[str, Any]) -> None:
    """将每轮需求澄清的外部输入、模型原始输出、完整模型 ID、需求分类与调用耗时追加写入 workspace/requirements/audit.jsonl。"""
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
    req_type_override: str | None = None,
    channel: str = "feishu",
) -> ClarificationTurnOutcome:
    """统一执行一轮需求澄清对话（供 feishu_daemon.py 与 web/api.py 共同调用）：
    1. 同步可选的 agent / mode / req_type 变更；
    2. 支持双轨分类：
       - 若人工通过参数或自然语言显式指定类型（SOFTWARE/DEPLOYMENT/HYBRID），锁定为 manual；
       - 若处于 auto 模式，先由程序结合项目代码模块与部署目录预判，再交由 Agent 在回复中自动寻找并确认分类；
    3. 调用底层只读大模型（支持 cli_session / cli_stateless）；
    4. 从 Agent 回复中提取自动分类结果并回写 ReqSessionStore；
    5. 若为定稿指令，按需求类型自动命名（REQ-DEPLOY-*.md / REQ-HYBRID-*.md / REQ-*.md）并运行 validate_requirement_spec；
    6. 记录本轮调用的开始/结束时间、耗时、需求类型与原始输入输出审计。
    """
    if agent_override:
        spec = resolve_model_spec(agent_override)
        store.set_agent(chat_id, spec.name)
    if mode_override:
        store.set_mode(chat_id, mode_override)

    clean_text = user_text.strip()

    # 检查是否有显式传入的 req_type_override 或对话内的自然语言切换指令
    if req_type_override:
        norm_override = normalize_req_type(req_type_override)
        if norm_override == "AUTO":
            store.set_req_type(chat_id, "AUTO", source="auto", reason="🤖 已设为 Agent 自动寻找与分类模式")
        else:
            store.set_req_type(chat_id, norm_override, source="manual", reason=f"👤 人工指定为 {norm_override}")
    else:
        nl_override = detect_manual_type_override(clean_text)
        if nl_override:
            if nl_override == "AUTO":
                store.set_req_type(chat_id, "AUTO", source="auto", reason="🤖 对话指令恢复 Agent 自动寻找与分类")
            else:
                store.set_req_type(
                    chat_id,
                    nl_override,
                    source="manual",
                    reason=f"👤 对话指令显式指定为 {nl_override}",
                )

    sess = store.get(chat_id)
    cwd = sess["cwd"]
    current_session_id = sess.get("session_id") or None
    current_mode = sess.get("mode", "cli_session")
    current_history = sess.get("history") or []
    is_new = (current_session_id is None) and (len(current_history) == 0)
    is_final = is_finalize_request(clean_text)

    normalized_input = normalize_user_input(clean_text)
    project_context = build_project_context_summary(cwd)
    inferred_type, inferred_reason = classify_requirement_type(
        clean_text,
        history=current_history,
        project_context=project_context,
    )

    sess_req_type = sess.get("req_type", "AUTO")
    sess_req_source = sess.get("req_type_source", "auto")

    agent_prompt = build_req_prompt(
        normalized_input,
        is_new=is_new,
        project_context_summary=project_context,
        req_type=sess_req_type,
        req_type_source=sess_req_source,
        inferred_type=inferred_type,
        inferred_reason=inferred_reason,
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
        eff_type = sess_req_type if sess_req_type != "AUTO" else inferred_type
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
                "req_type": eff_type,
                "req_type_source": sess_req_source,
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
            req_type=eff_type,
            req_type_source=sess_req_source,
            req_type_reason=sess.get("req_type_reason", ""),
            is_final=is_final,
            error=err_msg,
        )

    new_session_id = result.parsed.session_id
    if new_session_id and new_session_id != current_session_id and current_mode == "cli_session":
        store.update_session_id(chat_id, new_session_id)

    reply_text = result.parsed.reply.strip() or "（已完成分析，但未捕获到文本回复）"
    store.append_history(chat_id, clean_text, reply_text)

    # 双轨分类：若当前处于 auto 模式，优先采纳 Agent 在回复中结合代码与部署目录给出的分类结论
    if sess_req_source != "manual":
        agent_detected = extract_agent_classified_type(reply_text)
        if agent_detected in ("SOFTWARE", "DEPLOYMENT", "HARDWARE", "HYBRID"):
            store.set_req_type(
                chat_id,
                agent_detected,
                source="auto",
                reason=f"🤖 Agent 结合项目资产与对话自动判定为 {agent_detected}",
            )
        elif sess_req_type == "AUTO" or inferred_type != "SOFTWARE":
            store.set_req_type(
                chat_id,
                inferred_type,
                source="auto",
                reason=f"🤖 自动预判：{inferred_reason}",
            )

    updated_sess = store.get(chat_id)
    final_req_type = updated_sess.get("req_type", "SOFTWARE")
    if final_req_type == "AUTO":
        final_req_type = inferred_type
    final_req_source = updated_sess.get("req_type_source", "auto")
    final_req_reason = updated_sess.get("req_type_reason", "")

    archived_path = ""
    archived_filename = ""
    v_res: ValidationResult | None = None
    if is_final and len(reply_text) > 100:
        try:
            v_res = validate_requirement_spec(reply_text)
            doc_type = extract_req_type(reply_text) if reply_text else final_req_type
            if doc_type in ("SOFTWARE", "DEPLOYMENT", "HARDWARE", "HYBRID") and final_req_source != "manual":
                final_req_type = doc_type
                store.set_req_type(
                    chat_id,
                    doc_type,
                    source="auto",
                    reason=f"🤖 定稿文档确认为 {doc_type}",
                )
            req_dir = os.path.join(cwd, "docs", "requirements")
            os.makedirs(req_dir, exist_ok=True)
            ts = time.strftime("%Y%m%d-%H%M%S")
            if final_req_type == "DEPLOYMENT":
                archived_filename = f"REQ-DEPLOY-{ts}.md"
            elif final_req_type == "HARDWARE":
                archived_filename = f"REQ-HW-{ts}.md"
            elif final_req_type == "HYBRID":
                archived_filename = f"REQ-HYBRID-{ts}.md"
            else:
                archived_filename = f"REQ-{ts}.md"
            archived_path = os.path.join(req_dir, archived_filename)
            suffix = (
                "\n<!-- SPEC-VALIDATED: PASS -->\n"
                if v_res.is_valid
                else f"\n<!-- SPEC-VALIDATED: FAIL - {'; '.join(v_res.errors)} -->\n"
            )
            atomic_write(archived_path, reply_text + "\n" + suffix)
            store.set_last_archived_req(chat_id, archived_path)
            detected_req_id = extract_req_id(reply_text) or os.path.splitext(archived_filename)[0]
            store.set_active_req_id(chat_id, detected_req_id)
            log.info(
                "需求定稿文件已落盘: %s (id=%s, type=%s, valid=%s)",
                archived_path,
                detected_req_id,
                final_req_type,
                v_res.is_valid,
            )
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
            "req_type": final_req_type,
            "req_type_source": final_req_source,
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
        req_type=final_req_type,
        req_type_source=final_req_source,
        req_type_reason=final_req_reason,
        is_final=is_final,
        archived_path=archived_path,
        archived_filename=archived_filename,
        validation=v_res,
    )
