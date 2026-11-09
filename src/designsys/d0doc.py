"""D0 一页极简文档（D026）：由程序从 plan.json 与 handoff.json 生成，不由 Agent 撰写。内容只复述已有字段，不新增判断。"""
from __future__ import annotations

import json
from pathlib import Path

from designsys import rules as rl

NEEDED = ("design_level", "features", "risks", "mandatory_rules", "classification_rationale", "open_questions")
OUT_NAME = "d0-summary.md"


class D0Error(ValueError):
    """输入不是合法的 D0 设计包；消息直接给人看。"""


def _check_plan(plan) -> None:
    if not isinstance(plan, dict):
        raise D0Error("plan.json 不是对象")
    for key in NEEDED:
        if key not in plan:
            raise D0Error(f"plan.json 缺少字段 {key}")
    if plan["design_level"] != "D0":
        raise D0Error(f"这份计划的设计等级是 {plan['design_level']}，不是 D0：D0 一页文档不能替代完整设计")


def _bullets(items) -> list:
    return [f"- {x}" for x in items]


def _rule_lines(plan: dict, lib: dict) -> list:
    names = {r["rule_id"]: r for r in lib["rules"]}
    lines = []
    for rid in plan["mandatory_rules"]:
        rule = names.get(rid)
        if rule is None:
            lines.append(f"- `{rid}`：**规则库中不存在，需核对**")
            continue
        lines.append(f"- `{rid}` {rule['name']}（{rule['severity']}，成熟度 {rule['maturity']}）：{rule['requirement']}")
    return lines


def _task_lines(handoff) -> list:
    if not isinstance(handoff, dict):
        return ["- 尚未提供交接文件（handoff.json），因此没有开发任务可列；这里不代为编造。"]
    lines = []
    for t in handoff.get("tasks", []):
        ids = "、".join(t.get("mandatory_rule_ids", [])) or "无"
        lines.append(f"- `{t['task_id']}` {t['title']}（需求 {'、'.join(t.get('requirement_ids', []))}；强制规则 {ids}）")
    if not lines:
        return ["- 交接文件里没有任务。"]
    return lines


def render(plan, handoff, library=None) -> str:
    """渲染 D0 一页文档。非 D0 的计划拒绝，不当作 D0 渲染。"""
    _check_plan(plan)
    lib = library or rl.load_library()
    feats = plan["features"]
    risks = plan["risks"]
    feat_text = "、".join(feats) if feats else "无功能特征"
    risk_text = "、".join(risks) if risks else "无"
    L = []
    a = L.append
    a("# D0 设计摘要")
    a("")
    a("> 本页由程序根据 `plan.json` 与 `handoff.json` 自动生成，只复述其中已有的内容，没有任何 Agent 新写的判断。设计等级 D0 表示跳过独立设计，**不表示豁免工程规则**。")
    a("")
    a("## 设计等级与判定依据")
    a("")
    a(f"- 设计等级：**{plan['design_level']}**")
    a(f"- 项目类型：{plan.get('project_type', '未填写')}")
    a(f"- 功能特征：{feat_text}")
    a(f"- 风险：{risk_text}")
    a("- 判定依据（取自计划，原文）：")
    L.extend("  " + x for x in _bullets(plan["classification_rationale"]))
    a("")
    a("## 跳过独立设计的理由")
    a("")
    a("- 跳过独立设计的依据就是上面的判定依据；D0 只出本页与开发交接，不要求额外的技术设计文档。")
    a("- 若需求并不明确，或存在未决问题，按规则不应判为 D0。")
    a("")
    a("## 适用的工程规则")
    a("")
    L.extend(_rule_lines(plan, lib))
    a("")
    a("> 当前所有规则的成熟度是 R1（结构化），**没有验证器，不由程序强制执行**；写在这里表示必须在开发任务里落实，不表示已经被检查过。")
    a("")
    a("## 未决问题")
    a("")
    L.extend(_bullets(plan["open_questions"]) or ["- 无"])
    a("")
    a("## 开发交接")
    a("")
    L.extend(_task_lines(handoff))
    return "\n".join(L) + "\n"


def _read(path: Path, label: str):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise D0Error(f"{label} 无法解析：{e}")


def write(root) -> Path:
    """读取设计包目录里的 plan.json 与（若有）handoff.json，在同一目录写出 d0-summary.md。"""
    root = Path(root)
    plan = _read(root / "plan.json", "plan.json")
    if plan is None:
        raise D0Error(f"{root} 里没有 plan.json，无法生成 D0 摘要")
    handoff = _read(root / "handoff.json", "handoff.json")
    text = render(plan, handoff)
    out = root / OUT_NAME
    out.write_text(text, encoding="utf-8")
    return out
