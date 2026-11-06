"""由模板请求的确定性步骤：检查、发布候选、使用验证和正式发布。"""
import json
import os
import re
import signal
import subprocess
from pathlib import Path

from cockpit.store import atomic_write, now_iso
from cockpit.workdir import WorkdirError, checkpoint, head, tag


def _done(run_dir, state, spec, verdict, summary):
    folder = Path(run_dir) / state["step"]["dir"]
    folder.mkdir(parents=True, exist_ok=True)
    data = {"schema_version": 1, "id": state["id"], "stage": state["stage"],
            "round": state["round"], "role": state["step"]["role"], "verdict": verdict,
            "summary": summary, "outputs": list(spec.get("outputs", [])), "finished_at": now_iso()}
    atomic_write(folder / "done.json", json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return data


def _base_env(scratch):
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL", "SYSTEMROOT")}
    env.update(HOME=str(scratch), TMPDIR=str(scratch), TMP=str(scratch), TEMP=str(scratch))
    return env


def _expand(value, scratch):
    return str(value).replace("{scratch}", str(scratch))


def _run(command, cwd, env, timeout):
    try:
        proc = subprocess.Popen(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, start_new_session=True)
    except OSError as e:
        return 126, f"{type(e).__name__}: {e}\n"
    try:
        output, _ = proc.communicate(timeout=timeout)
        return proc.returncode, output
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        output, _ = proc.communicate()
        return 124, output + "\n超时，已终止进程组。\n"


def run_check(run_dir, state, spec):
    workdir = Path(state["workdir"])
    folder = Path(run_dir) / state["step"]["dir"]
    scratch = folder / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    command = spec.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
        log, verdict = "拒绝：检查命令必须是非空字符串列表。\n", "BLOCK"
    else:
        rc, output = _run(command, workdir, _base_env(scratch), spec.get("timeout_seconds", 180))
        log = f"$ {' '.join(command)}\n退出码：{rc}\n{output}"
        ran = re.search(r"Ran\s+(\d+)\s+tests?", output)
        verdict = "PASS" if rc == 0 and ran and int(ran.group(1)) > 0 else "FAIL"
        if rc == 0 and not ran:
            log += "\n未发现 unittest 的非零测试数，拒绝将空检查记为通过。\n"
    atomic_write(folder / "check.log", log)
    _done(run_dir, state, spec, verdict, "检查通过" if verdict == "PASS" else "检查未通过")
    return verdict


def run_usage(run_dir, state, spec):
    workdir = Path(state["workdir"])
    folder = Path(run_dir) / state["step"]["dir"]
    scratch = folder / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    env = _base_env(scratch)
    env.update({k: _expand(v, scratch) for k, v in spec.get("env", {}).items()})
    script = spec.get("script")
    verdict, lines = "PASS", []
    if not isinstance(script, list) or not script:
        verdict = "BLOCK"
        lines.append("拒绝：使用脚本必须是非空列表。")
    else:
        for i, step in enumerate(script, 1):
            command = step.get("cmd") if isinstance(step, dict) else None
            if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
                verdict = "BLOCK"
                lines.append(f"步骤 {i}: 使用脚本命令格式无效。")
                break
            step_env = env.copy()
            for name in step.get("unset", []):
                step_env.pop(name, None)
            command = [_expand(x, scratch) for x in command]
            rc, output = _run(command, workdir, step_env, step.get("timeout_seconds", spec.get("timeout_seconds", 30)))
            lines.append(f"步骤 {i}: {' '.join(command)}\n退出码：{rc}\n{output}")
            want_rc = step.get("rc", 0)
            ok_rc = (rc != 0) if want_rc == "nonzero" else rc == want_rc
            ok = ok_rc
            ok = ok and all(term in output for term in step.get("contains", []))
            ok = ok and all(term not in output for term in step.get("not_contains", []))
            expected = step.get("expect_file")
            if expected:
                ok = ok and Path(_expand(expected, scratch)).is_file()
            if not ok:
                verdict = "FAIL"
                lines.append(f"步骤 {i} 未达到预期，后续步骤停止。")
                break
    log = "\n\n".join(lines) + "\n"
    atomic_write(folder / "usage.log", log)
    _done(run_dir, state, spec, verdict, "使用验证通过" if verdict == "PASS" else "使用验证未通过")
    return verdict


def run_release(run_dir, state, spec):
    workdir = Path(state["workdir"])
    folder = Path(run_dir) / state["step"]["dir"]
    mode, version = spec.get("tag"), spec.get("version", "0.1.0")
    try:
        if mode == "rc":
            tags = subprocess.run(["git", "-C", str(workdir), "tag", "--list", f"v{version}-rc.*"],
                                  text=True, capture_output=True, check=True).stdout.splitlines()
            nums = [int(m.group(1)) for t in tags if (m := re.fullmatch(rf"v{re.escape(version)}-rc\.(\d+)", t))]
            name = f"v{version}-rc.{max(nums, default=0) + 1}"
        elif mode == "final":
            name = f"v{version}"
            if name in subprocess.run(["git", "-C", str(workdir), "tag", "--list"],
                                      text=True, capture_output=True, check=True).stdout.splitlines():
                raise WorkdirError(f"标签已存在：{name}")
            changelog = workdir / "CHANGELOG.md"
            if not changelog.exists():
                changelog.write_text(f"# Changelog\n\n## {name}\n\n- {spec.get('note', '发布')}\n", encoding="utf-8")
            checkpoint(workdir, f"Release {name}")
        else:
            raise WorkdirError(f"未知发布标签类型：{mode}")
        tag(workdir, name)
        verdict, log = "PASS", f"本地标签：{name}\n提交：{head(workdir)}\n未推送、未部署。\n"
    except (WorkdirError, subprocess.SubprocessError, OSError) as e:
        verdict, log = "BLOCK", f"发布失败：{e}\n"
    atomic_write(folder / "release.log", log)
    _done(run_dir, state, spec, verdict, log.splitlines()[0])
    return verdict


def run_tool(run_dir, state, template):
    spec = template["stages"][state["stage"]]
    name = spec.get("tool")
    if name == "check":
        return run_check(run_dir, state, spec)
    if name == "usage":
        return run_usage(run_dir, state, spec)
    if name == "release":
        return run_release(run_dir, state, spec)
    raise ValueError(f"未知程序步骤：{name}")
