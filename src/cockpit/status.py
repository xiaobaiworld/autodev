"""状态区：窗格状态映射与文字渲染（设计 2.4）。纯函数，不调用 hc。"""
import unicodedata
from datetime import datetime

SHELLS = {"zsh", "bash", "sh", "fish"}
WIDTHS = [6, 12, 15, 6]
SEPS = [1, 1, 2, 2]


def pane_state(agent, term, step):
    """term: hc 的终端记录或 None；step: state.json 的 step 或 None。"""
    if term is None:
        return "丢失"
    if not step or step.get("agent") != agent:
        return "空闲"
    s = step.get("state")
    if s == "pending":
        return "等待"
    if s in ("finished", "failed"):
        fg = (term.get("foreground") or {}).get("name")
        return "已结束" if fg in SHELLS else "运行中"
    return "运行中"


def elapsed(started, now):
    if not started:
        return "-"
    try:
        sec = max(0, int((now - datetime.fromisoformat(started)).total_seconds()))
    except (ValueError, TypeError):
        return "-"
    return f"{sec // 60:02d}:{sec % 60:02d}"


def _w(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _row(cells):
    out = " "
    for i, c in enumerate(cells):
        if i == len(cells) - 1:
            out += c
        else:
            out += c + " " * (WIDTHS[i] - _w(c) + SEPS[i])
    return out.rstrip()


def render(run, panes, terms, now):
    """panes: {agent: 地址}；terms: {地址: hc 终端记录}；run: state.json 或 None。"""
    step = (run or {}).get("step")
    if run:
        head = f"AutoDev  {run['id']}  {run['stage']}  第 {run['round']} 轮"
    else:
        head = "AutoDev  没有进行中的需求"
    lines = [head, "─" * 46,
             _row(["窗格", "Agent", "角色", "状态", "用时"])]
    for agent, addr in panes.items():
        st = pane_state(agent, terms.get(addr), step)
        mine = bool(step) and step.get("agent") == agent
        role = (step.get("role") or "-") if mine else "-"
        used = elapsed(step.get("started_at"), now) if mine and st == "运行中" else "-"
        lines.append(_row([addr, agent, role, st, used]))
    waiting = 1 if run and (run.get("human") or {}).get("waiting") else 0
    lines.append(f"待你决定：{waiting}")
    return "\n".join(lines) + "\n"
