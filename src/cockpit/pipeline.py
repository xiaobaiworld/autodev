"""模板定义驱动的阶段、产物契约和输入组装。"""
import json
import re
from pathlib import Path

from cockpit.store import atomic_write

TEMPLATES = Path(__file__).resolve().parents[2] / "templates" / "pipeline"


class SetupError(Exception):
    pass


def load_template(kind):
    path = TEMPLATES / (kind.split("/", 1)[1] + ".json")
    template = json.loads(path.read_text(encoding="utf-8"))
    if template.get("extends"):
        parent = load_template(template["extends"])
        parent["kind"] = template.get("kind")
        parent["order"] = template.get("order", parent["order"])
        parent["scope"] = template.get("scope", parent.get("scope"))
        parent_stages = parent["stages"]
        for name, stage in template.get("stages", {}).items():
            parent_stages[name] = dict(parent_stages.get(name, {}), **stage)
        template = parent
    if (template.get("kind") != kind or not template.get("order")
            or len(template["order"]) != len(set(template["order"]))
            or set(template["order"]) != set(template.get("stages", {}))):
        raise ValueError(f"模板 {path} 的 kind 或阶段表不一致")
    return template


_DEFAULT = load_template("pipeline/design")
STAGES, ORDER = _DEFAULT["stages"], _DEFAULT["order"]


def step_dir(stage, rnd, template=None):
    spec = (template or _DEFAULT)["stages"][stage]
    return f"{spec['dir']}/round-{rnd}"


