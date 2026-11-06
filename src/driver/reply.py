"""处理需求的人工回复：继续、退回指定阶段或拒绝。"""
import argparse
import sys
from pathlib import Path

from cockpit.agents import parse_agents, parse_limits, parse_roles
from cockpit.controller import Controller
from cockpit.pipeline import load_template
from cockpit.store import LockError, Run, acquire_lock, atomic_write
from driver.hub import Hub, HubError, load_config
from driver.runner import make_invoke

ROOT = Path(__file__).resolve().parents[2]


def apply_reply(root, request_id, action, note="", stage=None):
    run_dir = Path(root) / "workspace" / "runs" / request_id
    run = Run(run_dir)
    state = run.load()
    if state["status"] != "needs-human":
        raise ValueError(f"{request_id} 当前状态是 {state['status']}，不在等待人工")
    template = load_template(state["kind"])
    config = (Path(root) / "config.yaml").read_text(encoding="utf-8")
    ctrl = Controller(root, parse_agents(config), parse_roles(config), parse_limits(config),
                      invoke_fn=lambda *args, **kwargs: None, kind=state["kind"])
    if action == "reject":
        nxt = dict(state, status="rejected")
        nxt["human"] = dict(state["human"], waiting=False, pending_decision=None)
        event = "request.rejected"
    elif action == "continue":
        nxt = dict(state, status="active")
        if state["step"]["state"] == "finished":
            nxt["round"] += 1
            nxt["step"] = ctrl._new_step(nxt, 1)
        elif state["step"]["state"] != "pending":
            nxt["step"] = ctrl._new_step(nxt, state["step"]["attempt"] + 1)
        nxt["human"] = dict(state["human"], waiting=False, pending_decision=None, resume_to=None)
        event = "human.continued"
    elif action == "rework":
        if stage not in template["stages"]:
            raise ValueError(f"退回阶段必须是模板中的一项：{', '.join(template['order'])}")
        nxt = dict(state, status="active", stage=stage, round=state["round"] + 1)
        nxt["step"] = ctrl._new_step(nxt, 1)
        nxt["human"] = dict(state["human"], waiting=False, pending_decision=None, resume_to=None)
        event = "human.rework"
    else:
        raise ValueError(f"未知回复：{action}")
    if note:
        atomic_write(run_dir / "human.md", f"回复：{action}\n退回阶段：{stage or '-'}\n\n{note}\n")
    run.commit(nxt, event, actor="human", data={"action": action, "stage": stage, "note": note})
    return nxt


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("request_id")
    parser.add_argument("action", choices=("continue", "rework", "reject"))
    parser.add_argument("--stage")
    parser.add_argument("--note", default="")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--home", help="agent-autoloop 数据目录；继续或退回 Agent 步骤时必需")
    args = parser.parse_args(argv)
    try:
        root = Path(args.root)
        run_dir = root / "workspace" / "runs" / args.request_id
        lock = acquire_lock(root / "workspace" / ".lock")
        try:
            current = Run(run_dir).load()
            template = load_template(current["kind"])
            target = args.stage if args.action == "rework" else current["stage"]
            order = template["order"]
            target_index = order.index(target) if target in order else len(order)
            needs_agent = args.action != "reject" and any(
                template["stages"][name].get("runner") != "tool" for name in order[target_index:])
            if needs_agent and not args.home:
                raise ValueError("继续或退回后仍有 Agent 步骤，请提供 --home")
            config = (root / "config.yaml").read_text(encoding="utf-8")
            agents, roles, limits = parse_agents(config), parse_roles(config), parse_limits(config)
            hub = Hub(load_config(args.home)) if needs_agent else None
            if hub:
                hub.state()
            invoke = make_invoke(hub) if hub else (lambda *a, **k: None)
            state = apply_reply(root, args.request_id, args.action, args.note, args.stage)
            if args.action in ("continue", "rework"):
                ctrl = Controller(root, agents, roles, limits, invoke_fn=invoke, kind=state["kind"])
                ctrl.run_all(run_dir, log=lambda message: print(message, flush=True))
                state = Run(run_dir).read()
        finally:
            lock.close()
    except (OSError, ValueError, KeyError, LockError) as exc:
        print(f"回复失败：{exc}", file=sys.stderr)
        return 1
    except HubError as exc:
        print(f"回复失败：{exc}", file=sys.stderr)
        return 1
    print(f"{args.request_id} 已处理：{args.action}，状态 {state['status']}，阶段 {state['stage']}")
    return 0 if state["status"] in ("done", "rejected") else 2


if __name__ == "__main__":
    raise SystemExit(main())
