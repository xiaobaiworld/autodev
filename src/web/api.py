# 定位: api.py AutoDev 统一网页客户端的数据读取与受控写入核心逻辑（单一文件事实源，含密钥脱敏与 D008 校验）。
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from cockpit.agents import parse_agents, parse_limits, parse_roles
from cockpit.controller import Controller
from cockpit.kinds import DEFAULT_KIND
from cockpit.pipeline import SetupError, check_vendors, template_for
from cockpit.store import Run, atomic_write, now_iso
from requirements.agent_runner import run_agent_turn
from requirements.context_detector import build_project_context_summary
from requirements.flow import build_req_prompt, is_finalize_request, normalize_user_input
from requirements.handoff import extract_srs_metadata, handoff_srs_to_pipeline
from requirements.llm_provider import load_model_registry, resolve_model_spec
from requirements.presentation import extract_semantic_response
from requirements.session import ReqSessionStore
from requirements.validator import REQUIRED_SECTIONS, validate_requirement_spec

AUTODEV_ROOT = Path(__file__).resolve().parents[2]
WEB_CHAT_ID = "web_workbench_default"

SECRET_PATTERNS = [
    re.compile(r"(app_secret\s*=\s*['\"])([^'\"]+)(['\"])", re.I),
    re.compile(r"(sk-[a-zA-Z0-9]{16,})"),
    re.compile(r"(cli_[a-zA-Z0-9]{12,})"),
]


def redact_secrets(text: str) -> str:
    """展示产物前做密钥脱敏扫描（设计 9.4）。"""
    out = text
    out = SECRET_PATTERNS[0].sub(r"\1***REDACTED***\3", out)
    out = SECRET_PATTERNS[1].sub("sk-***REDACTED***", out)
    return out


