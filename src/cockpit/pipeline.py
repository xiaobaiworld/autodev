"""阶段表、done.json 校验、结论到下一步的规则（DATA_SPEC 7.2、7.3，设计 5.3）。
阶段表和转移都写在 templates/pipeline/<类型>.json 里；这里的函数按 state["kind"] 取模板，不写死阶段名。
"""
import json
from pathlib import Path

from cockpit.kinds import DEFAULT_KIND, KINDS
from cockpit.store import atomic_write
from cockpit.tools import TOOLS

TEMPLATES = Path(__file__).resolve().parents[2] / "templates" / "pipeline"
TERMINAL = {"done", "rejected", "needs-human"}  # 结论去向写成这三个字符串之一，或写成 {"goto": 阶段, "round": ..., "counter": ...}


def _check_transitions(t, path):
    stages = t["stages"]
    for name, spec in stages.items():
        on = spec.get("on")
        if not isinstance(on, dict):
            raise ValueError(f"模板 {path} 阶段 {name} 缺少 on（结论到哪去）")
        for v in spec["verdicts"]:
            if v != "BLOCK" and v not in on:  # BLOCK 一律转人工，由程序处理，不用写
                raise ValueError(f"模板 {path} 阶段 {name} 的结论 {v} 没有写去哪")
        if spec.get("workdir") not in (None, "write", "use", "readonly"):
            raise ValueError(f"模板 {path} 阶段 {name} 的 workdir 只能是 write / use / readonly，写的是 {spec.get('workdir')!r}")
        if "readonly" == spec.get("workdir") and spec.get("runner") == "tool":
            raise ValueError(f"模板 {path} 阶段 {name}：只读模式是给 Agent 审查用的，程序步骤用 use")
        if spec.get("runner") == "tool":
            if spec.get("tool") not in TOOLS:
                raise ValueError(f"模板 {path} 阶段 {name} 用了没有注册的工具 {spec.get('tool')!r}：{sorted(TOOLS)}")
            if spec["tool"] == "check" and not spec.get("command"):
                raise ValueError(f"模板 {path} 阶段 {name} 的 check 工具缺少 command")
        for v, act in on.items():
            if v not in spec["verdicts"]:
                raise ValueError(f"模板 {path} 阶段 {name} 的 on 里有不允许的结论 {v}")
            if isinstance(act, str):
                ok = act in TERMINAL
            else:
                r = act.get("round")
                ok = act.get("goto") in stages and (isinstance(r, int) or r in ("same", "inc"))
            if not ok:
                raise ValueError(f"模板 {path} 阶段 {name} 结论 {v} 的去向不合法：{act!r}")


def load_template(kind):
    """kind 如 pipeline/design，对应 templates/pipeline/design.json。
    模板可以 "extends" 另一个模板：阶段按名字逐项覆盖（每项内按字段覆盖），order、scope 等顶层字段覆盖基础模板。"""
    path = TEMPLATES / (kind.split("/", 1)[1] + ".json")
    t = json.loads(path.read_text(encoding="utf-8"))
    if "extends" in t:
        base = load_template(t["extends"])
        stages = {k: dict(v) for k, v in base["stages"].items()}
        for k, v in t.get("stages", {}).items():
            stages[k] = {**stages.get(k, {}), **v}
        t = {**base, **{k: v for k, v in t.items() if k not in ("extends", "stages")}, "stages": stages}
    if t.get("kind") != kind or not t.get("order") or set(t["order"]) != set(t["stages"]):
        raise ValueError(f"模板 {path} 的 kind 或阶段表不一致")
    _check_transitions(t, path)
    return t


def _kind(state):
    return state.get("kind") or DEFAULT_KIND  # 老记录没有 kind，按默认类型处理


def template_for(state):
    return load_template(_kind(state))


def counters_for(kind):
    """模板里所有回退用到的计数器，初始为 0。"""
    return {a["counter"]: 0 for s in load_template(kind)["stages"].values()
            for a in s["on"].values() if isinstance(a, dict) and a.get("counter")}


def stage_roles():
    """所有流水线模板里 阶段 -> 角色。规则按阶段路由、不按类型，所以同一阶段在不同模板里角色必须一致。"""
    out = {}
    for kind in sorted(KINDS):
        if kind.startswith("pipeline/"):
            for st, spec in load_template(kind)["stages"].items():
                if spec.get("runner") == "tool":
                    continue  # 程序步骤没有 Agent，不生成派活规则
                if out.setdefault(st, spec["role"]) != spec["role"]:
                    raise ValueError(f"阶段 {st} 在不同模板里角色不一致：{out[st]} 与 {spec['role']}")
    return dict(sorted(out.items()))


