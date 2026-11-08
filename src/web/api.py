# 定位: api.py AutoDev 统一网页客户端的数据读取与受控写入核心逻辑（单一文件事实源，含 O1~O4 与 C2/C3 优化收敛）。
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from cockpit.agents import parse_agents, parse_limits, parse_roles, validate_role
from cockpit.controller import Controller
from cockpit.kinds import DEFAULT_KIND
from cockpit.pipeline import SetupError, check_vendors, template_for, wait_reason
from cockpit.store import Run, acquire_lock, atomic_write
from driver.setup import USE as AUTOLOOP_SUPPORTED_CLIS
from requirements.flow import build_srs_template, normalize_req_type
from requirements.service import (
    append_audit_entry,
    execute_clarification_turn,
    load_audit_log,
)
from requirements.session import ReqSessionStore
from requirements.validator import inspect_srs_document

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
    """统一委托给 requirements.validator.inspect_srs_document（O2 收敛）。"""
    return inspect_srs_document(content)


def list_srs_documents(root: str | Path) -> list[dict[str, Any]]:
    root_path = Path(root)
    req_dir = root_path / "docs" / "requirements"
    if not req_dir.is_dir():
        return []
    items = []
    for p in sorted(req_dir.glob("REQ-*.md"), reverse=True):
        try:
            text = p.read_text(encoding="utf-8")
            detail = inspect_srs_document(text)
            items.append({
                "filename": p.name,
                "path": str(p),
                "title": detail["metadata"]["title"],
                "req_type": detail["req_type"],
                "deliverables": detail["deliverables"],
                "scale": detail["scale"],
                "is_valid": detail["is_valid"],
                "sections_ready": detail["sections_ready_count"],
                "updated_at": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "relations_count": len(detail["relations"]),
            })
        except Exception:
            continue
    return items


def generate_srs_template(root: str | Path, req_type: str = "SOFTWARE") -> dict[str, Any]:
    """根据指定的需求类型（SOFTWARE / DEPLOYMENT / HYBRID）生成标准 9 章节模板与实时校验结果。"""
    norm_type = normalize_req_type(req_type)
    if norm_type == "AUTO":
        norm_type = "SOFTWARE"
    ts = datetime.now().strftime("%Y%m%d")
    if norm_type == "DEPLOYMENT":
        fname = f"REQ-DEPLOY-SERVICE_DAEMON-{ts}.md"
    elif norm_type == "HARDWARE":
        fname = f"REQ-HW-DEVICE_INTEGRATION-{ts}.md"
    elif norm_type == "HYBRID":
        fname = f"REQ-HYBRID-FEATURE_AND_DEPLOY-{ts}.md"
    else:
        fname = f"REQ-SOFT-FEATURE-{ts}.md"
    content = build_srs_template(req_type=norm_type, req_id=fname[:-3], project=str(Path(root).resolve()))
    return {
        "ok": True,
        "filename": fname,
        "req_type": norm_type,
        "content": content,
        "validation": inspect_srs_document(content),
    }


def list_pipeline_runs(root: str | Path) -> list[dict[str, Any]]:
    """读取 workspace/runs/ 下的所有流水线运行状态，待人工决定的置顶并共享 wait_reason（O4）。"""
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
            is_waiting = bool(human.get("waiting")) or st.get("status") == "needs-human"
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
                "waiting_human": is_waiting,
                "pending_decision": human.get("pending_decision"),
                "wait_reason": wait_reason(st) if is_waiting else "",
            })
        except Exception:
            continue
    priority = {"needs-human": 0, "active": 1, "done": 2, "rejected": 3}
    out.sort(key=lambda r: (0 if r["waiting_human"] else priority.get(r["status"], 9), r["id"]))
    return out


def get_run_detail(root: str | Path, run_id: str) -> dict[str, Any]:
    """读取单个需求的完整 S1~S9 状态、事件流、各阶段产物原文及等待原因（设计 9.2，O4）。"""
    root_path = Path(root)
    run_dir = root_path / "workspace" / "runs" / run_id
    if not (run_dir / "state.json").is_file():
        raise FileNotFoundError(f"找不到运行记录: {run_id}")

    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
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
        "wait_reason": wait_reason(state) if state.get("status") == "needs-human" else "",
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
        "autoloop_supported_clis": sorted(AUTOLOOP_SUPPORTED_CLIS.keys()),
    }


