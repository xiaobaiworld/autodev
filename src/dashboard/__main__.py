"""命令行看板：python3 -m dashboard --home <autoloop 数据目录> --root <AutoDev 根目录> [--once]

只读：中台 /v1/state 加 <root>/workspace/runs/*/state.json。关掉它不影响流程。
"""
import argparse
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

from dashboard.logview import fit
from dashboard.render import render
from driver.hub import Hub, HubError, load_config


def pipelines(root):
    out = []
    for f in sorted((Path(root) / "workspace" / "runs").glob("*/state.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append(d)  # 已完成、已拒绝的也要列出，由 render 决定折叠
    return out


def frame(hub, root, home=None):
    state, err = None, None
    try:
        state = hub.state()
    except HubError as e:
        err = str(e)
    size = shutil.get_terminal_size((70, 24))
    now, pipes = datetime.now().astimezone(), pipelines(root)
    # 画面不能比窗格高，否则顶部会滚出去：从多到少试，直到放得下（至少留 1 条运行记录）
    for n in range(12, 0, -1):
        out = render(state, pipes, now, error=err, width=size.columns - 1, max_runs=n,
                     reply_cmd=f"PYTHONPATH=src python3 -m driver.reply --home {home}" if home else None)
        if len(out.splitlines()) <= size.lines - 1:
            break
    return "\n".join(fit(l, size.columns - 1) for l in out.splitlines()) + "\n"  # 超宽会折行，把画面撑高


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
        print(frame(hub, a.root, a.home), end="")
        return 0
    try:
        while True:
            print("\033[H\033[2J" + frame(hub, a.root, a.home), end="", flush=True)
            time.sleep(a.every)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
