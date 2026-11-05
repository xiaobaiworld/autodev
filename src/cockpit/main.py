"""驾驶舱入口（P1：只做认领与校验，拒绝启动时退出码 1）。

用法：PYTHONPATH=src python3 -m cockpit.main --self t14
本机环境变量里没有终端 ID，所以主控自己的地址由 --self 给出。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from cockpit.claim import ClaimError, claim_panes
from cockpit.config import ConfigError, parse_cockpit

ROOT = Path(__file__).resolve().parents[2]


def hc_json(*args):
    r = subprocess.run(["hc", *args], capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        raise ClaimError(f"hc {' '.join(args)} 失败：{r.stderr.strip()}")
    return json.loads(r.stdout)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--self", dest="self_addr", required=True)
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
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
    for role, addr in panes.items():
        print(f"{role}\t{addr}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
