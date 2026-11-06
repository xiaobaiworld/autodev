"""正式入口：把规则装进指定的 autoloop 中台，再用 Controller 跑一个需求的 S1 到 S3。

python3 -m driver.run --home <autoloop 数据目录> --root <AutoDev 根目录> --request <需求.md> [--effort low]
中台要已经在运行（agent-autoloop up）。看板与日志窗格读同一个 home 和 root，所以能实时看到这次运行。
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from cockpit.agents import parse_agents, parse_limits, parse_roles
from cockpit.controller import Controller, start_run
from cockpit.kinds import DEFAULT_KIND
from cockpit.pipeline import SetupError
from cockpit.store import LockError, Run, acquire_lock
from driver.hub import Hub, HubError, load_config
from driver.record import write_record
from driver.runner import make_invoke
from driver.setup import build_rules, install_rules

AUTODEV = Path(__file__).resolve().parents[2]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", required=True, help="agent-autoloop 数据目录（含 config.json、rules.json）")
    ap.add_argument("--root", default=str(AUTODEV), help="放 workspace/runs 的目录，看板读这里")
    ap.add_argument("--request", required=True, help="需求正文文件")
    ap.add_argument("--kind", default=DEFAULT_KIND, help="需求类型：pipeline/design（到设计审查）或 pipeline/build（含编码）")
    ap.add_argument("--effort", default=None, help="覆盖 config 里的强度，如 low")
    ap.add_argument("--config", default=str(AUTODEV / "config.yaml"))
    a = ap.parse_args(argv)
    root, home = Path(a.root), Path(a.home)
    try:
        lock = acquire_lock(root / "workspace" / ".lock")  # 单实例
        text = Path(a.config).read_text(encoding="utf-8")
        agents, roles, limits = parse_agents(text), parse_roles(text), parse_limits(text)
        base = json.loads((home / "rules.json").read_text(encoding="utf-8"))
        rules = build_rules(base, agents, roles, str(root / "workspace"), effort=a.effort)
        hub = Hub(load_config(home))
        hub.state()  # 中台没起来就在这里失败，不要先改规则
        backup = install_rules(home, rules)
        ctrl = Controller(root, agents, roles, limits,
                          invoke_fn=make_invoke(hub),
                          on_finish=lambda rd, st: write_record(home, rd, st))
        rid = start_run(root, Path(a.request).read_text(encoding="utf-8"), "toy", ctrl, kind=a.kind)
    except (OSError, ValueError, KeyError, LockError, SetupError, HubError) as e:
        print(f"启动失败：{e}", file=sys.stderr)
        return 1
    print(f"需求 {rid}；旧规则备份：{backup or '无'}", flush=True)
    time.sleep(4)  # 中台几秒内热加载规则
    t0 = time.time()
    ctrl.run_all(root / "workspace" / "runs" / rid, log=lambda m: print(f"[{time.time() - t0:5.0f}s] {m}", flush=True))
    st = Run(root / "workspace" / "runs" / rid).read()
    print(f"结束：{st['status']} {st['stage']} 第 {st['round']} 轮 {datetime.now().strftime('%H:%M:%S')}")
    lock.close()
    return 0 if st["status"] == "done" else 2


if __name__ == "__main__":
    sys.exit(main())
