"""落盘驱动模板流水线；每次 advance 只启动或完成当前一步。"""
import json
from datetime import datetime, timedelta
from pathlib import Path

from cockpit.agents import launch_cmd
from cockpit.kinds import DEFAULT_KIND, check_kind
from cockpit.pipeline import SetupError, check_vendors, load_template, next_move, step_dir, validate_done, write_input
from cockpit.store import Run, atomic_write, now_iso
from cockpit.tools import run_tool
from cockpit.workdir import checkpoint, fingerprint, full_patch, head, prepare, project_dir, restore
from driver.record import write_agent_record, write_tool_record


def start_run(root, request_text, project, ctrl, today=None, kind=DEFAULT_KIND):
    """写入原文和初始状态；未知流水线类型在任何写入前拒绝。"""
    check_kind(kind)
    ctrl.template = load_template(kind)
    root = Path(root)
    day = (today or datetime.now()).strftime("%Y%m%d")
    runs = root / "workspace" / "runs"
    rid = f"R{day}-{len(list(runs.glob(f'R{day}-*'))) + 1:03d}"
    active = root / "workspace" / "requests" / "active"
    active.mkdir(parents=True, exist_ok=True)
    atomic_write(active / f"{rid}.md",
                 f"---\nschema_version: 1\nid: {rid}\nproject: {project}\nsubmitted_at: {now_iso()}\n---\n\n{request_text}\n")
    counters = {key: 0 for key in ctrl.limits if key.endswith("_rounds")}
    state = {"schema_version": 1, "id": rid, "project": project, "kind": kind, "status": "active",
             "stage": ctrl.template["order"][0], "round": 1, "step": None,
             "counters": counters, "workdir": str(project_dir(root, {"project": project, "id": rid})),
             "human": {"waiting": False, "pending_decision": None, "resume_to": None}}
    state["step"] = ctrl._new_step(state, 1)
    Run(runs / rid).commit(state, "request.claimed")
    return rid


