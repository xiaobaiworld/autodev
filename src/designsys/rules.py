"""工程规则库与规则选择器（V2.1 第 5、9 节）：特征与风险 → 适用规则；覆盖率分母是全部适用规则。纯函数，不连模型。"""
from __future__ import annotations

import tomllib
from pathlib import Path

from designsys import classify

LIBRARY = Path(__file__).resolve().parents[2] / "design-system" / "rules" / "library.toml"
REQUIRED = ("rule_id", "version", "name", "category", "maturity", "severity", "requirement", "verification")
MATURITY = ("R0", "R1", "R2", "R3")
OVERRIDE_FEATURES = ("auth", "sensitive_data")
OVERRIDE_RISKS = ("cross_tenant", "high_impact_operation")


class RuleLibraryError(ValueError):
    """规则库文件或输入不合法；消息直接给人看。"""


def _vocab(path=classify.RULES) -> dict:
    rules = classify.load_rules(path)
    return {"features": set(rules["features"]), "risks": set(rules["risks"])}


def _check_rule(rule: dict, vocab: dict) -> None:
    rid = rule.get("rule_id", "?")
    for key in REQUIRED:
        if key not in rule:
            raise RuleLibraryError(f"规则 {rid} 缺少字段 {key}")
    if rule["maturity"] not in MATURITY:
        raise RuleLibraryError(f"规则 {rid} 的成熟度 {rule['maturity']} 不合法")
    for f in rule.get("features", []):
        if f not in vocab["features"]:
            raise RuleLibraryError(f"规则 {rid} 引用了未登记的特征 {f}")
    for k in rule.get("risks", []):
        if k not in vocab["risks"]:
            raise RuleLibraryError(f"规则 {rid} 引用了未登记的风险 {k}")


def load_library(path=LIBRARY) -> dict:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    rules = data.get("rules", [])
    if not rules:
        raise RuleLibraryError("规则库为空")
    vocab = _vocab()
    seen = set()
    for rule in rules:
        _check_rule(rule, vocab)
        if rule["rule_id"] in seen:
            raise RuleLibraryError(f"规则 {rule['rule_id']} 重复")
        seen.add(rule["rule_id"])
    return {"version": data.get("version", ""), "rules": rules, "vocab": vocab}


def _check_case(lib: dict, case: dict) -> None:
    for f in case.get("features", ()):
        if f not in lib["vocab"]["features"]:
            raise RuleLibraryError(f"输入引用了未登记的特征 {f}")
    for k in case.get("risks", ()):
        if k not in lib["vocab"]["risks"]:
            raise RuleLibraryError(f"输入引用了未登记的风险 {k}")


def _override_hits(rule: dict, features: set, risks: set) -> list:
    """覆盖强制只让“触发覆盖的那个条件”对应的安全规则适用，不把所有安全规则都拉进来。"""
    hits = []
    for f in rule.get("features", []):
        if f in features and f in OVERRIDE_FEATURES:
            hits.append(f"安全规则覆盖：特征 {f}，D0 也不豁免")
    for k in rule.get("risks", []):
        if k in risks and k in OVERRIDE_RISKS:
            hits.append(f"安全规则覆盖：风险 {k}，D0 也不豁免")
    return hits


def _why(rule: dict, features: set, risks: set, forced: bool):
    """返回适用理由列表；空表示不适用。"""
    if rule.get("always"):
        return ["全部项目"]
    wanted = rule.get("features", [])
    if wanted and rule.get("all_features"):
        if all(f in features for f in wanted):
            return ["同时具备特征 " + "+".join(wanted)]
    hits = []
    if not rule.get("all_features"):
        hits += [f"特征 {f}" for f in wanted if f in features]
    hits += [f"风险 {k}" for k in rule.get("risks", []) if k in risks]
    if not hits and forced and rule["category"] == "security":
        hits += _override_hits(rule, features, risks)
    return hits


def select(lib: dict, case: dict, security_override: bool = False) -> dict:
    """输入 features、risks（集合）、level。输出 applicable（适用，带理由）与 deferred（取决于产物内容、暂无法判定）。结果按 rule_id 排序，同输入同输出。"""
    _check_case(lib, case)
    features, risks = set(case.get("features", ())), set(case.get("risks", ()))
    applicable, deferred = [], []
    for rule in sorted(lib["rules"], key=lambda r: r["rule_id"]):
        if rule.get("content_based"):
            if rule.get("artifacts") and _artifact_in_play(rule, features):
                deferred.append({"rule_id": rule["rule_id"], "reason": "适用性取决于设计产物的内容，当前无法由特征判定"})
            continue
        why = _why(rule, features, risks, security_override)
        if why:
            applicable.append({"rule_id": rule["rule_id"], "severity": rule["severity"], "maturity": rule["maturity"], "why": why})
    return {"applicable": applicable, "deferred": deferred}


def _artifact_in_play(rule: dict, features: set) -> bool:
    """content_based 规则只有在它依赖的产物会被生成时才进入 deferred；A05 数据设计由持久化触发。"""
    triggers = {"A05": {"persistence"}}
    for art in rule.get("artifacts", []):
        if features & triggers.get(art, set()):
            return True
    return False


def coverage(selection: dict, bound_rule_ids) -> dict:
    """覆盖率：分母是全部适用规则，不由生成模型缩小。绑定到不适用或不存在的规则不计入，列入 ignored。分母为零时是 not_applicable，不记 100%。"""
    applicable = [x["rule_id"] for x in selection["applicable"]]
    bound = [rid for rid in dict.fromkeys(bound_rule_ids) if rid in applicable]
    ignored = [rid for rid in dict.fromkeys(bound_rule_ids) if rid not in applicable]
    missing = [rid for rid in applicable if rid not in bound]
    denominator = len(applicable)
    if denominator == 0:
        return {"denominator": 0, "bound": 0, "ratio": None, "status": "not_applicable", "complete": False, "missing": [], "ignored": ignored}
    return {"denominator": denominator, "bound": len(bound), "ratio": len(bound) / denominator, "status": "complete" if not missing else "incomplete", "complete": not missing, "missing": missing, "ignored": ignored}
