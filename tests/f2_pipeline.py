"""F2 端到端（花额度）：真实 Agent 在 autoloop 上跑 S1 到 S3，由我们的 Controller 经 driver 发事件、等结束、校验产物。

用法：python3 tests/f2_pipeline.py                 # 真实 Agent，花额度，期望 S3 PASS 后 done
      python3 tests/f2_pipeline.py --build         # 假 Agent，pipeline/build 跑 S1 到 S4，期望 done 在 S4 且有 diff.patch
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
from driver.record import write_record  # noqa: E402
from driver.runner import make_invoke  # noqa: E402
from driver.setup import build_rules  # noqa: E402

APP = Path(os.environ.get("AUTOLOOP_APP", "~/code/agent-autoloop")).expanduser()
REQUEST = "给计算器模块 calc.py 加一个 divide(a, b) 函数，返回 a / b；除数为 0 时抛出 ValueError，并带清楚的提示信息。需要对应的单元测试。"


def main(fake=False, build=False):
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
    policy.write_text(json.dumps({"check_fail_first": True, "S6": ["REWORK"], "no_exec_round": 3}
                                 if build else {"S3": ["REWORK"] * 5}))
    fake_cmd = ["python3", str(ROOT / "tests/fake_stage_agent.py"), str(policy), "{prompt}"] if (fake or build) else None
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
        ctrl = Controller(work, agents, roles, limits,
                          invoke_fn=make_invoke(hub),
                          on_finish=lambda rd, st: write_record(home, rd, st))
        rid = start_run(work, REQUEST, "toy", ctrl, kind="pipeline/build" if build else "pipeline/design")
        rd = work / "workspace" / "runs" / rid
        t0 = time.time()
        say = lambda m: print(f"[{time.time() - t0:5.0f}s] {m}", flush=True)
        ctrl.run_all(rd, log=say, max_steps=60)
        if build and Run(rd).read()["human"].get("pending_decision") == "gate:S9":
            say("停在 S9 前的人工关口；脚本代替人批准")
            ctrl.resume(rd, "continue", note="联机脚本批准", stage="S9")
            ctrl.run_all(rd, log=say, max_steps=60)
        st = Run(rd).read()
        events = [json.loads(l)["type"] for l in (rd / "events.jsonl").read_text().splitlines()]
        print("\n最终:", st["status"], st["stage"], "轮次", st["round"], "| 事件:", " ".join(events))
        for d in sorted(rd.glob("S*/round-*")):
            dj = d / "done.json"
            v = json.loads(dj.read_text()).get("verdict") if dj.exists() else None
            print(f"  {d.relative_to(rd)}: verdict={v} 产物={sorted(p.name for p in d.iterdir() if p.name != 'done.json')}")
        recs = sorted(rd.glob("S*/round-*/record-a*.json"))
        is_tool = lambda r: json.loads(r.read_text()).get("tool")        # 程序步骤（S5）没有中台运行和 Agent 日志，不按这条查
        bad = [r.name for r in recs if not is_tool(r) and (not json.loads(r.read_text()).get("hub_run")
                                                           or not (r.parent / "agent-a1.log").exists())]
        print(f"记录 {len(recs)} 份，缺中台运行号或日志的：{bad or '无'}")
        if build:  # 假 Agent 跑 S1 到 S9：S5 第 1 轮故意失败 -> 退回 S4 -> S5 PASS -> S6 REWORK -> 退回 S4（第 3 轮，bin/todo 故意没有可执行位）
            #           -> S5 PASS（测试不碰 bin/todo）-> S6 PASS -> S7 打 rc.1 -> S7U 使用验证判 FAIL -> 退回 S4（第 4 轮补上）
            #           -> S5 -> S6 -> S7 打 rc.2 -> S7U PASS -> S8 -> S9 前停下，脚本代替人批准 -> v0.1.0
            wd = work / "workspace" / "projects" / "toy" / rid
            rounds = lambda d: sorted(p.name for p in (rd / d).glob("round-*"))
            p2, p3 = rd / "S4-code" / "round-2" / "diff.patch", rd / "S4-code" / "round-3" / "diff.patch"
            c = lambda n: (rd / "S5-check" / f"round-{n}" / "check.log").read_text() if (rd / "S5-check" / f"round-{n}" / "check.log").exists() else ""
            full = rd / "S6-code-review" / "round-3" / "full.patch"       # 轮号跟着编码轮走：S6 只在 S5 通过后才进，所以是第 2、3 轮
            tags = subprocess.run(["git", "tag", "--list"], cwd=wd, capture_output=True, text=True).stdout.split()
            changelog = (wd / "CHANGELOG.md").read_text(encoding="utf-8") if (wd / "CHANGELOG.md").exists() else ""
            u = lambda n: (rd / "S7U-usage" / f"round-{n}" / "usage.log").read_text(encoding="utf-8") if (rd / "S7U-usage" / f"round-{n}" / "usage.log").exists() else ""
            ok = (st["status"] == "done" and st["stage"] == "S9"
                  and sorted(tags) == ["v0.1.0", "v0.1.0-rc.1", "v0.1.0-rc.2"] and "## v0.1.0" in changelog   # 两个候选（使用验证失败过一次）和正式标签，都是真的 git 操作
                  and (rd / "S7-release").exists() and (rd / "S8-acceptance").exists() and (rd / "S9-publish").exists()
                  and st["human"].get("approved") == ["S9"]
                  and len(rounds("S4-code")) == 4 and len(rounds("S5-check")) == 4 and len(rounds("S6-code-review")) == 3
                  and len(rounds("S7U-usage")) == 2 and len(rounds("S7-release")) == 2
                  and "不可执行" in u(3) and "✗" in u(3) and "✗" not in u(4) and u(4).count("✓") == 7   # 第 3 轮用不了，第 4 轮 7 步全过
                  and "退出码 1" in c(1) and "退出码 0" in c(2) and "退出码 0" in c(3)
                  and "-VERSION = 1" in p2.read_text() and "+VERSION = 2" in p2.read_text()    # 第 2 轮在第 1 轮代码上改
                  and "+VERSION = 3" in p3.read_text()                                          # 审查打回后第 3 轮继续在上面改
                  and full.exists() and "VERSION = 3" in full.read_text()                       # 第 2 次审查看到完整改动
                  and not bad)
            print(f"S4 {len(rounds('S4-code'))} 轮，S5 {len(rounds('S5-check'))} 轮，S6 {len(rounds('S6-code-review'))} 轮，S7U {len(rounds('S7U-usage'))} 轮；"
                  f"标签 {sorted(tags)}；代码目录 {sorted(p.name for p in wd.iterdir() if p.name != '.git')}；记录 {len(recs)} 份")
        elif fake:  # 3 次 REWORK 用完审查轮次，必须停在 needs-human，且发生过 limit.exceeded，S2 做过 3 轮
            ok = (st["status"] == "needs-human" and "limit.exceeded" in events
                  and len(list(rd.glob("S2-design/round-*"))) == 3 and st["counters"]["design_review_rounds"] == 3
                  and len(recs) == 7 and not bad)
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
    sys.exit(main(fake="--fake-rework" in sys.argv, build="--build" in sys.argv))
