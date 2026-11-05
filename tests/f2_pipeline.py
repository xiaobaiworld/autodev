"""F2 端到端（花额度）：真实 Agent 在 autoloop 上跑 S1 到 S3，由我们的 Controller 经 driver 发事件、等结束、校验产物。

用法：python3 tests/f2_pipeline.py                 # 真实 Agent，花额度，期望 S3 PASS 后 done
      python3 tests/f2_pipeline.py --fake-rework   # 假 Agent，S3 一直 REWORK，期望轮次上限后 needs-human
Agent、模型、厂商取自 config.yaml；为省钱，规则里的强度统一压到 low（config 里的强度不动）。
"""
import json
import os
import re
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
REQUEST = "给计算器模块 calc.py 加一个 divide(a, b) 函数，返回 a / b；除数为 0 时抛出 ValueError，并带清楚的提示信息。需要对应的单元测试。"


def main(fake=False):
    cfg_text = (ROOT / "config.yaml").read_text(encoding="utf-8")
    agents, roles, limits = parse_agents(cfg_text), parse_roles(cfg_text), parse_limits(cfg_text)
    limits["step_timeout_minutes"] = 15
    tmp = Path(tempfile.mkdtemp(prefix="autoloop-f2-"))
    home, work = tmp / "home", tmp / "root"
    (work / "workspace").mkdir(parents=True)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    (tmp / "bin").mkdir()
    osa = tmp / "bin/osascript"
    osa.write_text("#!/bin/sh\nexit 0\n")
    osa.chmod(0o755)
    env = dict(os.environ, AGENT_AUTOLOOP_HOME=str(home), PATH=f"{tmp / 'bin'}:{os.environ['PATH']}")
    cmd = ["node", "--disable-warning=ExperimentalWarning", str(APP / "bin/agent-autoloop.ts")]
    subprocess.run(cmd + ["init", "--command", "true {prompt}", "--no-service", "--port", str(port)],
                   env=env, capture_output=True, check=True)
    base = json.loads((home / "rules.json").read_text())
    policy = tmp / "policy.json"
    policy.write_text(json.dumps({"S3": ["REWORK"] * 5}))
    fake_cmd = ["python3", str(ROOT / "tests/fake_stage_agent.py"), str(policy), "{prompt}"] if fake else None
    rules = build_rules(base, agents, roles, str(work / "workspace"), effort="low", fake_command=fake_cmd)
    (home / "rules.json").write_text(json.dumps(rules, ensure_ascii=False, indent=1))
    chk = subprocess.run(cmd + ["check"], env=env, capture_output=True, text=True)
    print("规则检查:", (chk.stdout + chk.stderr).strip()[:120])
    hub_proc = subprocess.Popen(cmd + ["up"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
    ok = False
    try:
        for _ in range(100):
            with socket.socket() as s:
                s.settimeout(0.5)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    break
            time.sleep(0.1)
        hub = Hub(load_config(home))
        panes = {k: "hub" for k in agents}
        ctrl = Controller(work, None, agents, roles, panes, limits,
                          invoke_fn=make_invoke(hub, limits["step_retries"]))
        rid = start_run(work, REQUEST, "toy", ctrl)
        rd = work / "workspace" / "runs" / rid
        t0 = time.time()
        ctrl.run_all(rd, log=lambda m: print(f"[{time.time() - t0:5.0f}s] {m}", flush=True), max_steps=40)
        st = Run(rd).read()
        events = [json.loads(l)["type"] for l in (rd / "events.jsonl").read_text().splitlines()]
        print("\n最终:", st["status"], st["stage"], "轮次", st["round"], "| 事件:", " ".join(events))
        for d in sorted(rd.glob("S*/round-*")):
            dj = d / "done.json"
            v = json.loads(dj.read_text()).get("verdict") if dj.exists() else None
            print(f"  {d.relative_to(rd)}: verdict={v} 产物={sorted(p.name for p in d.iterdir() if p.name != 'done.json')}")
        if fake:  # 3 次 REWORK 用完审查轮次，必须停在 needs-human，且发生过 limit.exceeded，S2 做过 3 轮
            ok = (st["status"] == "needs-human" and "limit.exceeded" in events
                  and len(list(rd.glob("S2-design/round-*"))) == 3 and st["counters"]["design_review_rounds"] == 3)
        else:
            ok = st["status"] == "done" and st["stage"] == "S3"
    finally:
        try:
            os.killpg(hub_proc.pid, signal.SIGTERM)
            hub_proc.wait(timeout=10)
        except (ProcessLookupError, PermissionError, subprocess.TimeoutExpired):
            pass
    print(f"\n{'通过' if ok else '未通过'}；目录保留在 {tmp}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(fake="--fake-rework" in sys.argv))
