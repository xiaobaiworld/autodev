"""S1 到 S3 的阶段表、done.json 校验、结论到下一步的规则（DATA_SPEC 7.2、7.3，设计 5.3）。
纯函数，不碰文件系统以外的东西；S4 以后属于下一份计划。
"""
import json
from pathlib import Path

STAGES = {
    "S1": {"dir": "S1-analysis", "role": "analyst", "outputs": ["analysis.md"],
           "verdicts": ["ACCEPT", "REJECT", "CLARIFY", "BLOCK"],
           "task": "分析需求：写 analysis.md，frontmatter 含 verdict、summary、scope、"
                   "acceptance_criteria（列表），不明确时 verdict 写 CLARIFY 并在 questions 列出问题。"},
    "S2": {"dir": "S2-design", "role": "designer", "outputs": ["design.md", "dev-plan.md"],
           "verdicts": ["DONE", "BLOCK"],
           "task": "按分析结论写设计稿 design.md 和开发计划 dev-plan.md（frontmatter 含 verdict、summary，"
                   "dev-plan.md 另含 tasks 列表）。若有上轮审查意见，逐条回应并写 response.md。"},
    "S3": {"dir": "S3-design-review", "role": "design_reviewer", "outputs": ["review.md"],
           "verdicts": ["PASS", "REWORK", "BLOCK"],
           "task": "审查设计稿与开发计划：写 review.md，frontmatter 含 verdict、findings（列表，每项含 id、"
                   "severity、location、problem、expected）。只报会导致错误或不满足验收标准的问题，"
                   "不报风格。verdict 为 PASS 时不得有 critical 或 high 级别的问题。"},
}
ORDER = ["S1", "S2", "S3"]


def step_dir(stage, rnd):
    return f"{STAGES[stage]['dir']}/round-{rnd}"


def validate_done(run_dir, state):
    """返回 None 表示通过，否则返回原因字符串（记为 invalid_output）。"""
    step = state["step"]
    run_dir = Path(run_dir)
    stage = STAGES[state["stage"]]
    try:
        d = json.loads((run_dir / step["dir"] / "done.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return f"done.json 读不了：{e}"
    if not isinstance(d, dict):
        return "done.json 不是对象"
    for k, want in (("id", state["id"]), ("stage", state["stage"]),
                    ("round", state["round"]), ("role", step["role"])):
        if d.get(k) != want:
            return f"done.json 的 {k} 是 {d.get(k)!r}，应为 {want!r}"
    if d.get("verdict") not in stage["verdicts"]:
        return f"verdict {d.get('verdict')!r} 不在 {stage['verdicts']}"
    outs = d.get("outputs")
    if not isinstance(outs, list):
        return "outputs 不是列表"
    for need in stage["outputs"]:
        if need not in outs or not (run_dir / step["dir"] / need).is_file():
            return f"缺少产物 {need}"
    return None


def next_move(state, verdict, limits):
    """返回 (动作, 新阶段, 新轮次, 计数器增量)。动作：goto / done / rejected / needs-human / limit。"""
    stage, rnd = state["stage"], state["round"]
    if verdict == "BLOCK" or (stage == "S1" and verdict == "CLARIFY"):
        return ("needs-human", stage, rnd, {})
    if stage == "S1":
        return ("rejected", stage, rnd, {}) if verdict == "REJECT" else ("goto", "S2", 1, {})
    if stage == "S2":
        return ("goto", "S3", rnd, {})
    # S3：本阶段到此为止，PASS 即本计划范围内完成
    if verdict == "PASS":
        return ("done", stage, rnd, {})
    used = state["counters"]["design_review_rounds"] + 1
    if used >= limits["design_review_rounds"]:
        return ("limit", stage, rnd, {"design_review_rounds": 1})
    return ("goto", "S2", rnd + 1, {"design_review_rounds": 1})