def evaluate_srs_rules_detail(content: str) -> dict[str, Any]:
    """对 SRS 文本执行 validate_requirement_spec 并返回 9 大章节与 RULE-01~09 的逐项红绿灯状态。"""
    clean_text = re.sub(r"\n*<!--\s*SPEC-VALIDATED:.*?-->\s*\Z", "", content or "", flags=re.DOTALL).strip()
    v_res = validate_requirement_spec(clean_text)

    section_labels = [
        ("1", "## 1. 需求标识与元数据", ["## 1. 需求标识与元数据"]),
        ("2", "## 2. 需求规模分类与需求关联网络", ["## 2. 需求规模分类与需求关联网络", "## 2. 架构拓扑与近期关联"]),
        ("3", "## 3. 核心背景与业务目标 (Why & What)", ["## 3. 核心背景与业务目标 (Why & What)"]),
        ("4", "## 4. 业务用例与核心流程 (Scope)", ["## 4. 业务用例与核心流程 (Scope)"]),
        ("5", "## 5. 明确非目标与边界 (Non-goals)", ["## 5. 明确非目标与边界 (Non-goals)"]),
        ("6", "## 6. 外部界面原型草图 (UI Wireframe)", ["## 6. 外部界面原型草图 (UI Wireframe)"]),
        ("7", "## 7. 业务约束与前置依赖", ["## 7. 业务约束与前置依赖"]),
        ("8", "## 8. 可量化验收标准清单 (Acceptance Criteria)", ["## 8. 可量化验收标准清单 (Acceptance Criteria)"]),
        ("9", "## 9. 下游架构设计关注点", ["## 9. 下游架构设计关注点"]),
    ]

    sections_status = []
    for num, title, matches in section_labels:
        present = any(m in clean_text for m in matches)
        body = ""
        if present:
            m = re.search(rf"^##\s+{num}\.\s+[^\n]+\n(.*?)(?=^##\s+\d+\.|\Z)", clean_text, flags=re.M | re.S)
            body = m.group(1).strip() if m else ""
        sections_status.append({
            "num": int(num),
            "title": title,
            "present": present and len(body) > 5,
            "preview": body[:300],
        })

    rule_defs = [
        ("RULE-01", "UTF-8 编码与 REQ-*.md 命名规范"),
        ("RULE-02", "九大标准章节标题完整性"),
        ("RULE-03", "需求规模类别、模块归属与关系矩阵"),
        ("RULE-04", "核心业务背景与业务目标双要素"),
        ("RULE-05", "明确非目标与防膨胀边界声明"),
        ("RULE-06", "外部界面等宽线框图 (```text)"),
        ("RULE-07", "可量化验收标准场景清单"),
        ("RULE-08", "严禁越权编写 SQL 或实现代码"),
        ("RULE-09", "文档有效篇幅区间 (≥ 300 字符)"),
    ]
    rules_status = []
    for code, desc in rule_defs:
        failed_msgs = [e for e in v_res.errors if f"[{code}]" in e]
        rules_status.append({
            "code": code,
            "description": desc,
            "passed": len(failed_msgs) == 0 and bool(clean_text),
            "errors": failed_msgs,
        })

    # 提取规模、模块归属与关联关系用于前端可视化图谱
    scale_match = re.search(r"\b(Epic|Feature|Sub-feature|Enhancement)\b", clean_text)
    if not scale_match:
        scale_match = re.search(r"(史诗级大需求|标准功能|子功能|改动增强)", clean_text)
    scale = scale_match.group(1) if scale_match else "未标定"

    relations = []
    for rel_type in ("Parent", "Extends", "Connects-to", "Depends-on", "Relates-to", "Blocks", "Supersedes"):
        for m in re.finditer(rf"`?{rel_type}[^`\n]*`?[：:]\s*([^\n]+)", clean_text):
            relations.append({"type": rel_type, "target": m.group(1).strip()})

    wireframe = ""
    wf_match = re.search(r"## 6\.\s+外部界面原型草图.*?```text\n(.*?)```", clean_text, flags=re.S)
    if wf_match:
        wireframe = wf_match.group(1).rstrip()

    meta = extract_srs_metadata(clean_text) if clean_text else {
        "title": "未命名需求",
        "summary": "",
        "scope": "",
        "acceptance_criteria": [],
    }

    return {
        "is_valid": v_res.is_valid,
        "errors": v_res.errors,
        "warnings": v_res.warnings,
        "sections": sections_status,
        "sections_ready_count": sum(1 for s in sections_status if s["present"]),
        "rules": rules_status,
        "scale": scale,
        "relations": relations,
        "wireframe": wireframe,
        "metadata": meta,
    }


def list_srs_documents(root: str | Path) -> list[dict[str, Any]]:
    root_path = Path(root)
    req_dir = root_path / "docs" / "requirements"
    if not req_dir.is_dir():
        return []
    items = []
    for p in sorted(req_dir.glob("REQ-*.md"), reverse=True):
        try:
            text = p.read_text(encoding="utf-8")
            detail = evaluate_srs_rules_detail(text)
            items.append({
                "filename": p.name,
                "path": str(p),
                "title": detail["metadata"]["title"],
                "scale": detail["scale"],
                "is_valid": detail["is_valid"],
                "sections_ready": detail["sections_ready_count"],
                "updated_at": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "relations_count": len(detail["relations"]),
            })
        except Exception:
            continue
    return items


def load_audit_log(root: str | Path, limit: int = 30) -> list[dict[str, Any]]:
    """读取 workspace/requirements/web_audit.jsonl 中的原始问答与每轮调用耗时记录（对应 requirements.md 第 7 节）。"""
    audit_file = Path(root) / "workspace" / "requirements" / "web_audit.jsonl"
    if not audit_file.is_file():
        return []
    rows = []
    for line in audit_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows[-limit:]


