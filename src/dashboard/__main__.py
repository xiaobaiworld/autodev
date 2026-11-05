"""命令行看板：python3 -m dashboard --home <autoloop 数据目录> --root <AutoDev 根目录> [--once]

只读：中台 /v1/state 加 <root>/workspace/runs/*/state.json。关掉它不影响流程。
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from dashboard.render import render
from driver.hub import Hub, HubError, load_config


def pipelines(root):
    out = []
    for f in sorted((Path(root) / "workspace" / "runs").glob("*/state.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if d.get("status") in ("active", "needs-human"):
            out.append(d)
    return out


def frame(hub, root):
    state, err = None, None
    try:
        state = hub.state()
    except HubError as e:
        err = str(e)
    return render(state, pipelines(root), datetime.now().astimezone(), error=err)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", required=True, help="agent-autoloop 的数据目录（含 config.json）")
    ap.add_argument("--root", default=".", help="AutoDev 根目录")
    ap.add_argument("--every", type=float, default=2.0)
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args(argv)
    try:
        hub = Hub(load_config(a.home))
    except (OSError, KeyError, ValueError) as e:
        print(f"读不了中台配置 {a.home}/config.json：{e}", file=sys.stderr)
        return 1
    if a.once:
        print(frame(hub, a.root), end="")
        return 0
    try:
        while True:
            print("\033[H\033[2J" + frame(hub, a.root), end="", flush=True)
            time.sleep(a.every)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
