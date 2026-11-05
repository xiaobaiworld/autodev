"""驾驶舱入口：认领窗格，然后按 refresh_seconds 重绘状态区。认领失败退出码 1。

用法：PYTHONPATH=src python3 -m cockpit.main --self t14
本机环境变量里没有终端 ID，所以主控自己的地址由 --self 给出。
"""
import argparse
import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from cockpit.agents import parse_agents, parse_limits, parse_roles
from cockpit.claim import ClaimError, claim_panes
from cockpit.config import ConfigError, parse_cockpit
from cockpit.controller import Controller, SetupError, start_run
from cockpit.invoke import Hc
from cockpit.status import render
from cockpit.store import LockError, acquire_lock

ROOT = Path(__file__).resolve().parents[2]
ERRORS = []


def hc_json(*args):
    r = subprocess.run(["hc", *args], capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        raise ClaimError(f"hc {' '.join(args)} 失败：{r.stderr.strip()}")
    return json.loads(r.stdout)


def load_run(root):
    """取 workspace/runs 下最近更新的 status=active 的 state.json；没有返回 None。"""
    best = None
    for f in (root / "workspace" / "runs").glob("*/state.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if d.get("status") == "active" and (best is None or d.get("updated_at", "") > best.get("updated_at", "")):
            best = d
    return best


def frame(panes, root):
    """一帧文字；任何读取失败都变成一行错误，不抛出。"""
    try:
        terms = {t["address"]: t for t in hc_json("ls")["terminals"]}
        return render(load_run(root), panes, terms, datetime.now().astimezone())
    except (ClaimError, OSError, ValueError, KeyError, subprocess.SubprocessError) as e:
        return f"读取失败（将继续重试）：{e}\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--self", dest="self_addr", required=True)
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--once", action="store_true", help="只画一帧就退出")
    ap.add_argument("--binding", default=str(ROOT / "workspace" / "cockpit.json"))
    ap.add_argument("--start", metavar="REQUEST.md", help="用这份需求新建一个 run 并推进")
    ap.add_argument("--project", default="toy", help="--start 时写入的项目名")
    ap.add_argument("--resume", action="store_true", help="接续 workspace/runs 下未结束的 run")
    a = ap.parse_args(argv)
    lock = None
    try:
        if a.start or a.resume:
            lock = acquire_lock(ROOT / "workspace" / ".lock")
        cfg = parse_cockpit(Path(a.config).read_text(encoding="utf-8"))
        fb = None
        p = Path(a.binding)
        if p.exists():
            fb = json.loads(p.read_text(encoding="utf-8"))
        terms = hc_json("ls")["terminals"]
        panes = claim_panes(terms, lambda t: hc_json("get", t).get("labels", {}),
                            a.self_addr, cfg["panes"], fb)
        ctrl = None
        if a.start or a.resume:
            text = Path(a.config).read_text(encoding="utf-8")
            ctrl = Controller(ROOT, Hc(), parse_agents(text), parse_roles(text), panes, parse_limits(text))
            if a.start:
                rid = start_run(ROOT, Path(a.start).read_text(encoding="utf-8"), a.project, ctrl)
                run_dirs = [ROOT / "workspace" / "runs" / rid]
            else:
                run_dirs = [f.parent for f in (ROOT / "workspace" / "runs").glob("*/state.json")]
    except (ConfigError, ClaimError, LockError, SetupError, OSError, ValueError,
            subprocess.SubprocessError) as e:
        print(f"拒绝启动：{e}", file=sys.stderr)
        return 1
    if a.once:
        print(frame(panes, ROOT), end="")
        return 0
    if ctrl:
        def work():
            for d in run_dirs:
                try:
                    ctrl.run_all(d, log=lambda m: None)
                except Exception as e:  # 后台线程出错要让界面看得到，而不是静默退出
                    ERRORS.append(f"{d.name}: {type(e).__name__}: {e}")
        threading.Thread(target=work, daemon=True).start()
    try:
        while True:
            err = "".join(f"主控出错：{e}\n" for e in ERRORS)
            print("\033[H\033[2J" + frame(panes, ROOT) + err, end="", flush=True)
            time.sleep(cfg["refresh_seconds"])
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
