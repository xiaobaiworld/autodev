"""把 Controller 的 Agent 调用交给 autoloop，并从事实流等待结束。"""
import re
import time

from cockpit.store import Run
from driver.hub import HubError, RunTracker

STAGE_TYPE = lambda stage: f"stage.{stage.lower()}"


def event_id(state):
    """每次尝试一个新 id：同一 id 重发会被中台去重，重试就拿不到新的一轮。"""
    return f"{state['id']}-{state['stage']}-r{state['round']}-a{state['step']['attempt']}"


def subject_of(state):
    """步骤目录（相对 workspace 目录，规则的 cwd 就是 workspace）。只含字母数字和 - / .，符合中台对 subject 的限制，长度 < 100。"""
    return f"runs/{state['id']}/{state['step']['dir']}"


def make_invoke(hub, hub_retries=0, tracker=None, clock=time.monotonic, sleep=time.sleep, poll_s=30):
    tracker = tracker or RunTracker()  # ponytail: 从序号 0 重放整个日志；历史很大时改为只读最近序号

    def capture(result):
        if result and result.get("hub_run_id"):
            result["agent_log"] = hub.agent_log(result["hub_run_id"])
        return result

    def invoke(sd, _launch, _prompt, timeout_s):
        run_dir = sd.parents[1]
        state = Run(run_dir).read()
        key = event_id(state)
        try:
            hub.emit(key, STAGE_TYPE(state["stage"]), subject_of(state),
                     f"{state['stage']} {state['step']['role']}")
        except HubError as e:
            return {"ok": False, "reason": "command_failed", "detail": str(e)}
        deadline = clock() + timeout_s
        while True:
            remaining = max(0.1, deadline - clock())
            try:
                for fact in hub.facts(after=tracker.seq, timeout=min(poll_s, remaining)):
                    tracker.feed(fact)
                    done = capture(_judge(hub, tracker, key, hub_retries))
                    if done:
                        return done
                    if clock() >= deadline:
                        break
            except HubError as e:
                last = str(e)
                sleep(min(5, max(0, deadline - clock())))
                if clock() >= deadline:
                    return {"ok": False, "reason": "command_failed", "detail": last}
            done = capture(_judge(hub, tracker, key, hub_retries))
            if done:
                return done
            if clock() >= deadline:
                st = tracker.status(key)
                if st:
                    _try_cancel(hub, st["run"])
                    return capture({"ok": False, "reason": "timeout", "hub_run_id": st["run"],
                                    "hub_attempts": st["attempts"], "detail": st.get("error")})
                return {"ok": False, "reason": "timeout"}

    return invoke


def _judge(hub, tracker, key, hub_retries):
    st = tracker.status(key)
    if st is None or st["state"] == "running":
        return None
    if st["state"] == "ended":
        if st["raw"] == "cancelled":  # 中台连续失败后放弃、或被人取消
            return {"ok": False, "reason": "command_failed", "detail": st.get("summary"),
                    "hub_run_id": st["run"], "hub_attempts": st["attempts"]}
        return {"ok": True, "reason": None, "hub_run_id": st["run"], "hub_attempts": st["attempts"]}
    # 确定性进程失败交给 Controller 重新派新事件，不等中台的分钟级退避。
    if st["attempts"] > hub_retries:
        _try_cancel(hub, st["run"])
        return {"ok": False, "reason": "command_failed", "detail": st.get("error"),
                "hub_run_id": st["run"], "hub_attempts": st["attempts"]}
    return None


def _try_cancel(hub, run):
    try:
        hub.cancel(run)
    except HubError:
        pass
