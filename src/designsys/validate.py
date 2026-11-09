"""设计包验证（V2.1 第 7、9、15 节）：V1 文件与 Schema、V2 引用与规则覆盖、V3 跨产物一致性。程序检查，输出统一契约；error 不得当作通过。"""
from __future__ import annotations

import json
from pathlib import Path

from designsys import classify, rules as rl, schema

SCHEMAS = Path(__file__).resolve().parents[2] / "design-system" / "schemas"
VALIDATOR_VERSION = "0.1.0"
# 产物 ID -> (文件，Schema 名)；只登记 MVP 1 已有 Schema 的产物
FILES = {
    "A01": ("plan.json", "plan"),
    "A04": ("artifacts/technical.json", "technical"),
    "A05": ("artifacts/data.json", "data"),
    "A07": ("artifacts/security.json", "security"),
    "A08": ("handoff.json", "handoff"),
}
ALWAYS = ("A01", "A07", "A08")


def result(check, status, rule_id, artifact, location, message, severity="blocking", evidence=None, hint=""):
    return {"validator_id": check, "validator_version": VALIDATOR_VERSION, "rule_id": rule_id, "rule_version": "1.0.0", "artifact": artifact, "status": status, "severity": severity, "location": location, "message": message, "evidence": evidence or dict(), "repair_hint": hint}


class Pack:
    """读取设计包目录；解析失败的文件记在 errors 里，不抛异常。"""

    def __init__(self, root):
        self.root = Path(root)
        self.docs = dict()
        self.parse_errors = dict()
        self.missing = []

    def load(self, artifact_id):
        rel = FILES[artifact_id][0]
        path = self.root / rel
        if not path.is_file():
            self.missing.append(artifact_id)
            return None
        try:
            self.docs[artifact_id] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            self.parse_errors[artifact_id] = str(e)
            return None
        return self.docs[artifact_id]


def required(pack: Pack) -> list:
    """必需产物 = 恒定产物 + 计划里列出且本验证器认识的产物。计划读不出来时只能要求恒定产物。"""
    plan = pack.docs.get("A01")
    ids = list(ALWAYS)
    if isinstance(plan, dict):
        for a in plan.get("required_artifacts", []):
            if a in FILES and a not in ids:
                ids.append(a)
    return ids


def check_v1(pack: Pack, ctx: dict) -> list:
    out = []
    pack.load("A01")
    for aid in required(pack):
        file_rel, name = FILES[aid]
        doc = pack.load(aid) if aid not in pack.docs else pack.docs[aid]
        if aid in pack.missing:
            out.append(result("check_v1_files", "failed", "V1-FILE", file_rel, aid, f"必需产物 {aid} 的文件 {file_rel} 不存在", evidence=dict(artifact_id=aid), hint="生成该产物"))
            continue
        if aid in pack.parse_errors:
            out.append(result("check_v1_parse", "failed", "V1-PARSE", file_rel, aid, f"{file_rel} 无法解析：{pack.parse_errors[aid]}", hint="修正 JSON 语法"))
            continue
        sch = json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))
        errs = schema.validate(doc, sch)
        if not errs:
            out.append(result("check_v1_schema", "passed", "V1-SCHEMA", file_rel, aid, "Schema 合法"))
        for e in errs:
            out.append(result("check_v1_schema", "failed", "V1-SCHEMA", file_rel, e["path"], e["message"], evidence=dict(artifact_id=aid), hint="按 Schema 补全或修正字段"))
    return out


def _tasks(pack: Pack) -> list:
    h = pack.docs.get("A08")
    return h.get("tasks", []) if isinstance(h, dict) else []


def _case(pack: Pack) -> dict:
    """由计划里的特征、风险和设计等级还原规则选择器的输入。"""
    plan = pack.docs.get("A01") or dict()
    return {"features": set(plan.get("features", [])), "risks": set(plan.get("risks", [])), "level": plan.get("design_level", "D1")}


def _selection(pack: Pack, ctx: dict) -> dict:
    case = _case(pack)
    override = classify_override(ctx["classification"], case)
    return rl.select(ctx["library"], case, security_override=override)


def classify_override(rules: dict, case: dict) -> bool:
    """覆盖强制由分类规则决定：命中认证、敏感数据、跨租户或高影响操作。"""
    so = rules["security_override"]
    if any(f in case["features"] for f in so.get("any_features", [])):
        return True
    return any(r in case["risks"] for r in so.get("any_risks", []))


