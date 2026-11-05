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
from cockpit.pipeline import STAGES, next_move, step_dir, validate_done
from cockpit.store import Run, atomic_write, now_iso

EXIT_KEYS = ("ctrl+c", "ctrl+c")


class SetupError(Exception):
    pass


def check_vendors(agents, roles):
    """D008：设计作者与设计审查者的模型厂商必须不同。"""
    a, b = agents[roles["designer"]], agents[roles["design_reviewer"]]
    if a.get("vendor") == b.get("vendor"):
        raise SetupError(f"designer 与 design_reviewer 同为 {a.get('vendor')}，违反 D008")


def start_run(root, request_text, project, ctrl, today=None):
    """领取需求：写 active 需求文件与初始 state.json。返回 run_id。"""
    root = Path(root)
    day = (today or datetime.now()).strftime("%Y%m%d")
    active = root / "workspace" / "requests" / "active"
    active.mkdir(parents=True, exist_ok=True)
    n = len(list((root / "workspace" / "runs").glob(f"R{day}-*"))) + 1 if (root / "workspace" / "runs").exists() else 1
    rid = f"R{day}-{n:03d}"
    atomic_write(active / f"{rid}.md",
                 f"---\nschema_version: 1\nid: {rid}\nproject: {project}\n"
                 f"submitted_at: {now_iso()}\n---\n\n{request_text}\n")
    state = {"schema_version": 1, "id": rid, "project": project, "status": "active",
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
        st, step = state["stage"], state["step"]
        spec = STAGES[st]
        rid, rnd = state["id"], state["round"]
        req = self.root / "workspace" / "requests" / "active" / f"{rid}.md"
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
            f"## 输出要求\n产物与 done.json 都写到 {out}。最后写 done.json，内容为 JSON 对象，字段：\n"
            f'id="{rid}"，stage="{st}"，round={rnd}，role="{step["role"]}"，'
            f"outputs=产物文件名列表（须包含 {spec['outputs']}），"
            f"verdict 取 {spec['verdicts']} 之一，且与产物 frontmatter 的 verdict 一致，finished_at 为 ISO 时间。\n\n"
            "## 必须停止并写 BLOCK 的情况\n删除数据、修改密钥或凭证、修改权限、对外发送消息、花钱、改变产品方向。"
        )
        atomic_write(out / "input.md", body)
        return out / "input.md"

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
            launch_cmd(agent, sd, writable=True),
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
