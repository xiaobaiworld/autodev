"""设计阶段规则（D025）：按事实判定复杂度，并给出按类型的交付物、确认项与审查必查项。纯函数，不连模型，不改状态。"""
from __future__ import annotations

import tomllib
from pathlib import Path

RULES = Path(__file__).resolve().parents[2] / "config" / "design-rules.toml"
LEVELS = ("简单", "常规", "复杂")


class RuleError(ValueError):
    """规则文件或输入的事实不合法；消息直接给人看。"""


def _known(rules: dict, names, where: str) -> None:
    for name in names:
        if name not in rules["facts"]:
            raise RuleError(f"{where} 引用了未登记的事实 {name}")


def load_rules(path=RULES) -> dict:
    rules = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("facts", "complexity", "levels", "deliverables", "types"):
        if key not in rules:
            raise RuleError(f"规则文件缺少 [{key}]")
    for level in LEVELS:
        if level not in rules["levels"]:
            raise RuleError(f"规则文件缺少档位 {level} 的定义")
    cx = rules["complexity"]
    _known(rules, cx.get("complex_if_any", []), "complex_if_any")
    for group in cx.get("complex_if_all", []):
        _known(rules, group, "complex_if_all")
    _known(rules, cx.get("simple_requires_true", []), "simple_requires_true")
    _known(rules, cx.get("simple_requires_false", []), "simple_requires_false")
    dv = rules["deliverables"]
    _known(rules, dv.get("when", {}), "deliverables.when")
    _known(rules, dv.get("confirm", {}), "deliverables.confirm")
    return rules


def _check_facts(rules: dict, facts: dict) -> None:
    for name in rules["facts"]:
        if name not in facts:
            raise RuleError(f"缺少事实 {name}：由程序取得，不能省略或猜测")
        if not isinstance(facts[name], bool):
            raise RuleError(f"事实 {name} 必须是 true 或 false，收到 {facts[name]!r}")


def classify(rules: dict, facts: dict) -> str:
    """返回 简单 / 常规 / 复杂。事实缺失或不是布尔值时拒绝，不猜。"""
    _check_facts(rules, facts)
    cx = rules["complexity"]
    if any(facts[n] for n in cx.get("complex_if_any", [])):
        return "复杂"
    for group in cx.get("complex_if_all", []):
        if all(facts[n] for n in group):
            return "复杂"
    need_true = cx.get("simple_requires_true", [])
    need_false = cx.get("simple_requires_false", [])
    if need_true and all(facts[n] for n in need_true):
        if not any(facts[n] for n in need_false):
            return "简单"
    return "常规"


def _parts(rules: dict, kind: str, parts):
    if kind != "HYBRID":
        if kind not in rules["types"]:
            raise RuleError(f"未知的需求类型 {kind}，已登记：{sorted(rules['types'])} 和 HYBRID")
        return [kind]
    if not parts:
        raise RuleError("HYBRID 需要用 parts 指明组成部分")
    for p in parts:
        if p == "HYBRID" or p not in rules["types"]:
            raise RuleError(f"HYBRID 的组成部分 {p} 不合法：不能嵌套 HYBRID，也必须是已登记的类型")
    return list(parts)


def _union(items):
    seen = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


def plan(rules: dict, kind: str, facts: dict, parts=None) -> dict:
    """给定类型与事实，返回复杂度、设计详略、审查深度、必须交付的文件、需用户确认的事项与审查必查项。"""
    level = classify(rules, facts)
    names = _parts(rules, kind, parts)
    dv = rules["deliverables"]
    files = list(dv["always"])
    when = dv.get("when")
    if not when:
        when = dict()
    for fact, extra in when.items():
        if facts[fact]:
            files.extend(extra)
    confirms = [text for fact, text in dv.get("confirm", {}).items() if facts[fact]]
    review = []
    sections = []
    for name in names:
        review.extend(rules["types"][name]["review"])
        sections.extend(rules["types"][name]["design_sections"])
    if kind == "HYBRID":
        review.extend(rules["hybrid"]["review"])
        sections.extend(rules["hybrid"]["design_sections"])
    return {
        "type": kind,
        "parts": names,
        "complexity": level,
        "design_detail": rules["levels"][level]["design_detail"],
        "review_depth": rules["levels"][level]["review_depth"],
        "deliverables": _union(files),
        "confirmations": confirms,
        "design_sections": _union(sections),
        "review": _union(review),
    }
