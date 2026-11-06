"""对比两次流水线运行，并先列出可比性限制。"""
import json
import sys

from driver.record import digest


def diff(left_dir, right_dir):
    left, right = digest(left_dir), digest(right_dir)
    reasons = []
    if left.get("request_sha256") != right.get("request_sha256"):
        reasons.append("需求正文不同")
    if left.get("config_template_hashes") != right.get("config_template_hashes"):
        reasons.append("config.yaml 或流水线模板不同")
    def models(run):
        return {(r.get("stage"), r.get("role")): r.get("actual_model") for r in run["records"] if not r.get("tool")}
    lm, rm = models(left), models(right)
    for key in sorted(lm.keys() & rm.keys()):
        if lm[key] and rm[key] and lm[key] != rm[key]:
            reasons.append(f"{key[0]} {key[1]} 实际模型不同：{lm[key]} / {rm[key]}")
    for label, run in (("左侧", left), ("右侧", right)):
        missing = [f"{r.get('stage')} {r.get('role')}" for r in run["records"]
                   if not r.get("tool") and (not r.get("actual_model") or not r.get("usage"))]
        if missing:
            reasons.append(f"{label}模型或用量未验证：" + ", ".join(missing))
    left_steps = [(r.get("stage"), r.get("round"), r.get("attempt"), r.get("verdict"), r.get("summary")) for r in left["records"]]
    right_steps = [(r.get("stage"), r.get("round"), r.get("attempt"), r.get("verdict"), r.get("summary")) for r in right["records"]]
    return {"comparable": not reasons, "limitations": reasons,
            "runs": {"left": left["id"], "right": right["id"]},
            "outcome": {"left": {"status": left["status"], "stage": left["stage"],
                                  "counters": left["counters"], "usage_totals": left["usage_totals"]},
                        "right": {"status": right["status"], "stage": right["stage"],
                                   "counters": right["counters"], "usage_totals": right["usage_totals"]}},
            "steps": {"left": left_steps, "right": right_steps}}


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 2 and args[0] == "digest":
        result = digest(args[1])
    elif len(args) == 3 and args[0] == "diff":
        result = diff(args[1], args[2])
    else:
        print("用法：python3 -m driver.compare digest <run_dir> | diff <left_run_dir> <right_run_dir>", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