def check_v2_refs(pack: Pack, ctx: dict) -> list:
    out = []
    tasks = _tasks(pack)
    ids = [t["task_id"] for t in tasks]
    seen = set()
    for tid in ids:
        if tid in seen:
            out.append(result("check_v2_refs", "failed", "V2-REF", "handoff.json", tid, f"任务编号 {tid} 重复"))
        seen.add(tid)
    known_rules = {r["rule_id"] for r in ctx["library"]["rules"]}
    for t in tasks:
        for ref in t.get("design_refs", []):
            if not (pack.root / ref).exists():
                out.append(result("check_v2_refs", "failed", "V2-REF", "handoff.json", t["task_id"], f"任务 {t['task_id']} 引用的设计文件 {ref} 不存在", evidence=dict(ref=ref)))
        for dep in t.get("dependencies", []):
            if dep not in ids:
                out.append(result("check_v2_refs", "failed", "V2-REF", "handoff.json", t["task_id"], f"任务 {t['task_id']} 依赖不存在的任务 {dep}", evidence=dict(ref=dep)))
        for rid in t.get("mandatory_rule_ids", []):
            if rid not in known_rules:
                out.append(result("check_v2_refs", "failed", "V2-REF", "handoff.json", t["task_id"], f"任务 {t['task_id']} 引用的规则 {rid} 不在规则库中", evidence=dict(ref=rid)))
    sec = pack.docs.get("A07") or dict()
    for rule in sec.get("applicable_rules", []):
        for tid in rule.get("implementation_tasks", []):
            if tid not in ids:
                out.append(result("check_v2_refs", "failed", "V2-REF", "artifacts/security.json", rule["rule_id"], f"安全规则 {rule['rule_id']} 指向不存在的任务 {tid}", evidence=dict(ref=tid)))
    if not any(r["status"] == "failed" for r in out):
        out.append(result("check_v2_refs", "passed", "V2-REF", "handoff.json", "tasks", "引用均可解析"))
    return out


def check_v2_rules(pack: Pack, ctx: dict) -> list:
    """计划里的强制规则必须与规则选择器算出的适用规则完全一致：不能少（缩小分母），也不能多。"""
    plan = pack.docs.get("A01")
    if not isinstance(plan, dict):
        return []
    want = {x["rule_id"] for x in _selection(pack, ctx)["applicable"]}
    got = set(plan.get("mandatory_rules", []))
    out = []
    for rid in sorted(want - got):
        out.append(result("check_v2_rules", "failed", "V2-RULES", "plan.json", "mandatory_rules", f"适用规则 {rid} 没有列入计划（不能由生成模型缩小分母）", evidence=dict(rule=rid), hint="按规则选择器补回"))
    for rid in sorted(got - want):
        out.append(result("check_v2_rules", "failed", "V2-RULES", "plan.json", "mandatory_rules", f"计划列入的规则 {rid} 按当前特征与风险并不适用", evidence=dict(rule=rid), hint="去掉或修正特征"))
    if not out:
        out.append(result("check_v2_rules", "passed", "V2-RULES", "plan.json", "mandatory_rules", "计划的强制规则与规则选择器一致"))
    return out


def check_v2_security(pack: Pack, ctx: dict) -> list:
    """security.json 必须逐条交代每一条适用规则：落实，或说明不适用的理由。"""
    sec = pack.docs.get("A07")
    if not isinstance(sec, dict):
        return []
    want = {x["rule_id"] for x in _selection(pack, ctx)["applicable"]}
    done = {r["rule_id"] for r in sec.get("applicable_rules", [])}
    out = []
    for n in sec.get("not_applicable", []):
        if not str(n.get("reason", "")).strip():
            out.append(result("check_v2_security", "failed", "V2-SECURITY", "artifacts/security.json", n["rule_id"], f"规则 {n['rule_id']} 标为不适用却没有理由", hint="补写适用性判定依据"))
        done.add(n["rule_id"])
    for rid in sorted(want - done):
        out.append(result("check_v2_security", "failed", "V2-SECURITY", "artifacts/security.json", rid, f"适用规则 {rid} 既未落实也未说明不适用", evidence=dict(rule=rid)))
    if not out:
        out.append(result("check_v2_security", "passed", "V2-SECURITY", "artifacts/security.json", "applicable_rules", "每条适用规则都有交代"))
    return out


def _bound_rules(pack: Pack) -> list:
    bound = []
    for t in _tasks(pack):
        bound += t.get("mandatory_rule_ids", [])
    return bound


def check_v2_coverage(pack: Pack, ctx: dict) -> list:
    """强制规则落实率：分母是全部适用规则；没有绑定到任何开发任务的规则判失败。"""
    if not isinstance(pack.docs.get("A08"), dict):
        return []
    cov = rl.coverage(_selection(pack, ctx), _bound_rules(pack))
    ctx["coverage"] = cov
    if cov["status"] == "not_applicable":
        return [result("check_v2_coverage", "not_applicable", "V2-COVERAGE", "handoff.json", "mandatory_rule_ids", "没有适用规则，覆盖率分母为零，不记为 100%")]
    if cov["complete"]:
        return [result("check_v2_coverage", "passed", "V2-COVERAGE", "handoff.json", "mandatory_rule_ids", f"{cov['bound']}/{cov['denominator']} 条适用规则已绑定到开发任务")]
    return [result("check_v2_coverage", "failed", "V2-COVERAGE", "handoff.json", "mandatory_rule_ids", f"{len(cov['missing'])} 条适用规则没有绑定到任何开发任务", evidence=dict(missing=cov["missing"]), hint="把这些规则绑到对应任务和验收用例")]


