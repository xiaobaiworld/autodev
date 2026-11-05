"""一次 Agent 调用（设计 2.3）：发启动命令、发任务提示、等 done.json、退出并确认回到 shell。

hc 对象只需 get/send/keys/kill 四个方法，便于用假对象测试。完成判断以 done.json 为准（L003）。
"""
import json
import subprocess
import time
from pathlib import Path


def at_shell(info):
    """前台进程就是窗格自己的 shell。比 pid 而不是进程名：`bash x.sh` 的前台名也是 bash。"""
    fg = info.get("foreground") or {}
    return fg.get("pid") is not None and fg.get("pid") == info.get("pid")


def _fail(reason):
    return {"ok": False, "reason": reason}


def _read_done(path):
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _fail("invalid_output")
    if not isinstance(d, dict):
        return _fail("invalid_output")
    return {"ok": True, "reason": None} if d.get("ok") is True else _fail("command_failed")


def _exit_agent(hc, pane, exit_keys, clock, sleep, wait_s=10, poll=1):
    """发退出键，等前台回到 shell。返回 None=已回到 shell，或失败原因。"""
    hc.keys(pane, *exit_keys)
    start = clock()
    while True:
        info = hc.get(pane)
        if info is None:
            return "pane_lost"
        if at_shell(info):
            return None
        if clock() - start >= wait_s:
            hc.kill(pane)  # 退不出：杀掉，调用方把窗格恢复成 shell（风险 1）
            return "agent_blocked"
        sleep(poll)


def invoke(hc, pane, run_dir, launch_tmpl, prompt, timeout_s, exit_keys,
           clock=time.monotonic, sleep=time.sleep, poll=1):
    """run_dir 里要有 input.md；产物与 done.json 由 Agent 写到同目录。

    launch_tmpl 里的 {input} 会替换成 input.md 的绝对路径。
    返回 {"ok": bool, "reason": None|timeout|pane_lost|invalid_output|command_failed|agent_blocked}
    """
    run_dir = Path(run_dir)
    done = run_dir / "done.json"
    done.unlink(missing_ok=True)  # 重入安全：旧的完成标记不能算本次
    hc.send(pane, "clear && " + launch_tmpl.format(input=run_dir / "input.md"))
    hc.send(pane, prompt)

    start = clock()
    result = None
    while result is None:
        if hc.get(pane) is None:
            return _fail("pane_lost")
        if done.exists():
            result = _read_done(done)
        elif clock() - start >= timeout_s:
            result = _fail("timeout")
        else:
            sleep(poll)

    bad = _exit_agent(hc, pane, exit_keys, clock, sleep)
    return _fail(bad) if bad else result


class Hc:
    """真实 hc。发送走 `hc exec hc send`，避免从 Agent 窗格发出时文本被包装（L005）。
    # ponytail: 主控是普通进程时是否需要 exec，未测；先统一用 exec，确认后可简化。
    """

    def _run(self, *args, timeout=30):
        return subprocess.run(["hc", *args], capture_output=True, text=True, timeout=timeout)

    def get(self, pane):
        r = self._run("get", pane)
        if r.returncode != 0:
            return None
        d = json.loads(r.stdout)
        return d if d.get("state") == "live" and "foreground" in d else None

    def send(self, pane, text):
        r = self._run("exec", "hc", "send", pane, text)
        if r.returncode != 0:
            raise RuntimeError(f"hc send {pane} 失败：{r.stderr.strip()}")

    def keys(self, pane, *keys):
        self._run("keys", pane, *keys)

    def kill(self, pane):
        self._run("kill", pane)
