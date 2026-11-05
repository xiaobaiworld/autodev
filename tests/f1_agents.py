"""F1：真实 Agent 无界面各跑一轮（花额度）。判定只看文件、日志和 why，不信 Agent 自述。

用法：python3 -I tests/f1_agents.py [claude-opus claude-sonnet codex agy probe]   # 不给参数则全跑
每格输出 通过/失败/未验证 加证据路径。数据目录在临时位置，结束后保留日志目录路径以便查证。
"""
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

APP = Path(os.environ.get("AUTOLOOP_APP", "~/code/agent-autoloop")).expanduser()
TASK = "在当前目录创建文件 out.txt，内容恰好是 {want}（不加换行以外的任何字符）。做完后第一行只回复：没事可做：已写入。"
PROBE = "用 Bash 工具运行这条命令：printf '{\"t\":\"%s\"}\\n' \"$(date +%Y)\" > probe.json 。运行不了就直接说运行不了，不要尝试别的办法。第一行回复：没事可做：已处理。"
# 名称 -> (agent 配置, 期望的实际模型名片段)
AGENTS = {
    "claude-opus": ({"use": "claude", "model": "ai-code-with/claude-opus-5-5", "effort": "low", "access": "edit"}, "claude-opus-5-5"),
    "claude-sonnet": ({"use": "claude", "model": "ai-code-with/claude-sonnet-5-5", "effort": "low", "access": "edit"}, "claude-sonnet-5-5"),
    "codex": ({"use": "codex", "model": "gpt-6-sol", "effort": "low", "access": "edit"}, "gpt-6-sol"),
    "agy": ({"use": "command", "command": ["agy", "--model", "claude-sonnet-5-5-low", "-p", "{prompt}",
                                           "--dangerously-skip-permissions"]}, None),
}


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main(names):
    tmp = Path(tempfile.mkdtemp(prefix="autoloop-f1-"))
    home, port = tmp / "home", free_port()
    (tmp / "bin").mkdir()
    osa = tmp / "bin" / "osascript"
    osa.write_text("#!/bin/sh\nexit 0\n")
    osa.chmod(0o755)
    env = dict(os.environ, AGENT_AUTOLOOP_HOME=str(home), PATH=f"{tmp / 'bin'}:{os.environ['PATH']}")
    cmd = ["node", "--disable-warning=ExperimentalWarning", str(APP / "bin/agent-autoloop.ts")]
    al = lambda *a, t=60: subprocess.run(cmd + list(a), env=env, capture_output=True, text=True, timeout=t)
    al("init", "--command", "true {prompt}", "--no-service", "--port", str(port))
    rules = json.loads((home / "rules.json").read_text())
    worker = rules["agents"]["agent"]["worker"]
    rules["agents"] = {n: dict(AGENTS[n][0], name=n, worker=worker, timeout=6) for n in names if n in AGENTS}
    rules["agents"]["claude-probe"] = dict(AGENTS["claude-sonnet"][0], name="probe", worker=worker, timeout=6)
    rules["rules"] = []
    work = {}
    for n in list(names):
        d = tmp / "work" / n
        d.mkdir(parents=True)
        work[n] = d
        agent, prompt = ("claude-probe", PROBE) if n == "probe" else (n, TASK.format(want=f"hello-{n}"))
        rules["rules"].append({"name": n, "when": {"source": "local", "types": [f"f1.{n}"]}, "to": agent,
                               "cwd": str(d), "prompt": prompt})
    (home / "rules.json").write_text(json.dumps(rules, ensure_ascii=False, indent=1))
    hub = subprocess.Popen(cmd + ["up"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    out = {}
    try:
        for _ in range(100):
            with socket.socket() as s:
                s.settimeout(0.5)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    break
            time.sleep(0.1)
        chk = al("check")
        print("规则检查:", (chk.stdout + chk.stderr).strip()[:200])
        for i, n in enumerate(names, 1):  # 一个接一个跑，互不占预算
            al("emit", f"f1.{n}", "--id", f"f1-{n}", "--subject", n, "--summary", n)
            why = ""
            for _ in range(400):  # 最多约 8 分钟
                why = al("why", str(i)).stdout
                if "结束" in why:
                    break
                time.sleep(1.2)
            out[n] = (i, why)
        for n, (i, why) in out.items():
            report(n, i, why, work[n], home, al)
    finally:
        try:
            os.killpg(hub.pid, signal.SIGTERM)
            hub.wait(timeout=10)
        except (ProcessLookupError, PermissionError, subprocess.TimeoutExpired):
            pass
    print(f"\n日志与数据目录保留在 {tmp}（含 home/worker/runs/*/stdout-1.log）")


def model_of(home, i):
    """运行目录名是 <轮次>-<尝试>；Claude 的 stream-json 开头带实际模型名。"""
    log = home / "worker" / "runs" / f"{i}-1" / "stdout-1.log"
    if not log.exists():
        return None, None
    m = re.search(r'"model":"([^"]*)"', log.read_text(errors="replace"))
    return (m.group(1) if m else None), str(log)


def report(n, i, why, d, home, al):
    first = next((l for l in why.splitlines() if "结束" in l), "")
    ended = bool(first) and "没跑成" not in first and "待你处理" not in first
    if n == "probe":
        print(f"[{n}] 探针: {'结束(拒绝或已执行)' if first else '挂起'}  probe.json存在={ (d/'probe.json').exists() }  {first[-60:]}")
        return
    want = f"hello-{n}"
    f = d / "out.txt"
    content_ok = f.exists() and f.read_text() in (want, want + "\n")
    cfg_model, frag = AGENTS[n][0].get("model"), AGENTS[n][1]
    actual, evid = model_of(home, i)
    if frag is None or actual is None:
        model_state = "未验证(日志里没找到实际模型名)"
    else:
        model_state = "通过" if frag in actual else f"失败(实际 {actual})"
    usage = "有" if re.search(r'"usage":\s*\{', al("why", str(i), "--json").stdout) else "无"
    print(f"[{n}] 正常结束:{'通过' if ended else '失败'}  文件内容:{'通过' if content_ok else '失败'}"
          f"  实际模型:{model_state}  用量记录:{usage}  证据:{evid or d}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["claude-opus", "claude-sonnet", "codex", "agy", "probe"]))
