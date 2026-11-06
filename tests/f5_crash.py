"""F5 故障场景：在真实 autoloop 中台上模拟崩溃、挂起、驱动强杀和中台重启。"""
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
CFG_TEXT = (ROOT / "config.yaml").read_text(encoding="utf-8")
AGENTS, ROLES, BASE_LIMITS = parse_agents(CFG_TEXT), parse_roles(CFG_TEXT), parse_limits(CFG_TEXT)


def port_free():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def listening(port):
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def hub_command(home):
    return ["node", "--disable-warning=ExperimentalWarning", str(APP / "bin/agent-autoloop.ts")]


def start_hub(ctx):
    ctx["hub_proc"] = subprocess.Popen(hub_command(ctx["home"]) + ["up"], env=ctx["env"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       start_new_session=True)
    for _ in range(100):
        if listening(ctx["port"]):
            return
        time.sleep(0.1)
    raise RuntimeError("中台没有启动")


def stop_hub(ctx):
    proc = ctx.get("hub_proc")
    if proc and proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            pass
    ctx["hub_proc"] = None
    for _ in range(50):
        if not listening(ctx["port"]):
            return
        time.sleep(0.1)


def setup(mode):
    tmp = Path(tempfile.mkdtemp(prefix=f"autodev-f5-{mode}-"))
    home, root, port = tmp / "home", tmp / "root", port_free()
    (root / "workspace").mkdir(parents=True)
    (root / "config.yaml").write_text(CFG_TEXT, encoding="utf-8")
    (tmp / "bin").mkdir()
    osa = tmp / "bin/osascript"
    osa.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    osa.chmod(0o755)
    env = dict(os.environ, AGENT_AUTOLOOP_HOME=str(home), PATH=f"{tmp / 'bin'}:{os.environ['PATH']}")
    cli = hub_command(home)
    subprocess.run(cli + ["init", "--command", "true {prompt}", "--no-service", "--port", str(port)],
                   env=env, capture_output=True, text=True, check=True)
    base = json.loads((home / "rules.json").read_text(encoding="utf-8"))
    command = ["python3", str(ROOT / "tests/f5_worker.py"), mode, "{prompt}"]
    rules = build_rules(base, AGENTS, ROLES, str(root / "workspace"), effort="low", fake_command=command)
    (home / "rules.json").write_text(json.dumps(rules, ensure_ascii=False, indent=1), encoding="utf-8")
    check = subprocess.run(cli + ["check"], env=env, capture_output=True, text=True)
    if check.returncode:
        raise RuntimeError(check.stdout + check.stderr)
    ctx = {"tmp": tmp, "home": home, "root": root, "port": port, "env": env}
    start_hub(ctx)
    return ctx


def controller(ctx):
    limits = dict(BASE_LIMITS, step_timeout_minutes=0.05)
    return Controller(ctx["root"], AGENTS, ROLES, limits,
                      invoke_fn=make_invoke(Hub(load_config(ctx["home"])), poll_s=0.4))


def stop_all(ctx):
    stop_hub(ctx)


def fail_case(mode):
    ctx = setup(mode)
    ok = False
    try:
        ctrl = controller(ctx)
        rid = start_run(ctx["root"], "F5 故障场景", "toy", ctrl)
        run_dir = ctx["root"] / "workspace/runs" / rid
        before = time.monotonic()
        ctrl.run_all(run_dir, log=lambda msg: print(msg, flush=True))
        elapsed = time.monotonic() - before
        state = Run(run_dir).read()
        events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
        retries = [event for event in events if event["type"] == "step.retried"]
        event_ids = sorted(p.name for p in (ctx["home"] / "worker/runs").glob("*"))
        ok = (state["status"] == "needs-human" and len(retries) == BASE_LIMITS["step_retries"]
              and len(event_ids) == BASE_LIMITS["step_retries"] + 1 and elapsed < 25)
        print(f"{mode}: {elapsed:.1f}s, 重试 {len(retries)} 次, worker 目录 {len(event_ids)} 个")
    finally:
        stop_all(ctx)
    print("通过" if ok else f"未通过；证据保留在 {ctx['tmp']}")
    return 0 if ok else 1


def child_drive(root, home, rid):
    from cockpit.store import acquire_lock
    ctx = {"root": Path(root), "home": Path(home)}
    lock = acquire_lock(ctx["root"] / "workspace/.lock")
    try:
        ctrl = controller(ctx)
        run_dir = ctx["root"] / "workspace/runs" / rid
        ctrl.advance(run_dir)
        ctrl.advance(run_dir)
    finally:
        lock.close()


def wait_for(predicate, seconds=12):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return False


def driver_kill_case():
    ctx = setup("slow-first")
    ok = False
    try:
        ctrl = controller(ctx)
        rid = start_run(ctx["root"], "driver-kill resume", "toy", ctrl)
        run_dir = ctx["root"] / "workspace/runs" / rid
        env = dict(ctx["env"], PYTHONPATH=str(ROOT / "src"))
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--drive-child",
                                  str(ctx["root"]), str(ctx["home"]), rid], env=env, start_new_session=True)
        started = wait_for(lambda: bool(list((ctx["home"] / "worker/runs").glob("*/context.json")))
                           and Run(run_dir).read()["step"]["state"] == "running")
        if started:
            child.kill()
            child.wait(timeout=5)
            completed = wait_for(lambda: (run_dir / "S1-analysis/round-1/done.json").is_file(), 8)
            if completed:
                ctrl.run_all(run_dir, log=lambda msg: print(msg, flush=True))
                state = Run(run_dir).read()
                folders = list((ctx["home"] / "worker/runs").glob("*"))
                ok = state["status"] == "done" and len(folders) == 3
        elif child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        print("driver kill: 驱动被杀后从状态文件恢复", ok)
    finally:
        stop_all(ctx)
    print("通过" if ok else f"未通过；证据保留在 {ctx['tmp']}")
    return 0 if ok else 1


def hub_kill_case():
    ctx = setup("success")
    ok = False
    try:
        ctrl = controller(ctx)
        rid = start_run(ctx["root"], "hub-kill resume", "toy", ctrl)
        run_dir = ctx["root"] / "workspace/runs" / rid
        for _ in range(3):
            ctrl.advance(run_dir)
        state = Run(run_dir).read()
        before = state["stage"]
        stop_hub(ctx)
        start_hub(ctx)
        ctrl = controller(ctx)
        ctrl.run_all(run_dir, log=lambda msg: print(msg, flush=True))
        state = Run(run_dir).read()
        ok = before == "S2" and state["status"] == "done" and state["stage"] == "S3"
        print("hub kill: 中台重启后续跑", ok)
    finally:
        stop_all(ctx)
    print("通过" if ok else f"未通过；证据保留在 {ctx['tmp']}")
    return 0 if ok else 1


def main(case):
    if case in ("hang", "crash"):
        return fail_case(case)
    if case == "ctrl-kill":
        return driver_kill_case()
    if case == "hub-kill":
        return hub_kill_case()
    print("用法：python3 tests/f5_crash.py hang|crash|ctrl-kill|hub-kill", file=sys.stderr)
    return 2


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--drive-child":
        child_drive(*sys.argv[2:])
    else:
        sys.exit(main(sys.argv[1] if len(sys.argv) == 2 else ""))
