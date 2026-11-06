"""用真实 autoloop 测流水线：默认 S1-S3，--build 假 Agent 完整走 S1-S9。"""
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
from driver.reply import main as reply_main  # noqa: E402
from driver.runner import make_invoke  # noqa: E402
from driver.setup import build_rules  # noqa: E402

APP = Path(os.environ.get("AUTOLOOP_APP", "~/code/agent-autoloop")).expanduser()
TODO_REQUEST = (ROOT / "requests/demo-todo-cli.md").read_text(encoding="utf-8")
CALC_REQUEST = "给计算器模块 calc.py 加一个 divide(a, b) 函数，返回 a / b；除数为 0 时抛出 ValueError，并带清楚的提示信息。需要对应的单元测试。"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main(mode=None):
    kind = "pipeline/build" if mode == "build" else "pipeline/design"
    fake = mode in ("build", "fake-rework")
    request = TODO_REQUEST if mode == "build" else CALC_REQUEST
    config_text = (ROOT / "config.yaml").read_text(encoding="utf-8")
    agents, roles, limits = parse_agents(config_text), parse_roles(config_text), parse_limits(config_text)
    limits["step_timeout_minutes"] = 0.25
    tmp = Path(tempfile.mkdtemp(prefix="autodev-f2-"))
    home, work, port = tmp / "home", tmp / "root", free_port()
    (work / "workspace").mkdir(parents=True)
    (work / "config.yaml").write_text(config_text, encoding="utf-8")
    (tmp / "bin").mkdir()
    osa = tmp / "bin/osascript"
    osa.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    osa.chmod(0o755)
    env = dict(os.environ, AGENT_AUTOLOOP_HOME=str(home), PATH=f"{tmp / 'bin'}:{os.environ['PATH']}")
    cli = ["node", "--disable-warning=ExperimentalWarning", str(APP / "bin/agent-autoloop.ts")]
    subprocess.run(cli + ["init", "--command", "true {prompt}", "--no-service", "--port", str(port)],
                   env=env, capture_output=True, text=True, check=True)
    base = json.loads((home / "rules.json").read_text(encoding="utf-8"))
    policy = tmp / "policy.json"
    if mode == "build":
        policy.write_text(json.dumps({"S6": ["REWORK"]}), encoding="utf-8")
    elif mode == "fake-rework":
        policy.write_text(json.dumps({"S3": ["REWORK"] * 5}), encoding="utf-8")
    else:
        policy.write_text("{}", encoding="utf-8")
    fake_cmd = ["python3", str(ROOT / "tests/fake_stage_agent.py"), str(policy), "{prompt}"] if fake else None
    rules = build_rules(base, agents, roles, str(work / "workspace"), effort="low",
                        fake_command=fake_cmd, kind=kind)
    (home / "rules.json").write_text(json.dumps(rules, ensure_ascii=False, indent=1), encoding="utf-8")
    checked = subprocess.run(cli + ["check"], env=env, capture_output=True, text=True)
    print("规则检查:", (checked.stdout + checked.stderr).strip()[:200])
    if checked.returncode:
        print("规则无效；数据保留在", tmp)
        return 1
    hub_proc = subprocess.Popen(cli + ["up"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
    ok = False
    try:
        for _ in range(100):
            with socket.socket() as sock:
                sock.settimeout(0.25)
                if sock.connect_ex(("127.0.0.1", port)) == 0:
                    break
            time.sleep(0.1)
        hub = Hub(load_config(home))
        ctrl = Controller(work, agents, roles, limits, invoke_fn=make_invoke(hub), kind=kind)
        rid = start_run(work, request, "toy", ctrl, kind=kind)
        run_dir = work / "workspace/runs" / rid
        started = time.monotonic()
        ctrl.run_all(run_dir, log=lambda m: print(f"[{time.monotonic() - started:5.1f}s] {m}", flush=True))
        state = Run(run_dir).read()
        events = [json.loads(row)["type"] for row in (run_dir / "events.jsonl").read_text().splitlines()]
        print("\n阶段运行结束：", state["status"], state["stage"], "第", state["round"], "轮")
        if mode == "build":
            usage_fails = list(run_dir.glob("S7U-usage/round-*/usage.log"))
            tags = subprocess.run(["git", "-C", state["workdir"], "tag", "--list"], text=True,
                                  capture_output=True, check=True).stdout.splitlines()
            gate_ok = (state["status"] == "needs-human" and state["human"]["pending_decision"] == "gate:S9"
                       and "human.gate" in events and len(usage_fails) == 2
                       and any("未达到预期" in p.read_text(encoding="utf-8") for p in usage_fails)
                       and "v0.1.0-rc.1" in tags and "v0.1.0-rc.2" in tags and "v0.1.0" not in tags)
            print("S9 等待批准：", gate_ok, "| S7U 日志数：", len(usage_fails), "| 标签：", tags)
            if gate_ok:
                reply_status = reply_main([rid, "continue", "--note", "假 Agent 联机测试批准",
                                           "--root", str(work), "--home", str(home)])
                if reply_status != 0:
                    print("S9 回复命令失败：", reply_status)
                final = Run(run_dir).read()
                tags = subprocess.run(["git", "-C", final["workdir"], "tag", "--list"], text=True,
                                      capture_output=True, check=True).stdout.splitlines()
                ok = (reply_status == 0 and final["status"] == "done" and "v0.1.0" in tags
                      and (Path(final["workdir"]) / "CHANGELOG.md").is_file())
        elif mode == "fake-rework":
            ok = (state["status"] == "needs-human" and "limit.exceeded" in events
                  and len(list(run_dir.glob("S2-design/round-*"))) == 3
                  and state["counters"]["design_review_rounds"] == 3)
        else:
            ok = state["status"] == "done" and state["stage"] == "S3"
    finally:
        if hub_proc.poll() is None:
            try:
                os.killpg(hub_proc.pid, signal.SIGTERM)
                hub_proc.wait(timeout=10)
            except (ProcessLookupError, PermissionError, subprocess.TimeoutExpired):
                pass
    print(f"\n{'通过' if ok else '未通过'}；目录保留在 {tmp}")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--build" in sys.argv:
        sys.exit(main("build"))
    if "--fake-rework" in sys.argv:
        sys.exit(main("fake-rework"))
    sys.exit(main())
