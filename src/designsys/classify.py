"""设计等级判定（V2.1 第 3 节）：由程序按功能特征与风险计算 D0–D3，模型只给建议，不由设计作者自称。"""
from __future__ import annotations

import tomllib
from pathlib import Path

RULES = Path(__file__).resolve().parents[2] / "design-system" / "rules" / "classification.toml"
ORDER = ("D3", "D2", "D1")


class ClassifyError(ValueError):
    """规则文件或输入不合法；消息直接给人看。"""


def _known(rules: dict, section: str, names, where: str) -> None:
    for name in names:
        if name not in rules[section]:
            raise ClassifyError(f"{where} 引用了未登记的 {section[:-1]} {name}")


def load_rules(path=RULES) -> dict:
    rules = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("features", "risks", "levels", "security_override"):
        if key not in rules:
            raise ClassifyError(f"规则文件缺少 [{key}]")
    for level in ORDER:
        if level not in rules["levels"]:
            raise ClassifyError(f"规则文件缺少 {level} 的定义")
    for level, spec in rules["levels"].items():
        _known(rules, "features", spec.get("any_features", []), level)
        _known(rules, "risks", spec.get("any_risks", []), level)
        for group in spec.get("all_features", []):
            _known(rules, "features", group, level)
    so = rules["security_override"]
    _known(rules, "features", so.get("any_features", []), "security_override")
    _known(rules, "risks", so.get("any_risks", []), "security_override")
    return rules


def _check_input(rules: dict, case: dict) -> None:
    for key in ("requirements_clear", "multi_module"):
        if not isinstance(case.get(key), bool):
            raise ClassifyError(f"{key} 必须是 true 或 false，收到 {case.get(key)!r}")
    _known(rules, "features", case.get("features", ()), "输入")
    _known(rules, "risks", case.get("risks", ()), "输入")


def _hits(spec: dict, features: set, risks: set, multi_module: bool):
    """返回满足的条件说明列表；空表示这一档不满足。"""
    why = []
    for f in spec.get("any_features", []):
        if f in features:
            why.append(f"特征 {f}")
    for r in spec.get("any_risks", []):
        if r in risks:
            why.append(f"风险 {r}")
    for group in spec.get("all_features", []):
        if all(f in features for f in group):
            why.append("同时具备 " + "+".join(group))
    if spec.get("multi_module") and multi_module:
        why.append("多模块")
    return why


def classify(rules: dict, case: dict) -> dict:
    """输入：features、risks（集合）、requirements_clear、multi_module。输出：level、reasons、security_override。取满足条件的最高一档。"""
    _check_input(rules, case)
    features, risks = set(case.get("features", ())), set(case.get("risks", ()))
    level, reasons = "D0", []
    for name in ORDER:
        spec = rules["levels"][name]
        why = _hits(spec, features, risks, case["multi_module"])
        if name == "D1" and not case["requirements_clear"]:
            why.append("需求不明确，不能跳过设计")
        if why:
            level, reasons = name, why
            break
    if level == "D0":
        reasons = ["无功能特征与风险，需求明确：跳过独立设计，仍执行基础工程规则"]
    so = rules["security_override"]
    override = any(f in features for f in so.get("any_features", []))
    if any(r in risks for r in so.get("any_risks", [])):
        override = True
    return {"level": level, "reasons": reasons, "security_override": override}
