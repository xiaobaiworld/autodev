"""固化并比对两次运行。纯程序，不调用模型。

python3 -m driver.compare digest <需求目录>        # 生成 digest.json（可重复运行，结果相同）
python3 -m driver.compare diff <需求目录A> <需求目录B>  # 比对两份摘要，A 为基线

摘要只含从 record-a*.json 和需求文件、模板算出来的事实，所以比对不用再翻 Agent 日志，
同样的两份摘要永远得到同样的报告。比对前先看“可比性”：需求文本、模板、模型不同，差异就不能全算成优化的效果。
"""
import hashlib
import json
import sys
from pathlib import Path

from cockpit.store import atomic_write
from driver.record import normalize_usage, summarize_run


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _request_text(run_dir):
    """需求正文（去掉 frontmatter，因为里面有编号和提交时间，每次都不同）。"""
    run_dir = Path(run_dir)
    f = run_dir.parents[1] / "requests" / "active" / f"{run_dir.name}.md"
    if not f.exists():
        f = run_dir.parents[1] / "requests" / "done" / f"{run_dir.name}.md"
    text = f.read_text(encoding="utf-8") if f.exists() else ""
    parts = text.split("---\n", 2)
    return parts[2].strip() if text.startswith("---\n") and len(parts) == 3 else text.strip()


def _input_scope(sd):
    """input.md 里“输入文件”和“范围”两节的内容，用来看改了说明有没有进到输入里。去掉随编号变化的路径前缀。"""
    f = Path(sd) / "input.md"
    return f.read_text(encoding="utf-8") if f.exists() else ""


def _run_template_hash(run_dir):
    """取这次运行各步记录里的模板哈希；老记录没有就是 None（未记录），不拿现在的模板去猜。"""
    hashes = {json.loads(p.read_text())["template_hash"] if "template_hash" in json.loads(p.read_text()) else None
              for p in Path(run_dir).glob("S*/round-*/record-a*.json")}
    return hashes.pop() if len(hashes) == 1 else ("mixed" if hashes else None)


def build_digest(run_dir):
    run_dir = Path(run_dir)
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    steps = []
    for p in sorted(run_dir.glob("S*/round-*/record-a*.json"), key=lambda p: json.loads(p.read_text())["recorded_at"]):
        r = json.loads(p.read_text(encoding="utf-8"))
        steps.append({"stage": r["stage"], "round": r["round"], "attempt": r["attempt"], "agent": r["agent"],
                      "model": r.get("actual_model") or r.get("configured_model"), "verdict": r["verdict"],
                      "tokens": normalize_usage(r.get("usage")), "commands": r.get("commands_run"),
                      "has_scope_note": "## 范围" in _input_scope(p.parent)})
    kind = state.get("kind")
    return {"schema_version": 1, "id": state["id"], "kind": kind, "status": state["status"],
            "request_hash": _sha(_request_text(run_dir)),
            "template_hash": _run_template_hash(run_dir),
            "steps": steps, "summary": summarize_run(run_dir)}


def write_digest(run_dir):
    d = build_digest(run_dir)
    path = Path(run_dir) / "digest.json"
    atomic_write(path, json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    return path


def _load(run_dir):
    p = Path(run_dir) / "digest.json"
    if not p.exists():
        write_digest(run_dir)
    return json.loads(p.read_text(encoding="utf-8"))


def _pct(a, b):
    return "—" if not a else f"{(b - a) / a * 100:+.0f}%"


def diff_digests(a, b):
    """返回比对结果的字典：可比性问题、总量差异、按阶段差异、结论序列、返工轮数。"""
    issues = []
    if a["request_hash"] != b["request_hash"]:
        issues.append("需求文本不同：两次做的不是同一件事，差异不能全算成优化的效果")
    if a["template_hash"] is None or b["template_hash"] is None:
        issues.append("模板版本未记录（老记录）：无法判断两次用的模板是否相同")
    elif a["template_hash"] != b["template_hash"]:
        issues.append("模板不同：这正是要比较的改动，则下面的差异可归因于它；若还有别的改动则无法分开")
    sa, sb = {s["has_scope_note"] for s in a["steps"]}, {s["has_scope_note"] for s in b["steps"]}
    if sa != sb:  # 看 Agent 实际收到的 input.md，比看模板更准
        issues.append(f"步骤输入不同：范围说明 {'有' if True in sa else '无'} → {'有' if True in sb else '无'}（这是被比较的改动）")
    ma = sorted({s["model"] for s in a["steps"]}); mb = sorted({s["model"] for s in b["steps"]})
    if ma != mb:
        issues.append(f"实际模型不同：{ma} → {mb}")
    if a["summary"]["total"]["no_usage"] or b["summary"]["total"]["no_usage"]:
        issues.append("有的步骤没有用量，合计偏低")
    rows = {}
    for stage in sorted(set(a["summary"]["by_stage"]) | set(b["summary"]["by_stage"])):
        x = a["summary"]["by_stage"].get(stage, {"steps": 0, "input": 0, "cached": 0, "output": 0})
        y = b["summary"]["by_stage"].get(stage, {"steps": 0, "input": 0, "cached": 0, "output": 0})
        rows[stage] = {"steps": (x["steps"], y["steps"]), "input": (x["input"], y["input"]),
                       "output": (x["output"], y["output"])}
    seq = lambda d: [f"{s['stage']}:{s['verdict']}" for s in d["steps"]]
    return {"comparability": issues, "total": {k: (a["summary"]["total"][k], b["summary"]["total"][k])
                                                for k in ("steps", "input", "cached", "output")},
            "by_stage": rows, "verdicts": (seq(a), seq(b)),
            "design_rounds": (a["summary"]["design_rounds"], b["summary"]["design_rounds"])}


def render(a, b, d):
    out = [f"基线 {a['id']}  →  对照 {b['id']}", ""]
    out += ["可比性：" + ("无明显问题" if not d["comparability"] else "")] + [f"  - {i}" for i in d["comparability"]]
    out.append("")
    for name, (x, y) in [("步数", d["total"]["steps"]), ("设计轮数", d["design_rounds"]),
                         ("总输入", d["total"]["input"]), ("其中缓存", d["total"]["cached"]), ("总输出", d["total"]["output"])]:
        out.append(f"{name:<8}{x:>12,} → {y:>12,}  {_pct(x, y)}")
    out += ["", "按阶段（输入 token）"]
    for st, r in d["by_stage"].items():
        x, y = r["input"]
        out.append(f"  {st:<4}{r['steps'][0]}步→{r['steps'][1]}步  {x:>10,} → {y:>10,}  {_pct(x, y)}")
    out += ["", "结论序列", "  基线：" + " ".join(d["verdicts"][0]), "  对照：" + " ".join(d["verdicts"][1])]
    return "\n".join(out) + "\n"


def main(argv):
    if len(argv) == 2 and argv[0] == "digest":
        print(write_digest(argv[1]))
        return 0
    if len(argv) == 3 and argv[0] == "diff":
        a, b = _load(argv[1]), _load(argv[2])
        print(render(a, b, diff_digests(a, b)), end="")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