class Controller:
    def __init__(self, root, agents, roles, limits, invoke_fn, clock=None, kind=DEFAULT_KIND):
        self.root = Path(root)
        self.agents, self.roles, self.limits = agents, roles, limits
        self.invoke_fn, self.now = invoke_fn, clock or (lambda: datetime.now().astimezone())
        self.template = load_template(kind)
        check_vendors(agents, roles)

    def _new_step(self, state, attempt):
        spec = self.template["stages"][state["stage"]]
        role = spec["role"]
        agent = self.roles.get(role)
        model = self.agents.get(agent, {}).get("model") if agent else None
        return {"state": "pending", "role": role, "agent": agent, "model": model,
                "dir": step_dir(state["stage"], state["round"], self.template),
                "started_at": None, "deadline_at": None, "attempt": attempt, "fail_reason": None}

    def _write_input(self, run_dir, state):
        spec = self.template["stages"][state["stage"]]
        if "full_diff" in spec.get("inputs", []):
            patch = full_patch(state["workdir"])
            atomic_write(Path(run_dir) / "full.patch", patch)
        return write_input(self.root, run_dir, state, self.template)

    def advance(self, run_dir):
        run = Run(run_dir)
        state = run.load()
        if state["status"] != "active":
            return None
        status = state["step"]["state"]
        if status == "pending":
            return self._start(run, state)
        if status == "running":
            return self._run(run, state)
        if status == "finished":
            return self._transition(run, state)
        return self._after_failure(run, state)

    def _start(self, run, state):
        step = dict(state["step"])
        spec = self.template["stages"][state["stage"]]
        if spec.get("workdir") == "write":
            prepare(state["workdir"])
        started = self.now()
        step.update(state="running", started_at=started.isoformat(timespec="seconds"),
                    deadline_at=(started + timedelta(minutes=self.limits["step_timeout_minutes"])).isoformat(timespec="seconds"))
        self._write_input(run.dir, dict(state, step=step))
        run.commit(dict(state, step=step), "step.started",
                   data={"role": step["role"], "agent": step["agent"], "workdir": state["workdir"]})
        return f"{state['stage']} 启动 {step['agent'] or '程序'}"

    def _run(self, run, state):
        step = dict(state["step"])
        folder = run.dir / step["dir"]
        if (folder / "done.json").exists() and validate_done(run.dir, state, self.template) is None:
            return self._finish(run, state)
        spec = self.template["stages"][state["stage"]]
        if spec.get("runner") == "tool":
            try:
                verdict = run_tool(run.dir, state, self.template)
                write_tool_record(run.dir, state, spec, verdict)
                if validate_done(run.dir, state, self.template) is None:
                    return self._finish(run, state)
                res = {"ok": False, "reason": "invalid_output", "detail": "程序步骤产物无效"}
            except (OSError, ValueError, KeyError) as e:
                res = {"ok": False, "reason": "tool_error", "detail": str(e)}
            step.update(state="failed", fail_reason=res["reason"])
            run.commit(dict(state, step=step), "step.failed", data={"reason": res["reason"], "detail": res.get("detail")})
            return f"{state['stage']} 失败：{res['reason']}"

        inp = self._write_input(run.dir, state)
        agent = self.agents[step["agent"]]
        read_only = spec.get("workdir") == "readonly"
        before = fingerprint(state["workdir"]) if read_only else None
        revision = head(state["workdir"]) if read_only else None
        res = self.invoke_fn(
            folder,
            launch_cmd(agent, folder, writable=not read_only, add_dirs=[self.root / "workspace", state["workdir"]]),
            f"请读取 {inp}，按其中要求完成并写出 done.json，做完后只回复 DONE。",
            timeout_s=self.limits["step_timeout_minutes"] * 60)
        write_agent_record(run.dir, state, agent, res)
        if read_only and fingerprint(state["workdir"]) != before:
            restore(state["workdir"], revision)
            res = {"ok": False, "reason": "review_tampered", "detail": "审查者修改了只读代码，已恢复"}
        if res["ok"]:
            bad = validate_done(run.dir, state, self.template)
            if bad is None:
                if state["stage"] == "S4":
                    checkpoint(state["workdir"], f"Implement {state['id']} round {state['round']}")
                return self._finish(run, state)
            res = {"ok": False, "reason": "invalid_output", "detail": bad}
        step.update(state="failed", fail_reason=res["reason"])
        run.commit(dict(state, step=step), "step.failed", data={"reason": res["reason"], "detail": res.get("detail")})
        return f"{state['stage']} 失败：{res['reason']}"

    def _finish(self, run, state):
        done = json.loads((run.dir / state["step"]["dir"] / "done.json").read_text(encoding="utf-8"))
        step = dict(state["step"], state="finished", verdict=done["verdict"], summary=done["summary"], fail_reason=None)
        run.commit(dict(state, step=step), "step.finished", data={"verdict": done["verdict"], "summary": done["summary"]})
        return f"{state['stage']} 完成：{done['verdict']}"

    def _after_failure(self, run, state):
        step = state["step"]
        if step["attempt"] <= self.limits["step_retries"]:
            new = self._new_step(state, step["attempt"] + 1)
            run.commit(dict(state, step=new), "step.retried", data={"reason": step["fail_reason"]})
            return f"{state['stage']} 重试第 {new['attempt']} 次"
        return self._stop(run, state, "needs-human", "step.failed", {"reason": step["fail_reason"]})

    def _transition(self, run, state):
        verdict = state["step"]["verdict"]
        action, stage, rnd, inc = next_move(state, verdict, self.limits, self.template)
        counters = dict(state["counters"])
        for key, value in inc.items():
            counters[key] = counters.get(key, 0) + value
        if action == "goto":
            nxt = dict(state, stage=stage, round=rnd, counters=counters)
            nxt["step"] = self._new_step(nxt, 1)
            if self.template["stages"][stage].get("gate") == "human":
                nxt["status"] = "needs-human"
                nxt["human"] = {"waiting": True, "pending_decision": f"gate:{stage}", "resume_to": stage}
                run.commit(nxt, "human.gate", data={"stage": stage, "verdict": verdict})
                return f"进入 {stage} 前等待人工批准"
            run.commit(nxt, "stage.entered", data={"verdict": verdict})
            return f"进入 {stage} 第 {rnd} 轮"
        status = {"done": "done", "rejected": "rejected"}.get(action, "needs-human")
        event = {"limit": "limit.exceeded", "done": "request.done", "rejected": "request.rejected"}.get(action, "human.requested")
        return self._stop(run, dict(state, counters=counters), status, event, {"verdict": verdict})

    def _stop(self, run, state, status, event, data):
        nxt = dict(state, status=status)
        if status == "needs-human":
            nxt["human"] = dict(state.get("human", {}), waiting=True,
                                pending_decision=state.get("human", {}).get("pending_decision") or event,
                                resume_to=state.get("human", {}).get("resume_to"))
        run.commit(nxt, event, data=data)
        return f"{state['stage']} 停止：{status}"

    def run_all(self, run_dir, log=print, max_steps=300):
        for _ in range(max_steps):
            msg = self.advance(run_dir)
            if msg is None:
                return
            log(msg)
        raise RuntimeError(f"超过最大推进次数：{max_steps}")
