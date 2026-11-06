"""人处理完"等你"的需求后的回复入口。

python3 -m driver.reply --root <AutoDev 根目录> --home <autoloop 数据目录> <需求号> <continue|rework|reject> [--note 附言] [--stage 阶段]

continue 在人工确认关口（如 S9 前）上就是批准；rework 退回 --stage 指定的阶段；reject 结束需求。
回复后接着往下跑，直到下一次停下或结束。S9 是程序步骤，不调用 Agent，所以批准发布不需要中台在线以外的东西。
"""
import argparse
import sys
import time
from pathlib import Path

from cockpit.agents import parse_agents, parse_limits, parse_roles
from cockpit.controller import Controller
from cockpit.pipeline import SetupError
from cockpit.store import LockError, Run, acquire_lock
from driver.hub import Hub, HubError, load_config
from driver.record import write_record
from driver.runner import make_invoke

AUTODEV = Path(__file__).resolve().parents[2]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("action", choices=["continue", "rework", "reject"])
    ap.add_argument("--note", default="")
    ap.add_argument("--stage", default=None)
    ap.add_argument("--home", required=True)
    ap.add_argument("--root", default=str(AUTODEV))
    ap.add_argument("--config", default=str(AUTODEV / "config.yaml"))
    a = ap.parse_args(argv)
    root, home = Path(a.root), Path(a.home)
    rd = root / "workspace" / "runs" / a.run_id
    try:
        lock = acquire_lock(root / "workspace" / ".lock")  # 单实例：不能和正在跑的流水线同时动同一批需求
        text = Path(a.config).read_text(encoding="utf-8")
        agents, roles, limits = parse_agents(text), parse_roles(text), parse_limits(text)
        ctrl = Controller(root, agents, roles, limits, invoke_fn=make_invoke(Hub(load_config(home))),
                          on_finish=lambda d, st: write_record(home, d, st))
        before = Run(rd).read()
        print(f"{a.run_id} 现在：{before['status']} {before['stage']} 第 {before['round']} 轮"
              f"（{before['human'].get('pending_decision') or '无待决项'}）", flush=True)
        print(ctrl.resume(rd, a.action, note=a.note, stage=a.stage), flush=True)
    except (OSError, ValueError, KeyError, LockError, SetupError, HubError) as e:
        print(f"失败：{e}", file=sys.stderr)
        return 1
    t0 = time.time()
    ctrl.run_all(rd, log=lambda m: print(f"[{time.time() - t0:5.0f}s] {m}", flush=True))
    after = Run(rd).read()
    print(f"结束：{after['status']} {after['stage']} 第 {after['round']} 轮")
    lock.close()
    return 0 if after["status"] in ("done", "rejected") else 2


if __name__ == "__main__":
    sys.exit(main())
