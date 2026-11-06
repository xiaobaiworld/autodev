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
import shlex
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


def run_release(workdir, sd, spec, state):
    """S7 发布候选（tag="rc"）与 S9 正式发布（tag="final"）：在代码目录的 git 仓库里打标签并写日志。
    版本号取模板 spec["version"]（如 "0.1.0"）；候选标签 v0.1.0-rc.1（序号取已有 rc 标签的最大值加一），正式标签 v0.1.0。
    正式发布还把一条记录追加到代码目录的 CHANGELOG.md。已有同名正式标签就拒绝（BLOCK），不覆盖。
    # ponytail: 只在本地 git 里打标签，不推送、不部署；接真实项目（personagent）时再加推送，那时必须先问人。"""
    from cockpit.workdir import GitError, add_tag, commit_all, list_tags
    kind = spec["tag"]
    if kind not in ("rc", "final"):
        raise ValueError(f"release 工具的 tag 只能是 rc 或 final，收到 {kind!r}")
    version = str(spec.get("version") or "").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError(f"version 必须是 x.y.z，收到 {version!r}")
    log, tags = [], list_tags(workdir)
    if kind == "rc":
        nums = [int(m.group(1)) for t in tags if (m := re.fullmatch(rf"v{re.escape(version)}-rc\.(\d+)", t))]
        tag = f"v{version}-rc.{max(nums, default=0) + 1}"
    else:
        tag = f"v{version}"
        if tag in tags:
            atomic_write(Path(sd) / "release.log", f"正式标签 {tag} 已存在，不覆盖。\n")
            return {"verdict": "BLOCK", "summary": f"正式标签 {tag} 已存在，拒绝覆盖，需要人来决定。", "outputs": ["release.log"]}
        entry = f"## {tag}\n\n- 需求 {state['id']}：{spec.get('note') or '见需求记录'}\n"
        path = Path(workdir) / "CHANGELOG.md"
        path.write_text((path.read_text(encoding="utf-8") if path.exists() else "# CHANGELOG\n\n") + entry + "\n", encoding="utf-8")
        log.append(f"写入 CHANGELOG.md：{entry.strip()}")
    commit = commit_all(workdir, f"{state['id']} {tag}")
    add_tag(workdir, tag, f"{state['id']} {tag}")
    log.append(f"提交 {commit}，标签 {tag}")
    atomic_write(Path(sd) / "release.log", "\n".join(log) + "\n")
    return {"verdict": "PASS", "summary": f"已在代码目录打标签 {tag}（只在本地，未推送）。", "outputs": ["release.log"]}


def validate_usage_script(script):
    """使用脚本的格式检查，模板加载时和运行时都用。脚本是 [{"cmd": [...], "rc": 0|"nonzero", "contains": [...], ...}, ...]。"""
    if not isinstance(script, list) or not script:
        raise ValueError("使用脚本 script 必须是非空列表")
    for i, st in enumerate(script, 1):
        if not isinstance(st, dict):
            raise ValueError(f"使用脚本第 {i} 步必须是对象")
        cmd = st.get("cmd")
        if not (isinstance(cmd, list) and cmd and all(isinstance(x, str) for x in cmd)):
            raise ValueError(f"使用脚本第 {i} 步的 cmd 必须是非空的字符串列表（不经过 shell）")
        rc = st.get("rc", 0)
        if not ((isinstance(rc, int) and not isinstance(rc, bool)) or rc == "nonzero"):
            raise ValueError(f"使用脚本第 {i} 步的 rc 必须是整数或 \"nonzero\"")
        for key in ("contains", "not_contains", "unset"):
            v = st.get(key, [])
            if not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
                raise ValueError(f"使用脚本第 {i} 步的 {key} 必须是字符串列表")
        if "expect_file" in st and not isinstance(st["expect_file"], str):
            raise ValueError(f"使用脚本第 {i} 步的 expect_file 必须是字符串")