OWNER_FIELDS = ("project_id", "tenant_id", "workspace_id", "org_id", "owner_id")


def check_v3_isolation(pack: Pack, ctx: dict) -> list:
    """V2.1 第 7.3 节：SEC-005 适用时，受隔离的实体要有明确的归属字段，且规则绑定到开发任务。"""
    want = {x["rule_id"] for x in _selection(pack, ctx)["applicable"]}
    if "SEC-005" not in want:
        return [result("check_v3_isolation", "not_applicable", "V3-ISOLATION", "artifacts/data.json", "entities", "SEC-005 不适用：计划里没有跨项目或跨租户风险")]
    data = pack.docs.get("A05")
    if not isinstance(data, dict):
        return [result("check_v3_isolation", "failed", "V3-ISOLATION", "artifacts/data.json", "entities", "SEC-005 适用，但没有数据设计可供核对隔离", hint="补充数据设计并标明实体的项目归属")]
    out = []
    for ent in data.get("entities", []):
        names = [f["name"] for f in ent.get("fields", [])]
        if not any(n in OWNER_FIELDS for n in names):
            out.append(result("check_v3_isolation", "failed", "V3-ISOLATION", "artifacts/data.json", f"entities.{ent['id']}", f"实体 {ent['id']} 没有项目归属字段（{'、'.join(OWNER_FIELDS)} 之一）", evidence=dict(entity_id=ent["id"]), hint="增加归属字段；若用其他等效隔离机制，需在设计里写明并由人确认，本检查无法自动判断等效机制"))
    if not out:
        out.append(result("check_v3_isolation", "passed", "V3-ISOLATION", "artifacts/data.json", "entities", "每个实体都有归属字段（等效隔离机制不在自动检查范围）"))
    return out


# 校验器清单：顺序即执行顺序。测试会替换最后一项来模拟校验器自己出错。
CHECKS = [
    ("check_v1", check_v1),
    ("check_v2_refs", check_v2_refs),
    ("check_v2_rules", check_v2_rules),
    ("check_v2_security", check_v2_security),
    ("check_v2_coverage", check_v2_coverage),
    ("check_v3_isolation", check_v3_isolation),
]


def _run(check_id: str, fn, pack: Pack, ctx: dict) -> list:
    """校验器自己抛异常时记为 error，绝不当作通过（V2.1 第 15.1 节）。"""
    try:
        return fn(pack, ctx)
    except Exception as e:
        return [result(check_id, "error", "VALIDATOR-ERROR", "", check_id, f"校验器 {check_id} 执行失败：{e}", hint="修复校验器，在此之前不得验收")]


def _ratio(num: int, den: int) -> dict:
    if den == 0:
        return {"denominator": 0, "passed": 0, "ratio": None, "status": "not_applicable"}
    return {"denominator": den, "passed": num, "ratio": num / den, "status": "complete" if num == den else "incomplete"}


def _metrics(pack: Pack, results: list, ctx: dict) -> dict:
    req = required(pack)
    ok = [a for a in req if a not in pack.missing and a not in pack.parse_errors and not _schema_failed(results, a)]
    refs = [r for r in results if r["validator_id"] in ("check_v2_refs", "check_v1_schema") and r["status"] in ("passed", "failed")]
    return {
        "required_artifacts": _ratio(len(ok), len(req)),
        "structure_and_references": _ratio(sum(1 for r in refs if r["status"] == "passed"), len(refs)),
        "mandatory_rule_coverage": ctx.get("coverage") or _ratio(0, 0),
        "core_interactions": _ratio(0, 0),
        "checks_total": len(results),
        "checks_passed": sum(1 for r in results if r["status"] == "passed"),
        "checks_failed": sum(1 for r in results if r["status"] == "failed"),
        "checks_error": sum(1 for r in results if r["status"] == "error"),
    }


def _schema_failed(results: list, artifact_id: str) -> bool:
    for r in results:
        if r["status"] == "failed" and r["evidence"].get("artifact_id") == artifact_id:
            return True
    return False


def validate_pack(root, library=None, classification=None) -> dict:
    """对一个设计包目录做 V1–V3 检查。ready_for_coding 由本函数按结果计算，不采信设计包自己声称的值。"""
    pack = Pack(root)
    ctx = dict(library=library or rl.load_library(), classification=classification or classify.load_rules())
    results = []
    for check_id, fn in CHECKS:
        results += _run(check_id, fn, pack, ctx)
    blocking = [f"{r['rule_id']} {r['location']}: {r['message']}" for r in results if r["status"] in ("failed", "error") and r["severity"] == "blocking"]
    declared = (pack.docs.get("A08") or dict()).get("blocking_issues", [])
    blocking += [str(x) for x in declared]
    plan = pack.docs.get("A01") or dict()
    return {
        "ready_for_coding": not blocking and not any(r["status"] == "error" for r in results),
        "blocking": blocking,
        "open_questions": list(plan.get("open_questions", [])),
        "results": results,
        "metrics": _metrics(pack, results, ctx),
    }
