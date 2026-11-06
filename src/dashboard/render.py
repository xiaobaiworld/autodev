"""命令行看板的渲染：输入中台 /v1/state 和我们自己的 state.json，输出一屏文字。纯函数，不碰网络。"""
from datetime import datetime

from dashboard.width import _w  # 按显示宽度对齐中文

RUN_STATE = {"claimed": "运行中", "queued": "排队", "nothing": "已结束", "done": "已结束", "cancelled": "已取消"}


def _parse(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def fmt_elapsed(since, now):
    t = _parse(since)
    if t is None:
        return "-"
    sec = max(0, int((now - t).total_seconds()))
    h, rest = divmod(sec, 3600)
    return f"{h}:{rest // 60:02d}:{rest % 60:02d}" if h else f"{rest // 60:02d}:{rest % 60:02d}"


def _pad(s, width):
    return s + " " * max(0, width - _w(s))


def _one_line(text, limit=60):
    line = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    return line if len(line) <= limit else line[:limit - 1] + "…"


def _run_row(r, now):
    st = RUN_STATE.get(r.get("state"), r.get("state") or "?")
    note = ""
    if r.get("state") == "queued" and (r.get("attempts") or 0) > 0:
        st, note = "重试中", f"第 {r['attempts']} 次  {_one_line(r.get('error'))}"
    elif r.get("state") == "cancelled":
        note = _one_line(r.get("summary"))
    used = fmt_elapsed(r.get("claimedAt"), now) if r.get("state") == "claimed" else "-"
    return f" #{r['id']:<4}{_pad(r.get('rule') or '-', 20)}{_pad(r.get('agent') or '-', 13)}{_pad(st, 8)}{_pad(used, 8)}{note}".rstrip()


STATUS_WORD = {"active": "进行中", "needs-human": "等你", "done": "已完成", "rejected": "已拒绝"}
LIVE = ("active", "needs-human")


def _when(p):
    t = _parse(p.get("updated_at"))
    return t.timestamp() if t else 0


def _pick_requests(pipelines, max_requests):
    """进行中、等你的需求一个都不折叠；已结束的按最近更新排序，只留剩下的名额，其余折成一个数。"""
    newest_first = sorted(pipelines, key=_when, reverse=True)
    ordered = sorted(newest_first, key=lambda p: {"active": 0, "needs-human": 1}.get(p.get("status"), 2))
    live = [p for p in ordered if p.get("status") in LIVE]
    finished = [p for p in ordered if p.get("status") not in LIVE]
    slots = max(0, max_requests - len(live))
    return live + finished[:slots], max(0, len(finished) - slots)


def _request_line(p):
    word = STATUS_WORD.get(p.get("status"), p.get("status") or "?")
    line = f" {p.get('id', '?')}  {p.get('kind') or '未分类'}  {p.get('stage', '-')}  第 {p.get('round', '-')} 轮  {word}"
    if p.get("status") in LIVE:
        step = p.get("step") or {}
        line += f"  {step.get('role') or '-'} / {step.get('agent') or '-'}：{step.get('state') or '-'}"
    return line


def wait_reason(p):
    """一个等人的需求在等什么。全部从 state.json 已有的字段推出来，推不出就老实写“等你处理”，不编原因。"""
    h, step = p.get("human") or {}, p.get("step") or {}
    stage = p.get("stage", "-")
    gate = str(h.get("pending_decision") or "")
    if gate.startswith("gate:"):
        return f"要你批准才进 {gate[5:]}"
    if step.get("state") == "failed":
        return f"{stage} 步骤失败（{step.get('fail_reason') or '原因未记录'}），重试用完"
    verdict = step.get("verdict")
    if verdict == "BLOCK":
        return f"{stage} 的 Agent 报 BLOCK，要你判断"
    if verdict == "CLARIFY":
        return f"{stage} 需求不清楚，要你澄清"
    if verdict in ("REWORK", "FAIL"):
        return f"{stage} 返工轮次用完，仍是 {verdict}"
    return "等你处理"


def render(state, pipelines, now, error=None, max_runs=12, width=70, max_requests=6, reply_cmd=None):
    out = [f"AutoDev 看板  {now.astimezone().strftime('%H:%M:%S')}", "─" * max(10, min(width, 70))]
    if error:
        out.append(f"读取失败（将继续重试）：{error}")
    out.append("")
    shown, hidden = _pick_requests(pipelines, max_requests)
    if shown:
        out += [_request_line(p) for p in shown]
    else:
        out.append(" 没有进行中的需求")
    if hidden:
        out.append(f" 另有 {hidden} 个需求（已完成或已拒绝，较早的）")
    waiting = [p for p in pipelines if (p.get("human") or {}).get("waiting")]
    if state is None:
        return "\n".join(out) + "\n"
    t = state.get("totals", {})
    out += ["", f" 运行中 {t.get('running', 0)}  排队 {t.get('queued', 0)}  重试中 {t.get('retrying', 0)}"]
    runs = sorted(state.get("runs", []), key=lambda r: r["id"], reverse=True)[:max_runs]
    if runs:
        out.append(f" {_pad('#', 5)}{_pad('规则', 20)}{_pad('Agent', 13)}{_pad('状态', 8)}{_pad('用时', 8)}")
        out += [_run_row(r, now) for r in runs]
    off = [a for a in state.get("agents", []) if not a.get("online")]
    for a in off:
        out.append(f" Agent {a.get('name') or a['id']} 离线（上次 {a.get('seenAt') or '-'}）")
    open_cards = [c for c in state.get("cards", []) if c.get("state") == "open"]
    asks = [c for c in open_cards if c.get("kind") == "ask"]
    out += ["", f" 待你决定：{len(asks) + len(waiting)}"]
    out += [f"   [{c['id']}] {c.get('title') or ''}" for c in open_cards]
    for p in waiting:
        out.append(f"   {p.get('id', '?')}  {wait_reason(p)}")
        if reply_cmd:  # 完整的、复制就能敲的命令前缀，由调用方按自己的 --home 拼好
            out.append(f"     {reply_cmd} {p.get('id', '?')} continue|rework|reject")
    sp = (state.get("spending") or {}).get("today") or {}
    out.append(f" 今天 {sp.get('rounds', 0)} 轮" + ("（费用部分未上报）" if sp.get("missingCost") else ""))
    return "\n".join(out) + "\n"