def run_usage(workdir, sd, spec, timeout_s):
    """S7U 使用验证：按模板里的使用脚本，在隔离环境里把做出来的东西真的用一遍，输出原样写进 usage.log，作为验收者的输入。
    脚本由人写在模板里，Agent 改不了。命令不存在或不可执行算“用不了”（FAIL），不是工具出错：这正是最该被抓住的那类问题。
    隔离和 check 一样：最小环境变量、HOME 与临时目录指向草稿目录（{scratch}）、不经过 shell、超时杀进程组；
    挡不住网络，也挡不住对其他绝对路径的写入。第一步不符合预期就停，后面的步骤依赖前面的结果，继续跑只会产生噪音。"""
    script = spec.get("script")
    validate_usage_script(script)
    sd = Path(sd)
    scratch = sd / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    fill = lambda s: s.replace("{scratch}", str(scratch))
    base = _clean_env(scratch)
    base.pop("PYTHONPATH", None)                      # 要验的是“拿到手怎么用”，不借我们的 PYTHONPATH
    per_step = max(1, min(30, int(timeout_s)))
    lines = [f"使用验证（cwd {workdir}，HOME={scratch}）"]
    failure = None
    for i, st in enumerate(script, 1):
        env = dict(base)
        for k, v in {**(spec.get("env") or {}), **(st.get("env") or {})}.items():
            env[k] = fill(v)
        for k in st.get("unset", []):
            env.pop(k, None)
        cmd = [fill(x) for x in st["cmd"]]
        if "/" in cmd[0] and not os.path.isabs(cmd[0]):
            cmd[0] = str(Path(workdir) / cmd[0])
        lines.append(f"\n[{i}/{len(script)}] $ {shlex.join(cmd)}")
        try:
            proc = subprocess.Popen(cmd, cwd=workdir, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, errors="replace", start_new_session=True)
        except (FileNotFoundError, PermissionError, NotADirectoryError) as e:
            lines.append(f"  无法启动：{e}")
            failure = f"第 {i} 步命令不存在或不可执行（{st['cmd'][0]}）"
            lines.append("  ✗ " + failure + "\n  后面的步骤没有运行")
            break
        timed_out = False
        try:
            out, _ = proc.communicate(timeout=per_step)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGKILL)
            out, _ = proc.communicate()
        code, shown = proc.returncode, (out if len(out) <= 4000 else out[:2000] + "\n…（中间省略）…\n" + out[-2000:])
        lines.append("".join("  " + l + "\n" for l in shown.splitlines()).rstrip("\n") or "  （没有输出）")
        lines.append(f"  [退出码 {code}{'，超时被杀' if timed_out else ''}]")
        problems = ["超时被杀"] if timed_out else []
        want = st.get("rc", 0)
        if want == "nonzero":
            if code == 0:
                problems.append("期望非零退出码，实际是 0")
        elif code != want:
            problems.append(f"期望退出码 {want}，实际是 {code}")
        problems += [f"输出里没有 {s!r}" for s in st.get("contains", []) if fill(s) not in out]
        problems += [f"输出里不该有 {s!r}" for s in st.get("not_contains", []) if fill(s) in out]
        if "expect_file" in st and not Path(fill(st["expect_file"])).exists():
            problems.append(f"应该生成的文件不存在：{fill(st['expect_file'])}")
        if problems:
            failure = f"第 {i} 步不符合预期：{problems[0]}"
            lines.append("  ✗ " + "；".join(problems) + "\n  后面的步骤没有运行")
            break
        lines.append("  ✓")
    atomic_write(sd / "usage.log", "\n".join(lines) + "\n")
    if failure:
        return {"verdict": "FAIL", "summary": failure + "，详见 usage.log。", "outputs": ["usage.log"]}
    return {"verdict": "PASS", "summary": f"使用脚本 {len(script)} 步全部符合预期（隔离的 HOME 与数据文件）。", "outputs": ["usage.log"]}


TOOLS = {"usage": lambda ctx: run_usage(ctx["workdir"], ctx["sd"], ctx["spec"], ctx["timeout_s"]),
         "check": lambda ctx: run_check(ctx["workdir"], ctx["sd"], ctx["spec"], ctx["timeout_s"]),
         "release": lambda ctx: run_release(ctx["workdir"], ctx["sd"], ctx["spec"], ctx["state"])}
