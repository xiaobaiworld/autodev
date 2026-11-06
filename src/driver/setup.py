"""由 config.yaml 的 agents、roles 生成 autoloop 的 rules.json。F2 的测试脚本和正式入口共用，改规则只改这里。"""
import copy
import json
import shutil
import time
from pathlib import Path

from cockpit.pipeline import STAGES as PIPELINE_STAGES
from cockpit.store import atomic_write

PROMPT = ("这一轮的任务目录是事件的对象（subject），相对于当前目录。先读取该目录下的 input.md，严格按其中的要求完成："
          "产物和 done.json 都写进该目录，一律用文件读写工具，不要用 shell 命令写文件。最后一条消息第一行写一句话结论。")
STAGES = tuple((k.lower(), v["role"]) for k, v in PIPELINE_STAGES.items())  # 来自 templates/pipeline/design.json
USE = {"claude": "claude", "codex": "codex"}  # agy 走 command 插件，P4 之外暂不接


def build_rules(base, agents, roles, cwd, effort=None, fake_command=None, timeout_minutes=15):
    """base 是 autoloop init 生成的 rules.json（取 sources、channels、worker 名）。返回新的 rules 字典，不改 base。
    effort: 覆盖 config 里的强度（省钱用）；fake_command: 用这条命令代替真实 Agent（测试用）。"""
    out = copy.deepcopy(base)
    worker = next(iter(base["agents"].values()))["worker"]
    out["agents"], out["rules"] = {}, []
    for stage, role in STAGES:
        name = roles[role]
        if name in out["agents"]:
            continue
        a = agents[name]
        if fake_command:
            out["agents"][name] = {"name": name, "worker": worker, "use": "command", "command": list(fake_command)}
            continue
        if a["cli"] not in USE:
            raise ValueError(f"{name} 用的 {a['cli']} 暂不支持（只有 {sorted(USE)}）")
        out["agents"][name] = {"name": name, "worker": worker, "use": USE[a["cli"]], "model": a["model"],
                               "effort": effort or a.get("effort", "low"), "access": "edit",
                               "timeout": timeout_minutes}
    for stage, role in STAGES:
        out["rules"].append({"name": f"{stage}-{role}", "when": {"source": "local", "types": [f"stage.{stage}"]},
                             "to": roles[role], "cwd": cwd, "prompt": PROMPT})
    return out


def install_rules(home, rules):
    """把 rules 原子写进 <home>/rules.json（中台几秒内热加载）。已有旧文件先备份，返回备份路径或 None。"""
    path = Path(home) / "rules.json"
    backup = None
    if path.exists():
        n = 0
        while True:
            backup = path.with_name(f"rules.json.bak-{time.strftime('%Y%m%d-%H%M%S')}" + (f"-{n}" if n else ""))
            if not backup.exists():
                break
            n += 1
        shutil.copy2(path, backup)
    atomic_write(path, json.dumps(rules, ensure_ascii=False, indent=1) + "\n")
    return backup