def validate_done(run_dir, state, template=None):
    """返回 None 表示 done.json 和声明的产物都满足模板契约。"""
    step, run_dir = state["step"], Path(run_dir)
    stage = (template or _DEFAULT)["stages"][state["stage"]]
    folder = run_dir / step["dir"]
    try:
        done = json.loads((folder / "done.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return f"done.json 读不了：{e}"
    if not isinstance(done, dict):
        return "done.json 不是对象"
    for key, want in (("id", state["id"]), ("stage", state["stage"]),
                      ("round", state["round"]), ("role", step["role"])):
        if done.get(key) != want:
            return f"done.json 的 {key} 是 {done.get(key)!r}，应为 {want!r}"
    if done.get("verdict") not in stage["verdicts"]:
        return f"verdict {done.get('verdict')!r} 不在 {stage['verdicts']}"
    if not isinstance(done.get("summary"), str) or not done["summary"].strip():
        return "done.json 缺少非空 summary"
    outputs = done.get("outputs")
    if not isinstance(outputs, list):
        return "outputs 不是列表"
    for need in stage.get("outputs", []):
        if need not in outputs or not (folder / need).is_file():
            return f"缺少产物 {need}"
    for name, title in stage.get("required_sections", {}).items():
        file = folder / name
        if not file.is_file() or not re.search(rf"^#{{1,6}}\s+{re.escape(title)}\s*$", file.read_text(encoding="utf-8"), re.M):
            return f"{name} 缺少“{title}”标题"
    return None


def next_move(state, verdict, limits, template=None):
    """按模板返回 (动作, 阶段, 轮次, 计数器增量)。"""
    template = template or _DEFAULT
    stage, rnd = state["stage"], state["round"]
    spec = template["stages"][stage]
    move = spec.get("on", {}).get(verdict)
    if move is None:
        if verdict == "BLOCK" or (stage == "S1" and verdict == "CLARIFY"):
            return ("needs-human", stage, rnd, {})
        return ("needs-human", stage, rnd, {})
    if isinstance(move, str):
        return (move, stage, rnd, {})
    counter = move.get("counter")
    increments = {counter: 1} if counter else {}
    if counter and state.get("counters", {}).get(counter, 0) + 1 >= limits[counter]:
        return ("limit", stage, rnd, increments)
    new_round = move.get("round", "same")
    if new_round == "same":
        new_round = rnd
    elif new_round == "inc":
        new_round = rnd + 1
    return ("goto", move["goto"], new_round, increments)


def check_vendors(agents, roles):
    """作者与对应审查者的厂商必须不同。"""
    for author, reviewer in (("designer", "design_reviewer"), ("coder", "code_reviewer"),
                             ("coder", "acceptor")):
        if author not in roles or reviewer not in roles:
            continue
        a, b = agents[roles[author]], agents[roles[reviewer]]
        if a.get("vendor") == b.get("vendor"):
            raise SetupError(f"{author} 与 {reviewer} 同为 {a.get('vendor')}，违反 D008")


def _latest_step_dir(run_dir, stage, template):
    base = run_dir / template["stages"][stage]["dir"]
    found = []
    for path in base.glob("round-*"):
        match = re.fullmatch(r"round-(\d+)", path.name)
        if match:
            found.append((int(match.group(1)), path))
    return max(found, default=(0, None))[1]


def _input_path(name, root, run_dir, state, template):
    rid, rnd = state["id"], state["round"]
    count = state.get("counters", {})
    paths = {
        "request": root / "workspace" / "requests" / "active" / f"{rid}.md",
        "analysis": run_dir / step_dir("S1", 1, template) / "analysis.md",
        "design": (_latest_step_dir(run_dir, "S2", template) or run_dir) / "design.md",
        "plan": (_latest_step_dir(run_dir, "S2", template) or run_dir) / "dev-plan.md",
        "review_prev": run_dir / f"S3-design-review/round-{rnd - 1}/review.md",
        "check_prev": run_dir / f"S5-check/round-{count.get('check_rounds', 0)}/check.log",
        "review_code_prev": run_dir / f"S6-code-review/round-{count.get('code_review_rounds', 0)}/review.md",
        "check_now": run_dir / f"S5-check/round-{count.get('check_rounds', 0) + 1}/check.log",
        "usage_now": run_dir / f"S7U-usage/round-{count.get('usage_rounds', 0) + 1}/usage.log",
        "human": run_dir / "human.md",
        "full_diff": run_dir / "full.patch",
    }
    if name == "workdir":
        return Path(state["workdir"])
    if name == "workdir_ro":
        return Path(state["workdir"])
    return paths.get(name)


def write_input(root, run_dir, state, template=None):
    """按模板的 inputs 列表生成 Agent 本轮唯一的文件清单。"""
    root, run_dir = Path(root), Path(run_dir)
    template = template or _DEFAULT
    stage_name, step = state["stage"], state["step"]
    spec = template["stages"][stage_name]
    out = run_dir / step["dir"]
    lines = []
    for name in spec.get("inputs", ["request"]):
        path = _input_path(name, root, run_dir, state, template)
        if path is not None and path.exists():
            extra = "（只读）" if name == "workdir_ro" else ""
            lines.append(f"- {name}：{path}{extra}")
    if not spec.get("inputs"):
        lines.append(f"- request：{_input_path('request', root, run_dir, state, template)}")
    body = (
        f"---\nschema_version: 1\nid: {state['id']}\nstage: {stage_name}\nround: {state['round']}\n"
        f"role: {step['role']}\noutput_dir: {out}\nrequired_outputs: {spec.get('outputs', []) + ['done.json']}\n---\n\n"
    )
    if template.get("scope"):
        body += f"## 范围\n{template['scope']}\n\n"
    body += (f"## 任务\n{spec.get('task', '')}\n\n## 输入文件\n" + "\n".join(lines) +
             f"\n\n## 输出要求\n产物与 done.json 都写到 {out}。一律用文件读写工具，不要用 shell 命令写文件。"
             f"最后写 done.json，内容为 JSON 对象，字段：id={state['id']}，stage={stage_name}，"
             f"round={state['round']}，role={step['role']}，summary=简短结论，outputs=产物文件名列表，"
             f"verdict 取 {spec['verdicts']} 之一，且与产物 frontmatter 的 verdict 一致。\n\n"
             "## 必须停止并写 BLOCK 的情况\n删除数据、修改密钥或凭证、修改账号权限、对外发送消息、花钱、改变产品方向。")
    atomic_write(out / "input.md", body)
    return out / "input.md"
