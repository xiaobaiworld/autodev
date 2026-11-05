"""把 Controller 的"调用一次 Agent"换成：向 autoloop 中台发事件，读事实流等这一轮结束。

返回值和 cockpit.invoke.invoke 一致：{"ok": bool, "reason": None|timeout|command_failed}。
完成与否仍由 Controller 按 done.json 校验，这里只回答"中台那一轮有没有跑完"。
"""
import re
import time

from cockpit.store import Run
from driver.hub import HubError, RunTracker

STAGE_TYPE = lambda stage: f"stage.{stage.lower()}"


def event_id(state):
    """每次尝试一个新 id：同一 id 重发会被中台去重，重试就拿不到新的一轮。"""
    return f"{state['id']}-{state['stage']}-r{state['round']}-a{state['step']['attempt']}"


def subject_of(state):
    """步骤目录（相对 runs 目录）。只含字母数字和 - / .，符合中台对 subject 的限制，长度 < 100。"""
    return f"{state['id']}/{state['step']['dir']}"


def make_invoke(hub, step_retries, tracker=None, clock=time.monotonic, sleep=time.sleep, poll_s=30):
    tracker = tracker or RunTracker()  # ponytail: 从序号 0 重放整个日志；历史很大时改为只读最近序号

    def invoke(_hc, _pane, sd, _launch, _prompt, timeout_s, exit_keys=None):  # 与 Controller 的调用签名一致
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
            try:
                for fact in hub.facts(after=tracker.seq, timeout=poll_s):
                    tracker.feed(fact)
                    done = _judge(hub, tracker, key, step_retries)
                    if done:
                        return done
                    if clock() >= deadline:
                        break
            except HubError as e:
                last = str(e)
                sleep(min(5, max(0, deadline - clock())))
                if clock() >= deadline:
                    return {"ok": False, "reason": "command_failed", "detail": last}
            done = _judge(hub, tracker, key, step_retries)
            if done:
                return done
            if clock() >= deadline:
                st = tracker.status(key)
                if st:
                    _try_cancel(hub, st["run"])
                return {"ok": False, "reason": "timeout"}

    return invoke


def _judge(hub, tracker, key, step_retries):
    st = tracker.status(key)
    if st is None or st["state"] == "running":
        return None
    if st["state"] == "ended":
        if st["raw"] == "cancelled":  # 中台连续失败后放弃、或被人取消
            return {"ok": False, "reason": "command_failed", "detail": st.get("summary")}
        return {"ok": True, "reason": None}
    # retrying：中台还会自己重试；超过我们允许的次数就取消，交给 Controller 决定下一步
    if st["attempts"] > step_retries:
        _try_cancel(hub, st["run"])
        return {"ok": False, "reason": "command_failed", "detail": st.get("error")}
    return None


def _try_cancel(hub, run):
    try:
        hub.cancel(run)
    except HubError:
        pass
