"""F0 冒烟：在临时数据目录里用假 Agent 把 agent-autoloop 跑一遍，不花额度。

用法：python3 tests/smoke_autoloop.py            # 全部通过退出 0，否则退出 1
环境变量 AUTOLOOP_APP 指向上游检出目录，默认 ~/code/agent-autoloop（锁定提交 8f8e2ee）。
"""
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

APP = Path(os.environ.get("AUTOLOOP_APP", "~/code/agent-autoloop")).expanduser()
PINNED = "8f8e2eef3cfaa8f7a418818adc442450fe6bd884"
REAL_HOME = Path.home()
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(ok)
    print(f"{'通过' if ok else '失败'}  {name}" + (f"  [{detail}]" if detail and not ok else ""))
    return ok


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def listening(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main():
    tmp = Path(tempfile.mkdtemp(prefix="autoloop-smoke-"))
    home, port = tmp / "home", free_port()
    (tmp / "bin").mkdir()
    agent = tmp / "bin" / "fake-agent.sh"
    agent.write_text('#!/bin/sh\necho "没事可做：冒烟收到提示词"\n')
    osa = tmp / "bin" / "osascript"  # 拦住桌面通知，不弹真实通知
    osa.write_text(f'#!/bin/sh\necho "$@" >> {tmp}/notify.log\n')
    for f in (agent, osa):
        f.chmod(0o755)
    env = dict(os.environ, AGENT_AUTOLOOP_HOME=str(home), PATH=f"{tmp / 'bin'}:{os.environ['PATH']}")

    before = {p: p.exists() for p in (REAL_HOME / ".agent-autoloop", REAL_HOME / ".claude/skills/agent-autoloop",
                                      REAL_HOME / ".codex/skills/agent-autoloop")}

    def al(*args, timeout=30):
        return subprocess.run(["node", "--disable-warning=ExperimentalWarning", str(APP / "bin/agent-autoloop.ts"), *args],
                              env=env, capture_output=True, text=True, timeout=timeout)

    hub = None
    try:
        head = subprocess.run(["git", "-C", str(APP), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        check("上游检出锁定在 8f8e2ee", head == PINNED, head)
        r = al("init", "--command", f"{agent} {{prompt}}", "--no-service", "--port", str(port))
        check("init 成功", r.returncode == 0, r.stderr or r.stdout)
        hub = subprocess.Popen(["node", "--disable-warning=ExperimentalWarning", str(APP / "bin/agent-autoloop.ts"), "up"],
                               env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        for _ in range(100):
            if listening(port):
                break
            time.sleep(0.1)
        check("中台开始监听", listening(port))
        doc = al("doctor").stdout
        check("doctor 显示中台和 Agent 在线", "● 中台" in doc and "● Agent" in doc, doc)
        r = al("emit", "try.smoke", "--id", "smoke-1", "--subject", "smoke", "--summary", "冒烟")
        check("emit 被规则接住", "交给了" in r.stdout, r.stdout + r.stderr)
        why = ""
        for _ in range(100):
            why = al("why", "1").stdout
            if "结束" in why:
                break
            time.sleep(0.2)
        check("第 1 轮有领取和结束", "领取" in why and "结束" in why, why)
        al("emit", "try.smoke", "--id", "smoke-1", "--subject", "smoke", "--summary", "冒烟")
        time.sleep(1)
        check("重复 id 不产生第 2 轮", "没有这一轮" in (al("why", "2").stdout + al("why", "2").stderr))
    finally:
        if hub and hub.poll() is None:  # 已经退出的不再发信号：进程组可能不存在，pid 也可能已被复用
            try:
                os.killpg(hub.pid, signal.SIGTERM)
                hub.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(hub.pid, signal.SIGKILL)
            except OSError:
                pass
        time.sleep(0.5)
        check("结束后端口已释放", not listening(port))
        check("结束后中台进程已退出", hub is None or hub.poll() is not None)
        after = {p: p.exists() for p in before}
        check("真实数据目录和技能链接没被动过", after == before, str(after))
        shutil.rmtree(tmp, ignore_errors=True)
    bad = RESULTS.count(False)
    print(f"\n{'全部通过' if not bad else f'{bad} 项失败'}（共 {len(RESULTS)} 项）")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
