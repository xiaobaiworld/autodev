"""最小主循环（P4）：每次 advance 只推进一步并立即落盘，重启后从 state.json 继续（设计 5.3、5.4）。
hc、invoke 都可注入，便于测试。S4 以后不在本计划内。
"""
import json
import re
import shlex
from datetime import datetime, timedelta
from pathlib import Path

from cockpit.agents import launch_cmd
from cockpit.invoke import invoke as real_invoke
from cockpit.kinds import DEFAULT_KIND, check_kind
from cockpit.pipeline import STAGES, SetupError, check_vendors, next_move, step_dir, validate_done, write_input
from cockpit.store import Run, atomic_write, now_iso

EXIT_KEYS = ("ctrl+c", "ctrl+c")


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
             "counters": {"design_review_rounds": 0},
             "human": {"waiting": False, "pending_decision": None, "resume_to": None}}
    run = Run(root / "workspace" / "runs" / rid)
    state["step"] = _new_step(state, 1, ctrl)
    run.commit(state, "request.claimed")
    return rid


class Controller:
    def __init__(self, root, hc, agents, roles, panes, limits, invoke_fn=real_invoke, clock=None):
        self.root, self.hc = Path(root), hc
        self.agents, self.roles, self.panes, self.limits = agents, roles, panes, limits
        self.invoke_fn = invoke_fn
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
            return self._start(run, state)
        if s == "running":
            return self._run(run, state)
        if s == "finished":
            return self._transition(run, state)
        return self._after_failure(run, state)

    def _start(self, run, state):
        step = dict(state["step"])
        started = self.now()
        step.update(state="running", pane_id=self.panes[step["agent"]], started_at=started.isoformat(timespec="seconds"),
                    deadline_at=(started + timedelta(minutes=self.limits["step_timeout_minutes"])).isoformat(timespec="seconds"))
        self._write_input(run.dir, dict(state, step=step))
        run.commit(dict(state, step=step), "step.started", data={"role": step["role"], "agent": step["agent"], "pane_id": step["pane_id"]})
        return f"{state['stage']} 启动 {step['agent']}"

    def _run(self, run, state):
        step = dict(state["step"])
        sd = run.dir / step["dir"]
        if (sd / "done.json").exists() and validate_done(run.dir, state) is None:
            return self._finish(run, state)  # 崩溃前其实已完成（设计 5.4）
        # ponytail: 重启后一律从 input.md 重做，不接续等待仍存活的 pane；
        # 想省一次重做时再加"pane 存活且未超时则继续等"。
        inp = self._write_input(run.dir, state)
        agent = self.agents[step["agent"]]
        res = self.invoke_fn(
            self.hc, step["pane_id"], sd,
            launch_cmd(agent, sd, writable=True, add_dirs=[self.root / "workspace"]),
            f"请读取 {inp}，按其中要求把产物和 done.json 写到 {sd}，做完后只回复 DONE。",
            timeout_s=self.limits["step_timeout_minutes"] * 60, exit_keys=EXIT_KEYS)
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
        run.commit(dict(state, step=step), "step.finished", data={"verdict": d["verdict"]})
        return f"{state['stage']} 完成：{d['verdict']}"

    def _after_failure(self, run, state):
        step = state["step"]
        # 窗格丢了，重试只会立刻再失败，要人恢复窗格
        if step["fail_reason"] != "pane_lost" and step["attempt"] <= self.limits["step_retries"]:
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

    def run_all(self, run_dir, log=print, max_steps=200):
        for _ in range(max_steps):
            msg = self.advance(run_dir)
            if msg is None:
                return
            log(msg)


def _new_step(state, attempt, ctrl):
    stage = state["stage"]
    role = STAGES[stage]["role"]
    agent = ctrl.roles[role]
    model = ctrl.agents[agent].get("model")
    return {"state": "pending", "role": role, "agent": agent, "model": model,
            "dir": step_dir(stage, state["round"]), "pane_id": None, "started_at": None,
            "deadline_at": None, "attempt": attempt, "fail_reason": None}
