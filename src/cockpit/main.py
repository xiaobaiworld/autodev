"""驾驶舱入口：认领窗格，然后按 refresh_seconds 重绘状态区。认领失败退出码 1。

用法：PYTHONPATH=src python3 -m cockpit.main --self t14
本机环境变量里没有终端 ID，所以主控自己的地址由 --self 给出。
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from cockpit.claim import ClaimError, claim_panes
from cockpit.config import ConfigError, parse_cockpit
from cockpit.status import render

ROOT = Path(__file__).resolve().parents[2]


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
    a = ap.parse_args(argv)
    try:
        cfg = parse_cockpit(Path(a.config).read_text(encoding="utf-8"))
        fb = None
        p = Path(a.binding)
        if p.exists():
            fb = json.loads(p.read_text(encoding="utf-8"))
        terms = hc_json("ls")["terminals"]
        panes = claim_panes(terms, lambda t: hc_json("get", t).get("labels", {}),
                            a.self_addr, cfg["panes"], fb)
    except (ConfigError, ClaimError, OSError, ValueError, subprocess.SubprocessError) as e:
        print(f"拒绝启动：{e}", file=sys.stderr)
        return 1
    if a.once:
        print(frame(panes, ROOT), end="")
        return 0
    try:
        while True:
            print("\033[H\033[2J" + frame(panes, ROOT), end="", flush=True)
            time.sleep(cfg["refresh_seconds"])
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
