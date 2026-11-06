"""F5 崩溃与卡住（假 Agent，不花额度）：在真实 autoloop 中台上验证三种情况。

python3 tests/f5_crash.py hang        # Agent 卡住：我们超时、取消、重试，最后跑通；卡住的进程不能残留
python3 tests/f5_crash.py ctrl-kill   # 驱动被 kill -9 后重启：不重复发同一轮，最后跑通
python3 tests/f5_crash.py hub-kill    # 中台被 kill -9 后重启：观察是否恢复、有没有重复或丢失（先观察，再定标准）
"""
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cockpit.agents import parse_agents, parse_limits, parse_roles  # noqa: E402
from cockpit.controller import Controller, start_run  # noqa: E402
from cockpit.store import Run  # noqa: E402
from driver.hub import Hub, load_config  # noqa: E402
from driver.runner import make_invoke  # noqa: E402
from driver.setup import build_rules  # noqa: E402

APP = Path(os.environ.get("AUTOLOOP_APP", "~/code/agent-autoloop")).expanduser()
CMD = ["node", "--disable-warning=ExperimentalWarning", str(APP / "bin/agent-autoloop.ts")]
TIMEOUT_MIN = 0.15  # 9 秒，够快又不至于把正常的假 Agent 误判成卡住


class Env:
    def __init__(self, policy):
        self.tmp = Path(tempfile.mkdtemp(prefix="autoloop-f5-"))
        self.home, self.work = self.tmp / "home", self.tmp / "root"
        (self.work / "workspace").mkdir(parents=True)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        (self.tmp / "bin").mkdir()
        osa = self.tmp / "bin/osascript"
        osa.write_text("#!/bin/sh\nexit 0\n")
        osa.chmod(0o755)
        self.env = dict(os.environ, AGENT_AUTOLOOP_HOME=str(self.home), PATH=f"{self.tmp / 'bin'}:{os.environ['PATH']}")
        subprocess.run(CMD + ["init", "--command", "true {prompt}", "--no-service", "--port", str(self.port)],
                       env=self.env, capture_output=True, check=True)
        text = (ROOT / "config.yaml").read_text(encoding="utf-8")
        self.agents, self.roles, self.limits = parse_agents(text), parse_roles(text), parse_limits(text)
        self.limits["step_timeout_minutes"] = TIMEOUT_MIN
        self.policy = self.tmp / "policy.json"
        self.policy.write_text(json.dumps(policy))
        fake = ["python3", str(ROOT / "tests/fake_stage_agent.py"), str(self.policy), "{prompt}"]
        base = json.loads((self.home / "rules.json").read_text())
        rules = build_rules(base, self.agents, self.roles, str(self.work / "workspace"), fake_command=fake)
        (self.home / "rules.json").write_text(json.dumps(rules, ensure_ascii=False, indent=1))
        self.hub_proc = None

    def up(self):
        self.hub_proc = subprocess.Popen(CMD + ["up"], env=self.env, stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL, start_new_session=True)
        for _ in range(100):
            with socket.socket() as s:
                s.settimeout(0.5)
                if s.connect_ex(("127.0.0.1", self.port)) == 0:
                    return
            time.sleep(0.1)
        raise RuntimeError("中台没起来")

    def down(self, sig=signal.SIGTERM):
        if self.hub_proc:
            try:
                os.killpg(self.hub_proc.pid, sig)
                self.hub_proc.wait(timeout=10)
            except (ProcessLookupError, PermissionError, subprocess.TimeoutExpired):
                pass
            self.hub_proc = None

    def controller(self):
        hub = Hub(load_config(self.home))
        return hub, Controller(self.work, None, self.agents, self.roles, {k: "hub" for k in self.agents}, self.limits,
                               invoke_fn=make_invoke(hub, self.limits["step_retries"], poll_s=3))

    def events(self, rd):
        return [json.loads(l)["type"] for l in (rd / "events.jsonl").read_text().splitlines()]

    def ingested_keys(self):
        """事实日志里所有入库事件的 id（同一 id 重发会被中台去重，不会出现第二条）。"""
        import sqlite3
        c = sqlite3.connect(f"file:{self.home / 'hub.db'}?mode=ro", uri=True)
        out = []
        for (f,) in c.execute("select fact from facts order by seq"):
            for ch in json.loads(f).get("changes", []):
                if ch.get("table") == "events":
                    out.append(ch["row"]["key"])
        return out

    def leftovers(self):
        out = subprocess.run(["pgrep", "-f", f"fake_stage_agent.py {self.policy}"], capture_output=True, text=True)
        return [p for p in out.stdout.split() if p]


def check(name, cond, detail=""):
    print(f"  {'✓' if cond else '✗'} {name}{('：' + str(detail)) if detail else ''}")
    return bool(cond)


