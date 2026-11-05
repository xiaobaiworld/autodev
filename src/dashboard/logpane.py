"""主窗格：跟着最新一轮 Agent 的日志显示。python3 -m dashboard.logpane --home <autoloop 数据目录>

只读。日志在 <home>/worker/runs/<轮次>-<尝试>/stdout-<n>.log，格式化见 logview.py。
"""
import argparse
import re
import shutil
import sys
import time
from pathlib import Path

from dashboard.logview import latest_log, tail_lines
from driver.hub import Hub, HubError, load_config


def describe(log, hub):
    """标题行：第几轮、规则、Agent、状态。中台连不上时只显示轮次号。"""
    m = re.fullmatch(r"(\d+)-(\d+)", log.parent.name)
    run_id, attempt = int(m.group(1)), int(m.group(2))
    head = f"第 {run_id} 轮（尝试 {attempt}）"
    try:
        r = next((r for r in hub.state().get("runs", []) if r["id"] == run_id), None)
    except HubError:
        r = None
    if r:
        head += f"  {r.get('rule')} / {r.get('agent')}  {r.get('state')}"
    return head


def frame(home, hub, height, width):
    log = latest_log(Path(home) / "worker" / "runs")
    if log is None:
        return "还没有 Agent 运行过。\n"
    body = tail_lines(log, max(1, height - 3))
    return f"{describe(log, hub)}\n{'─' * max(10, min(width, 70))}\n" + "\n".join(body) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", required=True)
    ap.add_argument("--every", type=float, default=1.0)
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args(argv)
    try:
        hub = Hub(load_config(a.home))
    except (OSError, KeyError, ValueError) as e:
        print(f"读不了中台配置 {a.home}/config.json：{e}", file=sys.stderr)
        return 1
    try:
        while True:
            size = shutil.get_terminal_size((100, 30))
            out = frame(a.home, hub, size.lines, size.columns - 1)
            print(out if a.once else "\033[H\033[2J" + out, end="", flush=True)
            if a.once:
                return 0
            time.sleep(a.every)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
