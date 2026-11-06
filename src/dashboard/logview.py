"""把 Agent 的 stdout 日志（Claude stream-json、Codex exec --json、agy 纯文本）转成可读的几行字，并找到最新一轮的日志。

日志路径是 <autoloop 数据目录>/worker/runs/<轮次>-<尝试>/stdout-<第几次启动>.log。
"""
import json
import re
from pathlib import Path

from dashboard.text import width as _w  # 显示宽度

WIDTH = 110
NOISE = {"system", "rate_limit_event", "thread.started", "turn.started"}
TARGET_KEYS = ("file_path", "command", "path", "pattern", "url", "query", "description")


def fit(s, width):
    """按显示宽度截断（中文占 2 列），超出的用 … 代替。只截断，不改空白。"""
    s = str(s)
    if _w(s) <= width:
        return s
    out, used = "", 0
    for ch in s:
        cw = _w(ch)
        if used + cw > width - 1:
            break
        out, used = out + ch, used + cw
    return out + "…"


def _cut(s, n=WIDTH):
    return fit(" ".join(str(s).split()), n)  # 日志行：压缩空白后再截断


def _lines(text, prefix, limit=2):
    rows = [l for l in str(text).strip().splitlines() if l.strip()]
    out = [f"{prefix} {_cut(rows[0])}"] if rows else []
    out += [f"  {_cut(l)}" for l in rows[1:limit]]
    return out


def _claude_block(c):
    t = c.get("type")
    if t == "text":
        return _lines(c.get("text", ""), "说")
    if t == "thinking":
        return _lines(c.get("thinking", ""), "想", limit=1)
    if t == "tool_use":
        inp = c.get("input") or {}
        target = next((inp[k] for k in TARGET_KEYS if inp.get(k)), "")
        return [_cut(f"工具 {c.get('name')} {target}".strip())]
    if t == "tool_result":
        body = c.get("content")
        if isinstance(body, list):
            body = " ".join(x.get("text", "") for x in body if isinstance(x, dict))
        body = re.sub(r"^\s*\d+\t", "", body or "")
        return _lines(body, "得", limit=1)
    return []


def _codex_item(kind, item):
    t = item.get("type")
    if kind == "item.started":
        return []
    if t == "agent_message":
        return _lines(item.get("text", ""), "说")
    if t == "reasoning":
        return _lines(item.get("text", ""), "想", limit=1)
    if t == "command_execution":
        return [_cut(f"命令 {item.get('command', '')} → {item.get('exit_code')}")]
    if t == "file_change":
        return [_cut(f"改文件 {c.get('kind')} {c.get('path')}") for c in item.get("changes", [])]
    return []


def format_line(raw):
    """一行日志 -> 0 到几行可读文字。解析不了的原样当文字，不抛异常。"""
    raw = raw.rstrip("\n")
    if not raw.strip():
        return []
    try:
        d = json.loads(raw)
    except ValueError:
        return [_cut(raw.strip())] if not raw.lstrip().startswith("{") else [_cut(raw)]
    if not isinstance(d, dict):
        return [_cut(raw)]
    t = d.get("type")
    if t in NOISE:
        return []
    if t in ("assistant", "user"):
        out = []
        for c in (d.get("message") or {}).get("content") or []:
            if isinstance(c, dict):
                out += _claude_block(c)
        return out
    if t == "result":
        if d.get("is_error"):
            return [_cut(f"出错 {d.get('result') or d.get('subtype') or ''}")]
        secs = round((d.get("duration_ms") or 0) / 1000)
        return [f"完成 {secs}s ${d.get('total_cost_usd') or 0:.3f}"]
    if t in ("item.started", "item.completed"):
        return _codex_item(t, d.get("item") or {})
    if t == "turn.completed":
        u = d.get("usage") or {}
        return [f"完成 输入 {u.get('input_tokens', 0)} 输出 {u.get('output_tokens', 0)}"]
    return []


def latest_log(runs_dir):
    """最新一轮的日志：轮次号最大，其次尝试号、启动次数最大。按数字比，不按修改时间。"""
    best, best_key = None, None
    base = Path(runs_dir)
    if not base.is_dir():
        return None
    for d in base.iterdir():
        m = re.fullmatch(r"(\d+)-(\d+)", d.name)
        if not (m and d.is_dir()):
            continue
        for f in d.glob("stdout-*.log"):
            n = re.fullmatch(r"stdout-(\d+)\.log", f.name)
            if n:
                key = (int(m.group(1)), int(m.group(2)), int(n.group(1)))
                if best_key is None or key > best_key:
                    best, best_key = f, key
    return best


def tail_lines(path, count, max_bytes=200_000):
    """读文件末尾的 max_bytes，格式化后取最后 count 行。大文件不整个读进来。"""
    p = Path(path)
    size = p.stat().st_size
    with open(p, "rb") as f:
        if size > max_bytes:
            f.seek(size - max_bytes)
            f.readline()  # 丢掉被截断的半行
        text = f.read().decode("utf-8", errors="replace")
    out = []
    for raw in text.splitlines():
        out += format_line(raw)
    return out[-count:]