def log(t0):
    return lambda m: print(f"[{time.time() - t0:5.0f}s] {m}", flush=True)


def hang():
    e = Env({"hang": {"S2": 1}})
    try:
        e.up()
        _, ctrl = e.controller()
        rid = start_run(e.work, "卡住测试", "toy", ctrl)
        rd = e.work / "workspace" / "runs" / rid
        time.sleep(4)
        ctrl.run_all(rd, log=log(time.time()), max_steps=40)
        st, ev = Run(rd).read(), e.events(rd)
        time.sleep(2)
        return all([check("最终跑通", st["status"] == "done", st["status"]),
                    check("记录了超时失败和重试", "step.failed" in ev and "step.retried" in ev, ev),
                    check("卡住的 Agent 进程没有残留", not e.leftovers(), e.leftovers())])
    finally:
        e.down()
        print("目录:", e.tmp)


def ctrl_kill():
    e = Env({"hang": {"S2": 1}})
    child = None
    try:
        e.up()
        _, ctrl = e.controller()
        rid = start_run(e.work, "驱动被杀测试", "toy", ctrl)
        rd = e.work / "workspace" / "runs" / rid
        time.sleep(4)
        code = ("import sys,time;sys.path.insert(0,%r);sys.path.insert(0,%r)\n"
                "import f5_crash as f;e=f.Env.__new__(f.Env)\n") % (str(ROOT / "src"), str(ROOT / "tests"))
        # 子进程里重建控制器；用同一个中台和同一个需求目录
        code += ("import json,sys\nfrom pathlib import Path\nfrom cockpit.agents import *\n"
                 "from cockpit.controller import Controller\nfrom driver.hub import *\nfrom driver.runner import make_invoke\n"
                 "t=Path(%r).read_text();a,r,l=parse_agents(t),parse_roles(t),parse_limits(t);l['step_timeout_minutes']=%r\n"
                 "h=Hub(load_config(Path(%r)));c=Controller(Path(%r),None,a,r,{k:'hub' for k in a},l,invoke_fn=make_invoke(h,l['step_retries'],poll_s=3))\n"
                 "c.run_all(Path(%r),log=print,max_steps=40)\n") % (
            str(ROOT / "config.yaml"), TIMEOUT_MIN, str(e.home), str(e.work), str(rd))
        child = subprocess.Popen([sys.executable, "-c", code], env=dict(os.environ, PYTHONPATH=str(ROOT / "src")))
        time.sleep(5)  # S1 完成、S2 已发出并卡住
        os.kill(child.pid, signal.SIGKILL)
        child.wait()
        before = Run(rd).read()
        print("被杀时:", before["stage"], before["step"]["state"], "第", before["step"]["attempt"], "次")
        hub, ctrl2 = e.controller()
        ctrl2.run_all(rd, log=log(time.time()), max_steps=40)
        st, ev = Run(rd).read(), e.events(rd)
        time.sleep(2)
        keys = e.ingested_keys()
        s2 = [k for k in keys if "-S2-" in k]
        return all([check("最终跑通", st["status"] == "done", st["status"]),
                    check("S2 至少看到一个事件（检查不是空转）", len(s2) >= 1, s2),
                    check("S2 第一次尝试只入库一次，重试才有第二个", sorted(s2) == [k for k in sorted(s2) if k.endswith(("-a1", "-a2"))] and len(s2) == len(set(s2)) and len(s2) == 2, s2),
                    check("没有残留进程", not e.leftovers(), e.leftovers())])
    finally:
        if child and child.poll() is None:
            child.kill()
        e.down()
        print("目录:", e.tmp)


def hub_kill():
    e = Env({"hang": {}})
    try:
        e.up()
        hub, ctrl = e.controller()
        rid = start_run(e.work, "中台被杀测试", "toy", ctrl)
        rd = e.work / "workspace" / "runs" / rid
        import threading
        t = threading.Thread(target=lambda: ctrl.run_all(rd, log=log(time.time()), max_steps=40), daemon=True)
        t.start()
        time.sleep(3)
        e.down(signal.SIGKILL)
        print("中台已 kill -9；3 秒后重启")
        time.sleep(3)
        e.up()
        t.join(timeout=240)
        st, ev = Run(rd).read(), e.events(rd)
        print("结果:", st["status"], st["stage"], "事件:", " ".join(ev))
        return check("驱动线程已结束", not t.is_alive()) and check("最终跑通", st["status"] == "done", st["status"])
    finally:
        e.down()
        print("目录:", e.tmp)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = {"hang": hang, "ctrl-kill": ctrl_kill, "hub-kill": hub_kill}.get(which)
    if not fn:
        sys.exit(__doc__)
    ok = fn()
    print("通过" if ok else "未通过")
    sys.exit(0 if ok else 1)
