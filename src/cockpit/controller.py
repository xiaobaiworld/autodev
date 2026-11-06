"""最小主循环（P4）：每次 advance 只推进一步并立即落盘，重启后从 state.json 继续（设计 5.3、5.4）。
invoke_fn 必须传入（正式用 driver.runner.make_invoke，测试用假的）。阶段和转移来自 state["kind"] 对应的模板。
"""
import json
import re
import shlex
from datetime import datetime, timedelta
from pathlib import Path

from cockpit.kinds import DEFAULT_KIND, check_kind
from cockpit.pipeline import (SetupError, check_vendors, counters_for, next_move, step_dir, template_for,
                              validate_done, workdir_of, write_input)
from cockpit.tools import TOOLS
from cockpit.workdir import checkpoint, fingerprint, head, prepare, reset, snapshot
from cockpit.store import Run, atomic_write, now_iso


def start_run(root, request_text, project, ctrl, today=None, kind=DEFAULT_KIND):
    """领取需求：写 active 需求文件与初始 state.json。返回 run_id。kind 没登记就在写任何文件前拒绝。"""
    check_kind(kind)
    root = Path(root)
    day = (today or datetime.now()).strftime("%Y%m%d")
    active = root / "workspace" / "requests" / "active"
    active.mkdir(parents=True, exist_ok=True)
    n = len(list((root / "workspace" / "runs").glob(f"R{day}-*"))) + 1 if (root / "workspace" / "runs").exists() else 1
    rid = f"R{day}-{n:03d}"
    atomic_write(active / f"{rid}.md",
                 f"---\nschema_version: 1\nid: {rid}\nproject: {project}\n"
                 f"submitted_at: {now_iso()}\n---\n\n{request_text}\n")
    state = {"schema_version": 1, "id": rid, "project": project, "kind": kind, "status": "active",
             "stage": "S1", "round": 1, "step": None,
             "counters": counters_for(kind),
             "human": {"waiting": False, "pending_decision": None, "resume_to": None}}
    run = Run(root / "workspace" / "runs" / rid)
    state["step"] = _new_step(state, 1, ctrl)
    run.commit(state, "request.claimed")
    return rid