_DEFAULT = load_template(DEFAULT_KIND)
STAGES, ORDER, SCOPE = _DEFAULT["stages"], _DEFAULT["order"], _DEFAULT.get("scope", "")  # 默认类型的快照，给只关心它的调用方


def step_dir(stage, rnd, kind=DEFAULT_KIND):
    return f"{load_template(kind)['stages'][stage]['dir']}/round-{rnd}"


def validate_done(run_dir, state):
    """返回 None 表示通过，否则返回原因字符串（记为 invalid_output）。"""
    step = state["step"]
    run_dir = Path(run_dir)
    stage = template_for(state)["stages"][state["stage"]]
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
    """返回 (动作, 新阶段, 新轮次, 计数器增量)。动作：goto / done / rejected / needs-human / limit。去向全部来自模板。"""
    stage, rnd = state["stage"], state["round"]
    if verdict == "BLOCK":
        return ("needs-human", stage, rnd, {})
    act = template_for(state)["stages"][stage]["on"][verdict]
    if isinstance(act, str):
        return (act, stage, rnd, {})
    r = act["round"]
    new_rnd = r if isinstance(r, int) else (rnd if r == "same" else rnd + 1)
    c = act.get("counter")
    if c and state["counters"].get(c, 0) + 1 >= limits[c]:
        return ("limit", stage, rnd, {c: 1})
    return ("goto", act["goto"], new_rnd, {c: 1} if c else {})


class SetupError(Exception):
    pass


PAIRS = (("designer", "design_reviewer"), ("coder", "code_reviewer"))  # （作者，审查者）


def check_vendors(agents, roles):
    """D008：每一对作者与审查者的模型厂商必须不同。只检查 config 里两个角色都配了的对。"""
    for author, reviewer in PAIRS:
        if author not in roles or reviewer not in roles:
            continue
        a, b = agents[roles[author]], agents[roles[reviewer]]
        if a.get("vendor") == b.get("vendor"):
            raise SetupError(f"{author} 与 {reviewer} 同为 {a.get('vendor')}，违反 D008")


def _latest_round(run_dir, stage, kind):
    d = Path(run_dir) / load_template(kind)["stages"][stage]["dir"]
    nums = [int(p.name[6:]) for p in d.glob("round-*") if p.name[6:].isdigit()]
    return max(nums) if nums else None


def _verdict_of(step_dir_path):
    """读某个步骤目录里 done.json 的结论；读不到返回 None。"""
    try:
        return json.loads((Path(step_dir_path) / "done.json").read_text(encoding="utf-8")).get("verdict")
    except (OSError, ValueError):
        return None


def workdir_of(root, state):
    """编码阶段改代码的目录，放在 workspace 里（Agent 的沙箱只让写这里）。"""
    return Path(root) / "workspace" / "projects" / state.get("project", "toy") / state["id"]


