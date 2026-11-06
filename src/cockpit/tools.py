"""程序步骤用的工具：不调用 Agent，直接由程序执行并给出结论。每个工具的返回值固定为
{"verdict": ..., "summary": 一两句话, "outputs": [产物文件名]}，产物文件由工具写进步骤目录 sd。

check：在代码目录里跑检查命令（模板里的 command，不经过 shell），退出码为 0 且确实跑了测试才算 PASS。

安全：它执行的是 Agent 刚写出来的代码，而且在 Agent 自己的沙箱之外。能做的隔离只有这些——
最小环境变量（不带用户的密钥和令牌）、HOME 和临时目录指向步骤目录下的草稿目录（测试默认写 ~ 时不会碰真实的用户目录）、
不经过 shell、超时后杀整个进程组、输出只留尾部。它挡不住网络访问，也挡不住对其他绝对路径的写入。
# ponytail: 要真正隔离需要容器或 sandbox-exec，等检查命令开始跑不可信的大项目时再加。
"""
import os
import re
import signal
import subprocess
from pathlib import Path

from cockpit.store import atomic_write

MAX_LOG = 200_000
EMPTY_RUN = re.compile(r"Ran 0 tests|NO TESTS RAN", re.I)  # 空的测试集退出码可能是 0，但那不叫通过


def _clean_env(scratch):
    keep = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL")}
    return {**keep, "HOME": str(scratch), "TMPDIR": str(scratch), "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": "src"}


def run_check(workdir, sd, spec, timeout_s):
    """spec["command"] 是命令列表，例如 ["python3", "-m", "unittest", "discover", "-s", "tests"]。"""
    command = spec["command"]
    if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
        raise ValueError("检查命令必须是字符串列表（不经过 shell）")
    sd = Path(sd)
    scratch = sd / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(command, cwd=workdir, env=_clean_env(scratch), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, errors="replace", start_new_session=True)
    timed_out = False
    try:
        out, _ = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(proc.pid, signal.SIGKILL)
        out, _ = proc.communicate()
    tail = out[-MAX_LOG:] if len(out) > MAX_LOG else out
    head = f"$ {' '.join(command)}\n(cwd {workdir})\n"
    code = proc.returncode
    atomic_write(sd / "check.log", f"{head}\n{tail}\n[退出码 {code}{'，超时被杀' if timed_out else ''}]\n")
    if timed_out:
        return {"verdict": "FAIL", "summary": f"检查超过 {int(timeout_s)} 秒被终止。", "outputs": ["check.log"]}
    if code != 0:
        return {"verdict": "FAIL", "summary": f"检查命令退出码 {code}，详见 check.log。", "outputs": ["check.log"]}
    if EMPTY_RUN.search(out):
        return {"verdict": "FAIL", "summary": "检查命令退出码 0，但一个测试都没有跑，不算通过。", "outputs": ["check.log"]}
    return {"verdict": "PASS", "summary": "检查命令退出码 0，测试通过。", "outputs": ["check.log"]}


TOOLS = {"check": lambda ctx: run_check(ctx["workdir"], ctx["sd"], ctx["spec"], ctx["timeout_s"])}