class Controller:
    def __init__(self, root, agents, roles, limits, invoke_fn, clock=None, on_finish=None, tools=None):
        self.root = Path(root)
        self.agents, self.roles, self.limits = agents, roles, limits
        self.invoke_fn = invoke_fn
        self.tools = tools or TOOLS  # 程序步骤用的工具表；测试可以换成假的，正式运行用 cockpit.tools.TOOLS
        self.on_finish = on_finish  # 步骤完成后调用 (run_dir, state)，用来写记录；它出错不影响流程
        self.now = clock or (lambda: datetime.now().astimezone())
        check_vendors(agents, roles)

    # ---- 步骤与输入 ----
    def _new_step(self, state, attempt):
        return _new_step(state, attempt, self)

    def _write_input(self, run_dir, state):
        return write_input(self.root, run_dir, state)

    # ---- 一步推进 ----
    def advance(self, run_dir):
        """推进一步，返回描述字符串；需求不在 active 时返回 None。"""
        run = Run(run_dir)
        state = run.load()
        if state["status"] != "active":
            return None
        step = state["step"]
        s = step["state"]
        if s == "pending":
            stage = state["stage"]
            if self._spec(state).get("gate") == "human" and stage not in state["human"].get("approved", []):
                # 人工确认关口（设计 8：合并或发布前须用户确认）：停在这一阶段开始之前，等 resume(continue) 批准
                held = dict(state, human=dict(state["human"], pending_decision=f"gate:{stage}"))
                return self._stop(run, held, "needs-human", "human.requested", {"gate": stage})
            return self._start(run, state)
        if s == "running":
            return self._run(run, state)
        if s == "finished":
            return self._transition(run, state)
        return self._after_failure(run, state)

    def _start(self, run, state):
        step = dict(state["step"])
        started = self.now()
        step.update(state="running", started_at=started.isoformat(timespec="seconds"),
                    deadline_at=(started + timedelta(minutes=self.limits["step_timeout_minutes"])).isoformat(timespec="seconds"))
        sd = run.dir / step["dir"]
        if (sd / "done.json").exists():
            # 同一阶段同一轮号被再次进入（人工处理后回到旧阶段，或审查通过后第二次进编码）：
            # 上次的 done.json 不能留在原地，否则会被"崩溃前其实已完成"的快捷路径当成这次的结果。改名归档，不删。
            n = 1
            while sd.with_name(f"{sd.name}.prev-{n}").exists():
                n += 1
            sd.rename(sd.with_name(f"{sd.name}.prev-{n}"))
        mode = self._spec(state).get("workdir")                  # write（改代码）/ use（程序用，不改）/ readonly（Agent 只读）
        if mode:
            wd = workdir_of(self.root, state)
            first = prepare(wd)                                  # 第一次建仓库；已有就不动。返回仓库的第一个提交
            step["first_commit"] = first
            if mode in ("write", "readonly"):
                # 起点：会改动或可能被改动代码的步骤开始前，先把当前代码提交成检查点，作为这一步的起点。
                # write：检查失败或审查打回退回 S4 时，Agent 是在已有代码上修，不会被清空；同一轮内的失败重试回到这个起点。
                # readonly：审查者越权改了代码时，要恢复到“审查前的真实状态”，不能恢复到更早的提交（那会把编码者的代码一起清掉）。
                label = "审查前" if mode == "readonly" else "起点"
                step["base_commit"] = checkpoint(wd, f"{state['stage']} 第 {state['round']} 轮{label}")
            else:
                step["base_commit"] = head(wd)
            if mode == "readonly":
                step["tree_before"] = fingerprint(wd)            # 审查前的指纹，审查后比对，改了就判无效
                snapshot(wd, first, run.dir / step["dir"] / "full.patch")   # 审查者要看的完整改动：从最初起点到现在
        self._write_input(run.dir, dict(state, step=step))
        run.commit(dict(state, step=step), "step.started", data={"role": step["role"], "agent": step["agent"]})
        return f"{state['stage']} 启动 {step['agent']}"

    def _spec(self, state):
        return template_for(state)["stages"][state["stage"]]

    def _run_tool(self, run, state):
        """程序步骤：不调用 Agent，工具给出 verdict，由程序写 done.json 再走同一套校验。"""
        step, spec = state["step"], self._spec(state)
        sd = run.dir / step["dir"]
        (sd / "done.json").unlink(missing_ok=True)
        wd = workdir_of(self.root, state)
        try:
            r = self.tools[spec["tool"]]({"workdir": wd, "sd": sd, "spec": spec, "state": state,
                                     "timeout_s": self.limits["step_timeout_minutes"] * 60})
        except Exception as e:  # 工具自己出错（不是检查没通过）：按步骤失败处理，会重试，用完转人工
            r = None
            res = {"reason": "command_failed", "detail": f"{type(e).__name__}: {e}"}
        if r is not None:
            atomic_write(sd / "done.json", json.dumps({
                "id": state["id"], "stage": state["stage"], "round": state["round"], "role": step["role"],
                "outputs": r["outputs"], "verdict": r["verdict"], "summary": r["summary"],
                "finished_at": now_iso()}, ensure_ascii=False, indent=1) + "\n")
            bad = validate_done(run.dir, state)
            if bad is None:
                return self._finish(run, state)
            res = {"reason": "invalid_output", "detail": bad}
        nstep = dict(step, state="failed", fail_reason=res["reason"])
        run.commit(dict(state, step=nstep), "step.failed", data={"reason": res["reason"], "detail": res["detail"]})
        return f"{state['stage']} 失败：{res['reason']}"

    def _run(self, run, state):
        step = dict(state["step"])
        sd = run.dir / step["dir"]
        if self._spec(state).get("runner") == "tool":
            return self._run_tool(run, state)
        mode = self._spec(state).get("workdir")
        wd = workdir_of(self.root, state) if mode else None
        if (sd / "done.json").exists() and validate_done(run.dir, state) is None:
            # 崩溃可能发生在 Agent 写完、快照之前：编码阶段补做快照，确认真有改动才算完成；没有改动就当没做过，往下重做。
            # 只读阶段（审查）则确认代码没被动过。
            if mode == "write":
                if snapshot(wd, step["base_commit"], sd / "diff.patch"):
                    return self._finish(run, state)  # 崩溃前其实已完成（设计 5.4）
            elif mode == "readonly":
                if fingerprint(wd) == step["tree_before"]:
                    return self._finish(run, state)
            else:
                return self._finish(run, state)
        # ponytail: 重启后一律从 input.md 重做，不接续等待仍存活的 pane；
        # 想省一次重做时再加"pane 存活且未超时则继续等"。
        inp = self._write_input(run.dir, state)
        agent = self.agents[step["agent"]]
        (sd / "done.json").unlink(missing_ok=True)  # 重做前清掉上一次的完成标记，免得被当成这次的结果
        if mode == "write":
            reset(wd, step["base_commit"])  # 每次都从同一个起点开始，失败重试不会带着上次的半成品
        res = self.invoke_fn(
            sd, timeout_s=self.limits["step_timeout_minutes"] * 60)
        if res["ok"] and mode == "write":
            if not snapshot(wd, step["base_commit"], sd / "diff.patch"):
                res = {"ok": False, "reason": "invalid_output", "detail": "代码目录没有任何改动，不能算编码完成"}
        elif res["ok"] and mode == "readonly":
            if fingerprint(wd) != step["tree_before"]:
                # 审查者动了代码：它的结论不可信（可能改了代码再放行）。把代码恢复成审查前的样子，按无效输出重试
                reset(wd, step["base_commit"])
                res = {"ok": False, "reason": "invalid_output", "detail": "审查者修改了代码目录，结果作废，代码已恢复"}
        if res["ok"]:
            bad = validate_done(run.dir, state)
            if bad is None:
                return self._finish(run, state)
            res = {"ok": False, "reason": "invalid_output", "detail": bad}
        step.update(state="failed", fail_reason=res["reason"])
        run.commit(dict(state, step=step), "step.failed", data={"reason": res["reason"], "detail": res.get("detail")})
        return f"{state['stage']} 失败：{res['reason']}"

    def _finish(self, run, state):
        d = json.loads((run.dir / state["step"]["dir"] / "done.json").read_text(encoding="utf-8"))
        step = dict(state["step"], state="finished", verdict=d["verdict"], fail_reason=None)
        run.commit(dict(state, step=step), "step.finished", data={"verdict": d["verdict"], "summary": d["summary"]})
        if self.on_finish:
            try:
                self.on_finish(run.dir, state)
            except Exception as e:  # 记录是附加的，写不出来只留一条事件，不拖垮流水线
                run.commit(run.read(), "record.failed", data={"error": f"{type(e).__name__}: {e}"})
        return f"{state['stage']} 完成：{d['verdict']}"

    def _after_failure(self, run, state):
        step = state["step"]
        if step["attempt"] <= self.limits["step_retries"]:
            new = self._new_step(state, step["attempt"] + 1)
            run.commit(dict(state, step=new), "step.retried", data={"reason": step["fail_reason"]})
            return f"{state['stage']} 重试第 {new['attempt']} 次"
        return self._stop(run, state, "needs-human", "step.failed", {"reason": step["fail_reason"]})

    def _transition(self, run, state):
        verdict = state["step"]["verdict"]
        act, stage, rnd, inc = next_move(state, verdict, self.limits)
        counters = dict(state["counters"])
        for k, v in inc.items():
            counters[k] += v
        if act == "goto":
            nxt = dict(state, stage=stage, round=rnd, counters=counters)
            nxt["step"] = self._new_step(nxt, 1)
            run.commit(nxt, "stage.entered", data={"verdict": verdict})
            return f"进入 {stage} 第 {rnd} 轮"
        status = {"done": "done", "rejected": "rejected"}.get(act, "needs-human")
        evt = {"limit": "limit.exceeded", "done": "request.done", "rejected": "request.rejected"}.get(act, "human.requested")
        return self._stop(run, dict(state, counters=counters), status, evt, {"verdict": verdict})

    def _stop(self, run, state, status, event, data):
        nxt = dict(state, status=status)
        if status == "needs-human":
            nxt["human"] = dict(state["human"], waiting=True)
        run.commit(nxt, event, data=data)
        return f"{state['stage']} 停止：{status}"

    def resume(self, run_dir, action, note="", stage=None):
        """人处理完"等你"的需求后的回复入口（DATA_SPEC 第 8 到 10 节的最小版）。
        action: continue（原阶段再来一轮）/ rework（回到 stage 指定的阶段，默认原阶段，开新一轮）/ reject（结束）。
        回复写进 human/reply-<K>.md，后续步骤的输入里会带上它；计数器清零（用户拍板后重新给轮次）。
        只改 needs-human 的需求，其他状态报错；校验都在写任何东西之前。"""
        run = Run(run_dir)
        state = run.load()
        if state["status"] != "needs-human":
            raise ValueError(f"需求 {state['id']} 不在等待人工的状态（现在是 {state['status']}）")
        if action not in ("continue", "rework", "reject"):
            raise ValueError(f"action 只能是 continue / rework / reject，收到 {action!r}")
        stages = template_for(state)["stages"]
        target = stage or state["stage"]
        if action != "reject" and target not in stages:
            raise ValueError(f"阶段 {target!r} 不在模板里：{sorted(stages)}")
        gate = str(state["human"].get("pending_decision") or "")
        if gate.startswith("gate:") and action == "continue" and target == gate[5:]:
            # 人批准了这道关口：记下已批准，原轮次原阶段直接放行；不开新一轮，也不清计数器
            k = len(list((run.dir / "human").glob("reply-*.md"))) + 1 if (run.dir / "human").exists() else 1
            atomic_write(run.dir / "human" / f"reply-{k}.md",
                         f"---\naction: continue\nstage: {target}\nreplied_at: {now_iso()}\n---\n\n{note or '（批准）'}\n")
            human = {"waiting": False, "pending_decision": None, "resume_to": None,
                     "approved": list(state["human"].get("approved", [])) + [target]}
            run.commit(dict(state, status="active", human=human), "human.replied",
                       data={"action": "approve", "gate": target, "reply": f"human/reply-{k}.md"})
            return f"{state['id']} 批准通过 {target}"
        hdir = run.dir / "human"
        k = len(list(hdir.glob("reply-*.md"))) + 1 if hdir.exists() else 1
        atomic_write(hdir / f"reply-{k}.md",
                     f"---\naction: {action}\nstage: {target}\nreplied_at: {now_iso()}\n---\n\n{note or '（没有附言）'}\n")
        human = {"waiting": False, "pending_decision": None, "resume_to": None}
        if action == "reject":
            run.commit(dict(state, status="rejected", human=human), "human.replied",
                       data={"action": action, "reply": f"human/reply-{k}.md"})
            return f"已拒绝 {state['id']}"
        nxt = dict(state, status="active", stage=target, round=state["round"] + 1,
                   counters=counters_for(state.get("kind") or DEFAULT_KIND), human=human)
        nxt["step"] = self._new_step(nxt, 1)
        run.commit(nxt, "human.replied", data={"action": action, "stage": target, "reply": f"human/reply-{k}.md"})
        return f"{state['id']} 回到 {target} 第 {nxt['round']} 轮"

    def run_all(self, run_dir, log=print, max_steps=200):
        for _ in range(max_steps):
            msg = self.advance(run_dir)
            if msg is None:
                return
            log(msg)


def _new_step(state, attempt, ctrl):
    stage = state["stage"]
    spec = template_for(state)["stages"][stage]
    role = spec["role"]
    if spec.get("runner") == "tool":  # 程序步骤没有 Agent，也没有模型
        agent, model = f"tool:{spec['tool']}", None
    else:
        agent = ctrl.roles[role]
        model = ctrl.agents[agent].get("model")
    return {"state": "pending", "role": role, "agent": agent, "model": model,
            "dir": step_dir(stage, state["round"], state.get("kind") or DEFAULT_KIND), "started_at": None,
            "deadline_at": None, "attempt": attempt, "fail_reason": None}