def write_input(root, run_dir, state):
    """写本步骤的 input.md（DATA_SPEC 7.1）。返回路径。root 是 AutoDev 根目录。"""
    root, run_dir = Path(root), Path(run_dir)
    st, step, kind = state["stage"], state["step"], _kind(state)
    tpl = load_template(kind)
    spec = tpl["stages"][st]
    scope = tpl.get("scope", "")
    rid, rnd = state["id"], state["round"]
    at = lambda stg, r: run_dir / step_dir(stg, r, kind)
    latest = lambda stg: _latest_round(run_dir, stg, kind) or 1
    # 模板里 inputs 写这一步要读哪些文件（名字 -> (说明, 路径函数)），只算这一步用到的，模板没有的阶段不会被碰到；没有的名字报错，不静默漏掉
    paths = {
        "request": ("需求", lambda: root / "workspace" / "requests" / "active" / f"{rid}.md"),
        "analysis": ("分析", lambda: at("S1", 1) / "analysis.md"),
        "design": ("设计稿", lambda: at("S2", latest("S2")) / "design.md"),
        "plan": ("开发计划", lambda: at("S2", latest("S2")) / "dev-plan.md"),
        "review_prev": ("上轮审查意见（逐条回应，写 response.md）", lambda: at("S3", rnd - 1) / "review.md"),
        "workdir": ("代码目录（只改这里的文件，不要执行 git 命令）", lambda: workdir_of(root, state)),
        "check_prev": ("上轮检查结果（由程序运行测试得到，先读它，在已有代码上修复，不要推倒重来）",
                       lambda: at("S5", rnd - 1) / "check.log"),
        "review_code_prev": ("上轮代码审查意见（逐条处理，在已有代码上改，不要推倒重来）",
                             lambda: at("S6", rnd - 1) / "review.md"),
        "workdir_ro": ("代码目录（只读：不要修改里面任何文件，也不要执行 git 命令）", lambda: workdir_of(root, state)),
        "full_diff": ("完整改动（从起点到现在，程序生成）", lambda: run_dir / step["dir"] / "full.patch"),
        "check_now": ("本轮检查结果（程序运行测试得到）", lambda: at("S5", rnd) / "check.log"),
    }
    files = []
    replies = sorted((run_dir / "human").glob("reply-*.md")) if (run_dir / "human").exists() else []
    for name in spec.get("inputs", ["request"]):
        if name == "review_prev" and rnd <= 1:
            continue  # 第 1 轮没有上轮意见
        if name == "human":
            files += [f"- 用户决定（优先于需求原文，必须遵守）：{p}" for p in replies]  # 没有回复就不列
            continue
        if name not in paths:
            raise ValueError(f"模板阶段 {st} 的 inputs 里有未知名字 {name!r}")
        label, make = paths[name]
        p = make()
        if name in ("check_prev", "review_code_prev") and not p.is_file():
            continue  # 不是从那一步退回来的（第 1 轮，或人工处理后继续），就没有这份文件
        if name == "check_prev" and _verdict_of(p.parent) != "FAIL":
            continue  # 上一轮检查是通过的（这一轮是代码审查打回来的），不能把通过的结果当成"没通过"塞给编码者
        files.append(f"- {label}：{p}")
    out = run_dir / step["dir"]
    body = (
        f"---\nschema_version: 1\nid: {rid}\nstage: {st}\nround: {rnd}\nrole: {step['role']}\n"
        f"output_dir: {out}\nrequired_outputs: {spec['outputs'] + ['done.json']}\n---\n\n"
        f"## 任务\n{spec['task']}\n\n## 输入文件\n" + "\n".join(files) + "\n\n"
        + (f"## 范围\n{scope}\n\n" if scope else "")
        + f"## 输出要求\n产物与 done.json 都写到 {out}，一律用文件写入工具，不要用 shell 命令写文件。"
        f"最后写 done.json，内容为 JSON 对象，字段：\n"
        f'id="{rid}"，stage="{st}"，round={rnd}，role="{step["role"]}"，'
        f"summary=一两句话写清做了什么、为什么这么做（不能为空），"
        f"outputs=产物文件名列表（须包含 {spec['outputs']}），"
        f"verdict 取 {spec['verdicts']} 之一，且与产物 frontmatter 的 verdict 一致，finished_at 为 ISO 时间。\n\n"
        "## 必须停止并写 BLOCK 的情况\n删除数据、修改密钥或凭证、修改权限、对外发送消息、花钱、改变产品方向。"
    )
    atomic_write(out / "input.md", body)
    return out / "input.md"
    req = root / "workspace" / "requests" / "active" / f"{rid}.md"
    files = [f"- 需求：{req}"]
    if st in ("S2", "S3", "S4"):
        files.append(f"- 分析：{at('S1', 1) / 'analysis.md'}")
    if st == "S3":
        files += [f"- 设计稿：{at('S2', rnd) / 'design.md'}", f"- 开发计划：{at('S2', rnd) / 'dev-plan.md'}"]
    if st == "S4":
        r = _latest_round(run_dir, "S2", kind)  # 通过审查的那一轮设计
        files += [f"- 设计稿：{at('S2', r) / 'design.md'}", f"- 开发计划：{at('S2', r) / 'dev-plan.md'}",
                  f"- 工作目录（只改这里的文件，不要提交 git）：{workdir_of(root, state)}"]
    if st == "S2" and rnd > 1:
        files.append(f"- 上轮审查意见：{at('S3', rnd - 1) / 'review.md'}（逐条回应，写 response.md）")
    out = run_dir / step["dir"]
    body = (
        f"---\nschema_version: 1\nid: {rid}\nstage: {st}\nround: {rnd}\nrole: {step['role']}\n"
        f"output_dir: {out}\nrequired_outputs: {spec['outputs'] + ['done.json']}\n---\n\n"
        f"## 任务\n{spec['task']}\n\n## 输入文件\n" + "\n".join(files) + "\n\n"
        + (f"## 范围\n{scope}\n\n" if scope else "")
        + f"## 输出要求\n产物与 done.json 都写到 {out}，一律用文件写入工具，不要用 shell 命令写文件。"
        f"最后写 done.json，内容为 JSON 对象，字段：\n"
        f'id="{rid}"，stage="{st}"，round={rnd}，role="{step["role"]}"，'
        f"summary=一两句话写清做了什么、为什么这么做（不能为空），"
        f"outputs=产物文件名列表（须包含 {spec['outputs']}），"
        f"verdict 取 {spec['verdicts']} 之一，且与产物 frontmatter 的 verdict 一致，finished_at 为 ISO 时间。\n\n"
        "## 必须停止并写 BLOCK 的情况\n删除数据、修改密钥或凭证、修改权限、对外发送消息、花钱、改变产品方向。"
    )
    atomic_write(out / "input.md", body)
    return out / "input.md"