def append_audit_entry(root: str | Path, entry: dict[str, Any]) -> None:
    audit_dir = Path(root) / "workspace" / "requirements"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_file = audit_dir / "web_audit.jsonl"
    with open(audit_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def list_pipeline_runs(root: str | Path) -> list[dict[str, Any]]:
    """读取 workspace/runs/ 下的所有流水线运行状态，待人工决定的置顶（设计 9.3）。"""
    root_path = Path(root)
    runs_dir = root_path / "workspace" / "runs"
    if not runs_dir.is_dir():
        return []
    out = []
    for rd in sorted(runs_dir.glob("R*"), reverse=True):
        state_file = rd / "state.json"
        if not state_file.is_file():
            continue
        try:
            st = json.loads(state_file.read_text(encoding="utf-8"))
            rid = st.get("id", rd.name)
            req_file = root_path / "workspace" / "requests" / "active" / f"{rid}.md"
            title = rid
            if req_file.is_file():
                req_txt = req_file.read_text(encoding="utf-8", errors="replace")
                m = re.search(r"^#\s+(.+?)\s*$", req_txt, flags=re.M)
                if m:
                    title = m.group(1).strip()
            step = st.get("step") or {}
            human = st.get("human") or {}
            out.append({
                "id": rid,
                "title": title,
                "project": st.get("project", "toy"),
                "kind": st.get("kind") or DEFAULT_KIND,
                "status": st.get("status", "unknown"),
                "stage": st.get("stage", "S1"),
                "round": st.get("round", 1),
                "step_state": step.get("state", ""),
                "agent": step.get("agent", ""),
                "model": step.get("model", ""),
                "waiting_human": bool(human.get("waiting")) or st.get("status") == "needs-human",
                "pending_decision": human.get("pending_decision"),
            })
        except Exception:
            continue
    # 置顶待你决定的需求，其次 active，最后其他
    priority = {"needs-human": 0, "active": 1, "done": 2, "rejected": 3}
    out.sort(key=lambda r: (0 if r["waiting_human"] else priority.get(r["status"], 9), r["id"]))
    return out


def get_run_detail(root: str | Path, run_id: str) -> dict[str, Any]:
    """读取单个需求的完整 S1~S9 状态、事件流、各阶段产物原文及需求变更轨迹（设计 9.2）。"""
    root_path = Path(root)
    run_dir = root_path / "workspace" / "runs" / run_id
    if not (run_dir / "state.json").is_file():
        raise FileNotFoundError(f"找不到运行记录: {run_id}")

    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    kind = state.get("kind") or DEFAULT_KIND
    tpl = template_for(state)
    order = tpl["order"]
    stages_spec = tpl["stages"]

    events = []
    ev_file = run_dir / "events.jsonl"
    if ev_file.is_file():
        for line in ev_file.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    events.append(json.loads(line))
                except Exception:
                    pass

    req_file = root_path / "workspace" / "requests" / "active" / f"{run_id}.md"
    request_text = redact_secrets(req_file.read_text(encoding="utf-8", errors="replace")) if req_file.is_file() else ""

    curr_stage = state.get("stage", "S1")
    curr_idx = order.index(curr_stage) if curr_stage in order else 0

    stages_detail = []
    for idx, stg in enumerate(order):
        spec = stages_spec[stg]
        stg_dir = run_dir / spec["dir"]
        rounds_data = []
        if stg_dir.is_dir():
            for rdir in sorted(stg_dir.glob("round-*")):
                artifacts = {}
                for fname in ("analysis.md", "design.md", "dev-plan.md", "review.md", "response.md",
                              "check.log", "usage.log", "acceptance.md", "done.json", "record-a1.json"):
                    fpath = rdir / fname
                    if fpath.is_file():
                        artifacts[fname] = redact_secrets(fpath.read_text(encoding="utf-8", errors="replace")[:15000])
                done_obj = {}
                if (rdir / "done.json").is_file():
                    try:
                        done_obj = json.loads((rdir / "done.json").read_text(encoding="utf-8"))
                    except Exception:
                        pass
                rounds_data.append({
                    "round": rdir.name,
                    "done": done_obj,
                    "artifacts": artifacts,
                })

        if state.get("status") == "done" or idx < curr_idx or (rounds_data and rounds_data[-1]["done"].get("verdict") in ("ACCEPT", "DONE", "PASS")):
            ui_status = "complete"
        elif stg == curr_stage:
            ui_status = "paused" if state.get("status") == "needs-human" else "running"
        else:
            ui_status = "pending"

        stages_detail.append({
            "code": stg,
            "dir": spec["dir"],
            "role": spec.get("role", ""),
            "runner": spec.get("runner", "agent"),
            "task": spec.get("task", ""),
            "outputs": spec.get("outputs", []),
            "verdicts": spec.get("verdicts", []),
            "gate": spec.get("gate"),
            "ui_status": ui_status,
            "rounds": rounds_data,
        })

    human_replies = []
    hdir = run_dir / "human"
    if hdir.is_dir():
        for rp in sorted(hdir.glob("reply-*.md")):
            human_replies.append({
                "name": rp.name,
                "content": redact_secrets(rp.read_text(encoding="utf-8", errors="replace")),
            })

    return {
        "state": state,
        "order": order,
        "request_text": request_text,
        "stages": stages_detail,
        "events": events[-40:],
        "human_replies": human_replies,
    }


def get_config_view(root: str | Path) -> dict[str, Any]:
    """读取 config.yaml 角色与完整模型 ID 配置，附上文件哈希用于乐观锁保存（设计 9.1、9.3）。"""
    cfg_path = Path(root) / "config.yaml"
    if not cfg_path.is_file():
        cfg_path = AUTODEV_ROOT / "config.yaml"
    raw = cfg_path.read_text(encoding="utf-8")
    version_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    agents = parse_agents(raw)
    roles = parse_roles(raw)
    limits = parse_limits(raw)
    return {
        "version_hash": version_hash,
        "agents": agents,
        "roles": roles,
        "limits": limits,
    }


def update_roles_config(root: str | Path, new_roles: dict[str, str], expected_hash: str) -> dict[str, Any]:
    """更新 config.yaml 中的角色绑定，强制执行版本哈希比对与 D008 异构厂商检查。"""
    cfg_path = Path(root) / "config.yaml"
    if not cfg_path.is_file():
        cfg_path = AUTODEV_ROOT / "config.yaml"
    raw = cfg_path.read_text(encoding="utf-8")
    curr_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    if expected_hash and curr_hash != expected_hash:
        raise ValueError("配置文件已被其他进程修改，请刷新页面后再保存（乐观锁拦截）")

    agents = parse_agents(raw)
    merged_roles = parse_roles(raw)
    for role_name, agent_name in new_roles.items():
        if agent_name not in agents:
            raise ValueError(f"角色 {role_name} 绑定的 Agent {agent_name!r} 不在 config.yaml 的 agents 段中")
        merged_roles[role_name] = agent_name

    # D008 异构厂商校验
    check_vendors(agents, merged_roles)

    updated = raw
    for role_name, agent_name in merged_roles.items():
        updated = re.sub(
            rf"^(\s+{re.escape(role_name)}:\s*\{{\s*agent:\s*)\S+?(\s*\}}\s*)$",
            rf"\g<1>{agent_name}\2",
            updated,
            flags=re.M,
        )
    atomic_write(cfg_path, updated)
    return get_config_view(root)


def submit_human_decision(
    root: str | Path,
    run_id: str,
    action: str,
    note: str = "",
    stage: str | None = None,
) -> dict[str, Any]:
    """在网页端对 needs-human 的需求提交人工决策（复用 Controller.resume，写入 human/reply-K.md）。"""
    root_path = Path(root)
    cfg_view = get_config_view(root_path)
    ctrl = Controller(
        root_path,
        cfg_view["agents"],
        cfg_view["roles"],
        cfg_view["limits"],
        invoke_fn=lambda *a, **kw: {"ok": False, "reason": "web_resume_only"},
    )
    run_dir = root_path / "workspace" / "runs" / run_id
    msg = ctrl.resume(run_dir, action=action, note=note, stage=stage or None)
    return {"ok": True, "message": msg, "run": get_run_detail(root_path, run_id)}


def run_web_req_turn(
    root: str | Path,
    user_text: str,
    agent_name: str | None = None,
    mode: str | None = None,
    session_file: str | Path | None = None,
) -> dict[str, Any]:
    """在网页端执行一轮需求澄清对话（与飞书共享 ReqSessionStore 结构，并记录原始输入输出与耗时审计）。"""
    root_path = Path(root)
    sfile = str(session_file or (root_path / ".req_session.json"))
    store = ReqSessionStore(sfile, str(root_path), "claude-sonnet")

    if agent_name:
        spec = resolve_model_spec(agent_name)
        store.set_agent(WEB_CHAT_ID, spec.name)
    if mode:
        store.set_mode(WEB_CHAT_ID, mode)

    sess = store.get(WEB_CHAT_ID)
    clean_text = user_text.strip()
    if clean_text in ("/new", "新需求", "/reset"):
        store.reset_session(WEB_CHAT_ID)
        return {
            "ok": True,
            "reply": "🌱 已开启全新的需求澄清会话！请直接输入你的想法，我会结合当前项目模块与近期变更帮你梳理。",
            "choices": [],
            "session": store.get(WEB_CHAT_ID),
        }

    current_session_id = sess.get("session_id") or None
    current_mode = sess.get("mode", "cli_session")
    current_history = sess.get("history") or []
    is_new = (current_session_id is None) and (len(current_history) == 0)
    is_final = is_finalize_request(clean_text)

    normalized_input = normalize_user_input(clean_text)
    project_context = build_project_context_summary(sess["cwd"])
    prompt = build_req_prompt(normalized_input, is_new=is_new, project_context_summary=project_context)

    started_iso = now_iso()
    t0 = time.monotonic()
    result = run_agent_turn(
        sess["agent"],
        prompt,
        sess["cwd"],
        session_id=current_session_id,
        timeout=300,
        mode=current_mode,
        history=current_history,
    )
    duration_s = round(time.monotonic() - t0, 2)
    ended_iso = now_iso()

    reply_text = result.parsed.reply.strip() if result.ok else f"⚠️ 调用异常: {result.parsed.error}"
    if result.ok:
        if result.parsed.session_id and current_mode == "cli_session":
            store.update_session_id(WEB_CHAT_ID, result.parsed.session_id)
        store.append_history(WEB_CHAT_ID, clean_text, reply_text)

    archived_filename = ""
    if result.ok and is_final and len(reply_text) > 100:
        v_res = validate_requirement_spec(reply_text)
        req_dir = root_path / "docs" / "requirements"
        req_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d-%H%M%S")
        archived_filename = f"REQ-{ts}.md"
        full_path = req_dir / archived_filename
        suffix = "\n<!-- SPEC-VALIDATED: PASS -->\n" if v_res.is_valid else f"\n<!-- SPEC-VALIDATED: FAIL - {'; '.join(v_res.errors)} -->\n"
        atomic_write(full_path, reply_text + "\n" + suffix)
        store.set_last_archived_req(WEB_CHAT_ID, str(full_path))

    append_audit_entry(
        root_path,
        {
            "turn": len(current_history) + 1,
            "started_at": started_iso,
            "ended_at": ended_iso,
            "duration_sec": duration_s,
            "ok": result.ok,
            "agent": result.model_name,
            "full_model_id": result.full_model_id,
            "vendor": result.vendor,
            "mode": result.mode,
            "user_input": clean_text,
            "raw_output": reply_text,
            "archived_file": archived_filename,
        },
    )

    sem = extract_semantic_response(reply_text, is_finalize=is_final)
    return {
        "ok": result.ok,
        "reply": reply_text,
        "summary": sem.summary_markdown,
        "choices": [{"index": c.index, "label": c.label, "description": c.description} for c in sem.choices],
        "duration_sec": duration_s,
        "full_model_id": result.full_model_id,
        "archived_filename": archived_filename,
        "session": store.get(WEB_CHAT_ID),
    }