def update_roles_config(root: str | Path, new_roles: dict[str, str], expected_hash: str) -> dict[str, Any]:
    """更新 config.yaml 中的角色绑定，强制执行版本哈希比对、autoloop CLI 兼容性检查（C2）与 D008 异构厂商检查。"""
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
        if role_name not in merged_roles:
            raise ValueError('只能修改已登记角色')
        if agent_name not in agents:
            raise ValueError(f"角色 {role_name} 绑定的 Agent {agent_name!r} 不在 config.yaml 的 agents 段中")
        cli_name = agents[agent_name].get("cli", "")
        if cli_name not in AUTOLOOP_SUPPORTED_CLIS:
            raise SetupError(
                f"角色 {role_name} 不能绑定 {agent_name!r}（CLI={cli_name!r}）：当前 autoloop 流水线规则仅支持 {sorted(AUTOLOOP_SUPPORTED_CLIS)}，{agent_name} 仅可用于需求澄清阶段（D015）"
            )
        merged_roles[role_name] = agent_name

    # D008 异构厂商校验
    check_vendors(agents, merged_roles)
    for role_name, agent_name in new_roles.items():
        validate_role(agents, role_name, agent_name)

    updated = raw
    if 'agent_registry:' in raw and not re.search(r'^roles:', raw, re.M):
        updated += '\nroles:\n' + ''.join(f'  {role}: {{ agent: {name} }}\n' for role, name in merged_roles.items())
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
    """在网页端对 needs-human 的需求提交人工决策（复用 Controller.resume 并加 workspace/.lock 单实例锁，C3）。"""
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
    lock = acquire_lock(root_path / "workspace" / ".lock")
    try:
        msg = ctrl.resume(run_dir, action=action, note=note, stage=stage or None)
    finally:
        lock.close()
    return {"ok": True, "message": msg, "run": get_run_detail(root_path, run_id)}


def set_web_req_type(
    root: str | Path,
    req_type: str,
    session_file: str | Path | None = None,
    chat_id: str | None = None,
) -> dict[str, Any]:
    """在网页端切换当前会话的需求类型模式（AUTO / SOFTWARE / DEPLOYMENT / HYBRID）。"""
    root_path = Path(root)
    sfile = str(session_file or (root_path / ".req_session.json"))
    store = ReqSessionStore(sfile, str(root_path), "claude-sonnet")
    target_chat_id = chat_id or store.get_active_chat_id(WEB_CHAT_ID)
    norm_type = normalize_req_type(req_type)
    updated_sess = store.set_req_type(
        target_chat_id,
        norm_type,
        source="auto" if norm_type == "AUTO" else "manual",
    )
    return {
        "ok": True,
        "req_type": updated_sess["req_type"],
        "req_type_source": updated_sess["req_type_source"],
        "req_type_reason": updated_sess["req_type_reason"],
        "session": updated_sess,
    }


def run_web_req_turn(
    root: str | Path,
    user_text: str,
    agent_name: str | None = None,
    mode: str | None = None,
    req_type: str | None = None,
    session_file: str | Path | None = None,
    chat_id: str | None = None,
) -> dict[str, Any]:
    """在网页端执行一轮需求澄清对话（与飞书共享 ReqSessionStore、双轨分类及 execute_clarification_turn，O1）。"""
    root_path = Path(root)
    sfile = str(session_file or (root_path / ".req_session.json"))
    store = ReqSessionStore(sfile, str(root_path), "claude-sonnet")
    target_chat_id = chat_id or store.get_active_chat_id(WEB_CHAT_ID)

    clean_text = user_text.strip()
    if clean_text in ("/new", "新需求", "/reset"):
        store.reset_session(target_chat_id)
        return {
            "ok": True,
            "reply": "🌱 已开启全新的需求澄清会话！请直接输入你的想法，我会结合当前项目代码模块与部署目录自动帮你寻找并分类（软件研发 / 环境部署）。",
            "choices": [],
            "session": store.get(target_chat_id),
        }

    if clean_text.startswith("/type "):
        target_t = clean_text.split(maxsplit=1)[1].strip()
        res = set_web_req_type(root_path, target_t, session_file=sfile, chat_id=target_chat_id)
        return {
            "ok": True,
            "reply": f"🧭 需求类型已切换为：`{res['req_type']}`（{res['req_type_reason']}）",
            "choices": [],
            "session": res["session"],
        }

    outcome = execute_clarification_turn(
        store=store,
        chat_id=target_chat_id,
        user_text=clean_text,
        timeout=300,
        agent_override=agent_name,
        mode_override=mode,
        req_type_override=req_type,
        channel="web",
    )

    return {
        "ok": outcome.ok,
        "reply": outcome.reply_text,
        "summary": outcome.semantic.summary_markdown,
        "choices": [
            {"index": c.index, "label": c.label, "description": c.description}
            for c in outcome.semantic.choices
        ],
        "duration_sec": outcome.duration_sec,
        "full_model_id": outcome.full_model_id,
        "req_type": outcome.req_type,
        "req_type_source": outcome.req_type_source,
        "req_type_reason": outcome.req_type_reason,
        "archived_filename": outcome.archived_filename,
        "session": store.get(target_chat_id),
    }
