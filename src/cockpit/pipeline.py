"""S1 到 S3 的阶段表、done.json 校验、结论到下一步的规则（DATA_SPEC 7.2、7.3，设计 5.3）。
纯函数，不碰文件系统以外的东西；S4 以后属于下一份计划。
"""
import json
from pathlib import Path

from cockpit.store import atomic_write

TEMPLATES = Path(__file__).resolve().parents[2] / "templates" / "pipeline"


def load_template(kind):
    """kind 如 pipeline/design，对应 templates/pipeline/design.json：阶段表、角色、产物、结论、任务说明都在那里，改那一处即可。"""
    path = TEMPLATES / (kind.split("/", 1)[1] + ".json")
    t = json.loads(path.read_text(encoding="utf-8"))
    if t.get("kind") != kind or not t.get("order") or set(t["order"]) != set(t["stages"]):
        raise ValueError(f"模板 {path} 的 kind 或阶段表不一致")
    return t


_DEFAULT = load_template("pipeline/design")
STAGES, ORDER = _DEFAULT["stages"], _DEFAULT["order"]  # 现只有一个模板；多模板时按 state["kind"] 取


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
    if not isinstance(d.get("summary"), str) or not d["summary"].strip():
        return "done.json 缺少 summary（一两句话：做了什么、为什么这么做）"
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


class SetupError(Exception):
    pass


def check_vendors(agents, roles):
    """D008：设计作者与设计审查者的模型厂商必须不同。"""
    a, b = agents[roles["designer"]], agents[roles["design_reviewer"]]
    if a.get("vendor") == b.get("vendor"):
        raise SetupError(f"designer 与 design_reviewer 同为 {a.get('vendor')}，违反 D008")


def write_input(root, run_dir, state):
    """写本步骤的 input.md（DATA_SPEC 7.1）。返回路径。root 是 AutoDev 根目录。"""
    root, run_dir = Path(root), Path(run_dir)
    st, step = state["stage"], state["step"]
    spec = STAGES[st]
    rid, rnd = state["id"], state["round"]
    req = root / "workspace" / "requests" / "active" / f"{rid}.md"
    files = [f"- 需求：{req}"]
    if st in ("S2", "S3"):
        files.append(f"- 分析：{run_dir / step_dir('S1', 1) / 'analysis.md'}")
    if st == "S3":
        d = run_dir / step_dir("S2", rnd)
        files += [f"- 设计稿：{d / 'design.md'}", f"- 开发计划：{d / 'dev-plan.md'}"]
    if st == "S2" and rnd > 1:
        files.append(f"- 上轮审查意见：{run_dir / step_dir('S3', rnd - 1) / 'review.md'}（逐条回应，写 response.md）")
    out = run_dir / step["dir"]
    body = (
        f"---\nschema_version: 1\nid: {rid}\nstage: {st}\nround: {rnd}\nrole: {step['role']}\n"
        f"output_dir: {out}\nrequired_outputs: {spec['outputs'] + ['done.json']}\n---\n\n"
        f"## 任务\n{spec['task']}\n\n## 输入文件\n" + "\n".join(files) + "\n\n"
        f"## 输出要求\n产物与 done.json 都写到 {out}，一律用文件写入工具，不要用 shell 命令写文件。"
        f"最后写 done.json，内容为 JSON 对象，字段：\n"
        f'id="{rid}"，stage="{st}"，round={rnd}，role="{step["role"]}"，'
        f"summary=一两句话写清做了什么、为什么这么做（不能为空），"
        f"outputs=产物文件名列表（须包含 {spec['outputs']}），"
        f"verdict 取 {spec['verdicts']} 之一，且与产物 frontmatter 的 verdict 一致，finished_at 为 ISO 时间。\n\n"
        "## 必须停止并写 BLOCK 的情况\n删除数据、修改密钥或凭证、修改权限、对外发送消息、花钱、改变产品方向。"
    )
    atomic_write(out / "input.md", body)
    return out / "input.md"
