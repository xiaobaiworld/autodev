"""每步结束写一份 record-a<次>.json 并把 Agent 的原始日志留进需求目录。

程序能确定的事实由这里记（输入、输出、中台运行号、实际模型、用量、耗时、日志）；
“为什么”由 Agent 写在 done.json 的 summary 里，这里只原样带上。
中台的日志在 <home>/worker/runs/<运行号>-<次>/，靠 context.json 里的事件 id 找到。
"""
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from cockpit.store import atomic_write
from driver.runner import event_id


def find_worker_run(home, key):
    """返回含有事件 key 的最新一个 worker 运行目录，没有则 None。"""
    best = None
    for ctx in Path(home, "worker", "runs").glob("*/context.json"):
        try:
            if any(e.get("id") == key for e in json.loads(ctx.read_text(encoding="utf-8")).get("events", [])):
                m = re.fullmatch(r"(\d+)-(\d+)", ctx.parent.name)
                rank = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
                if best is None or rank > best[0]:
                    best = (rank, ctx.parent)
        except (OSError, ValueError):
            continue
    return best[1] if best else None


def parse_log(path):
    """从 Claude（-p stream-json）或 Codex（exec --json）日志取：实际模型、用量、总结、动作。取不到的字段是 None。"""
    out = {"cli": None, "model": None, "usage": None, "cost_usd": None, "duration_ms": None,
           "final_message": None, "commands": 0, "files_changed": [], "reasoning": []}
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            j = json.loads(line)
        except ValueError:
            continue
        t = j.get("type")
        if t == "system" and j.get("subtype") == "init":
            out["cli"], out["model"] = "claude", j.get("model")
        elif t == "result" and "usage" in j:
            out.update(cli="claude", usage=j["usage"], cost_usd=j.get("total_cost_usd"),
                       duration_ms=j.get("duration_ms"), final_message=j.get("result"))
        elif t == "thread.started":
            out["cli"] = "codex"
        elif t == "turn.completed":
            out["usage"] = j.get("usage")
        elif t == "item.completed":
            it = j.get("item") or {}
            kind = it.get("type")
            if kind == "agent_message":
                out["final_message"] = it.get("text")
            elif kind == "command_execution":
                out["commands"] += 1
            elif kind == "file_change":
                out["files_changed"] += [c.get("path") for c in it.get("changes", []) if c.get("path")]
            elif kind == "reasoning" and it.get("text"):
                out["reasoning"].append(it["text"])
    return out


def codex_model_from_command(path):
    m = re.search(r"'-m'\s+'([^']+)'|\s-m\s+(\S+)", Path(path).read_text(encoding="utf-8", errors="replace"))
    return (m.group(1) or m.group(2)) if m else None


def _files(d, names):
    return [str(Path(d) / n) for n in names]


def write_record(home, run_dir, state, now=None):
    """给 state 里当前这一步写记录。返回 record 路径；找不到中台日志时仍写，并在 notes 里说明。"""
    step, run_dir = state["step"], Path(run_dir)
    sd = run_dir / step["dir"]
    key = event_id(state)
    done = json.loads((sd / "done.json").read_text(encoding="utf-8"))
    rec = {"schema_version": 1, "id": state["id"], "kind": state.get("kind"), "stage": state["stage"],
           "round": state["round"], "attempt": step["attempt"], "role": step["role"], "agent": step["agent"],
           "configured_model": step.get("model"), "started_at": step.get("started_at"),
           "recorded_at": (now or datetime.now().astimezone()).isoformat(timespec="seconds"),
           "event_id": key, "input": str(sd / "input.md"), "outputs": _files(sd, done.get("outputs", [])),
           "verdict": done.get("verdict"), "summary": done.get("summary"), "notes": []}
    wr = find_worker_run(home, key)
    if wr is None:
        rec["notes"].append("没有找到中台的运行目录，原始日志没有留存")
    else:
        rec["hub_run"] = wr.name
        log = wr / "stdout-1.log"
        logs = sorted(wr.glob("stdout-*.log"))
        if logs:
            log = logs[-1]
        p = parse_log(log)
        if p["cli"] == "codex" and (wr / "command-1.sh").exists():
            p["model"] = codex_model_from_command(wr / "command-1.sh")
        rec["actual_model"], rec["usage"], rec["cost_usd"] = p["model"], p["usage"], p["cost_usd"]
        rec["duration_ms"] = p["duration_ms"]
        rec["agent_final_message"] = p["final_message"]
        rec["commands_run"], rec["files_changed"], rec["reasoning"] = p["commands"], p["files_changed"], p["reasoning"]
        dst = sd / f"agent-a{step['attempt']}.log"
        shutil.copyfile(log, dst)
        rec["log"] = str(dst)
        if p["model"] is None:
            rec["notes"].append("日志里没取到实际模型")
        elif step.get("model") and not str(step["model"]).endswith(str(p["model"]).split("/")[-1]):
            rec["notes"].append(f"实际模型 {p['model']} 与配置 {step['model']} 不一致")
    path = sd / f"record-a{step['attempt']}.json"
    atomic_write(path, json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
    return path
