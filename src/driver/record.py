"""每步执行记录、token 归一化与运行摘要。"""
import hashlib
import json
import re
import sys
from pathlib import Path

from cockpit.store import atomic_write, now_iso

TOKEN_KEYS = {"input_tokens", "prompt_tokens", "inputTokens", "output_tokens", "completion_tokens",
              "outputTokens", "cached_input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"}


def _walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def parse_log(text):
    """读 Claude stream-json 或 Codex exec-json，返回最末模型与累计用量摘要。"""
    objects = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("{"):
            try:
                objects.append(json.loads(stripped))
            except json.JSONDecodeError:
                continue
    models, usage_candidates = [], []
    for obj in objects:
        for item in _walk(obj):
            model = item.get("model") or item.get("model_name") or item.get("actual_model")
            if isinstance(model, str) and model not in models:
                models.append(model)
            for key, candidate in item.items():
                if key == "usage" and isinstance(candidate, dict) and TOKEN_KEYS.intersection(candidate):
                    usage_candidates.append(candidate)
    usage = None
    if usage_candidates:
        raw = usage_candidates[-1]
        def value(*keys):
            for key in keys:
                try:
                    return int(raw[key])
                except (KeyError, TypeError, ValueError):
                    pass
            return 0
        input_tokens = value("input_tokens", "prompt_tokens", "inputTokens")
        output_tokens = value("output_tokens", "completion_tokens", "outputTokens")
        cached = value("cached_input_tokens", "cache_read_input_tokens") + value("cache_creation_input_tokens")
        usage = {"input_tokens": input_tokens, "output_tokens": output_tokens,
                 "cached_input_tokens": cached, "total_tokens": input_tokens + output_tokens}
    return {"actual_model": models[-1] if models else None, "usage": usage}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _request_sha(path):
    text = Path(path).read_text(encoding="utf-8")
    body = text.split("\n\n", 1)[1] if "\n\n" in text else text
    return hashlib.sha256(body.strip().encode()).hexdigest()


def write_agent_record(run_dir, state, agent, result):
    folder, step = Path(run_dir) / state["step"]["dir"], state["step"]
    raw = result.get("agent_log", "")
    log_name = f"agent-a{step['attempt']}.log"
    if raw:
        atomic_write(folder / log_name, raw)
    parsed = parse_log(raw)
    done_path = folder / "done.json"
    summary = state["step"].get("summary")
    if done_path.is_file():
        try:
            summary = json.loads(done_path.read_text(encoding="utf-8")).get("summary", summary)
        except ValueError:
            pass
    record = {"schema_version": 1, "id": state["id"], "stage": state["stage"], "round": state["round"],
              "attempt": step["attempt"], "role": step["role"], "agent": step["agent"],
              "vendor": agent.get("vendor"), "configured_model": agent.get("model"),
              "actual_model": parsed["actual_model"], "model_source": "log" if parsed["actual_model"] else "unverified",
              "effort": agent.get("effort"), "hub_run_id": result.get("hub_run_id"),
              "hub_attempts": result.get("hub_attempts"), "usage": parsed["usage"],
              "ok": bool(result.get("ok")), "reason": result.get("reason"), "detail": result.get("detail"),
              "summary": summary, "input_sha256": _sha(folder / "input.md") if (folder / "input.md").is_file() else None,
              "log": log_name if raw else None, "recorded_at": now_iso()}
    atomic_write(folder / f"record-a{step['attempt']}.json", json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    return record


def write_tool_record(run_dir, state, spec, verdict):
    folder, step = Path(run_dir) / state["step"]["dir"], state["step"]
    data = json.loads((folder / "done.json").read_text(encoding="utf-8"))
    record = {"schema_version": 1, "id": state["id"], "stage": state["stage"], "round": state["round"],
              "attempt": step["attempt"], "role": step["role"], "tool": spec.get("tool"),
              "verdict": verdict, "ok": verdict in ("PASS", "DONE"), "summary": data.get("summary"),
              "usage": None, "recorded_at": now_iso()}
    atomic_write(folder / f"record-a{step['attempt']}.json", json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    return record


def digest(run_dir):
    run_dir = Path(run_dir).resolve()
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    root = run_dir.parents[2]
    request = root / "workspace" / "requests" / "active" / f"{state['id']}.md"
    records = []
    for path in sorted(run_dir.glob("S*/round-*/record-a*.json")):
        records.append(json.loads(path.read_text(encoding="utf-8")))
    inputs = sorted((p.relative_to(run_dir).as_posix(), _sha(p)) for p in run_dir.glob("S*/round-*/input.md"))
    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "known_steps": 0, "unknown_steps": 0}
    for record in records:
        usage = record.get("usage")
        if usage:
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                totals[key] += usage.get(key, 0)
            totals["known_steps"] += 1
        elif record.get("tool") is None:
            totals["unknown_steps"] += 1
    hashes = {}
    for name in ("config.yaml", "templates/pipeline/design.json", "templates/pipeline/build.json"):
        path = root / name
        if path.is_file():
            hashes[name] = _sha(path)
    return {"id": state["id"], "kind": state.get("kind"), "status": state["status"], "stage": state["stage"],
            "round": state["round"], "counters": state.get("counters", {}),
            "request_sha256": _request_sha(request) if request.is_file() else None,
            "config_template_hashes": hashes, "input_hashes": inputs,
            "workdir_head": _head(Path(state["workdir"])) if state.get("workdir") and (Path(state["workdir"]) / ".git").exists() else None,
            "records": records, "usage_totals": totals}


def _head(path):
    import subprocess
    p = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("用法：python3 -m driver.record <workspace/runs/需求号>", file=sys.stderr)
        return 2
    print(json.dumps(digest(args[0]), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
