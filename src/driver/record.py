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


def normalize_usage(usage):
    """把 Claude / Codex 的用量归成同一套：input（总输入）、cached（其中缓存命中）、output（含推理）。取不到返回 None。
    按字段名判断来源，所以老记录也能用。
    Claude：input_tokens 不含缓存，总输入 = 新输入 + 缓存读 + 缓存写。
    Codex：按 OpenAI 的口径，input_tokens 已含 cached_input_tokens（这一点我没有在 Codex 文档里核实，见 DATA_SPEC 7.2.1）。"""
    if not isinstance(usage, dict):
        return None
    if "cache_read_input_tokens" in usage or "cache_creation_input_tokens" in usage:
        cached = usage.get("cache_read_input_tokens") or 0
        total = (usage.get("input_tokens") or 0) + cached + (usage.get("cache_creation_input_tokens") or 0)
    elif "cached_input_tokens" in usage:
        cached, total = usage.get("cached_input_tokens") or 0, usage.get("input_tokens") or 0
    else:
        return None
    return {"input": total, "cached": cached, "output": usage.get("output_tokens") or 0}


def summarize_run(run_dir):
    """汇总一个需求目录下所有 record-a*.json：总用量、按阶段、按 Agent、返工轮数。纯读文件。"""
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(run_dir).glob("S*/round-*/record-a*.json"))]
    zero = lambda: {"steps": 0, "input": 0, "cached": 0, "output": 0, "no_usage": 0}
    total, by_stage, by_agent = zero(), {}, {}
    for r in recs:
        t = normalize_usage(r.get("usage"))
        for bucket in (total, by_stage.setdefault(r["stage"], zero()), by_agent.setdefault(r["agent"], zero())):
            bucket["steps"] += 1
            if t is None:
                bucket["no_usage"] += 1
            else:
                for k in ("input", "cached", "output"):
                    bucket[k] += t[k]
    return {"records": len(recs), "total": total, "by_stage": by_stage, "by_agent": by_agent,
            "design_rounds": max([r["round"] for r in recs if r["stage"] == "S2"] or [0])}


def template_hash(kind):
    """运行当时的模板内容哈希。比对时用它判断模板是否相同，不能等到生成摘要时再算（那时模板可能已经改了）。"""
    from driver.compare import _sha
    from cockpit.pipeline import TEMPLATES
    f = TEMPLATES / (kind.split("/", 1)[1] + ".json") if kind else None
    return _sha(f.read_text(encoding="utf-8")) if f and f.exists() else None


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
           "verdict": done.get("verdict"), "summary": done.get("summary"), "notes": [],
           "template_hash": template_hash(state.get("kind"))}
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
        rec["tokens"] = normalize_usage(p["usage"])  # 统一口径，Claude 和 Codex 可以直接比
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


if __name__ == "__main__":
    import sys
    s = summarize_run(sys.argv[1])
    row = lambda n, b: print(f"{n:<14}{b['steps']:>3} 步  输入 {b['input']:>9,}（缓存 {b['cached']:>9,}）  输出 {b['output']:>7,}"
                             + (f"  [{b['no_usage']} 步无用量]" if b["no_usage"] else ""))
    print(f"{sys.argv[1]}：{s['records']} 份记录，设计共 {s['design_rounds']} 轮")
    row("合计", s["total"])
    for k, v in sorted(s["by_stage"].items()):
        row(k, v)
    for k, v in sorted(s["by_agent"].items()):
        row(k, v)
