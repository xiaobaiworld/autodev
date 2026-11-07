# 定位: agent_runner.py 封装 Claude/Codex CLI 只读多轮调用与横幅过滤容错解析。
from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import time
from dataclasses import dataclass

log = logging.getLogger("autodev.req")


@dataclass(frozen=True)
class ParsedOutput:
    session_id: str = ""
    reply: str = ""
    error: str = ""


@dataclass(frozen=True)
class RunnerResult:
    ok: bool
    parsed: ParsedOutput
    duration_sec: float
    output: str


def build_argv(agent: str, prompt: str, cwd: str, session_id: str | None) -> list[str]:
    if agent == "cc":
        argv = ["claude", "-p", prompt, "--permission-mode", "plan", "--output-format", "json"]
        if session_id:
            argv.extend(["--resume", session_id])
        return argv
    if agent == "codex":
        if session_id:
            return [
                "codex", "exec", "resume",
                "-c", 'sandbox_mode="read-only"',
                "--skip-git-repo-check", "--json",
                session_id, prompt,
            ]
        return [
            "codex", "exec", "-C", cwd, "-s", "read-only",
            "--skip-git-repo-check", "--json", prompt,
        ]
    raise ValueError(f"未知 agent: {agent}")


def parse_claude_output(output: str, expected_id: str | None) -> ParsedOutput:
    payload = None
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        for line in reversed(output.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    payload = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
        if payload is None:
            start = output.find("{")
            end = output.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    payload = json.loads(output[start : end + 1])
                except json.JSONDecodeError:
                    pass

    if payload is None:
        return ParsedOutput(error="Claude 返回了非法 JSON")
    if not isinstance(payload, dict):
        return ParsedOutput(error="Claude JSON 不是对象")
    if payload.get("type") != "result" or payload.get("is_error") is True:
        return ParsedOutput(error="Claude 返回不是成功 result")
    session_id = payload.get("session_id")
    reply = payload.get("result")
    if not isinstance(session_id, str) or not session_id:
        return ParsedOutput(error="Claude 缺少会话 ID")
    if expected_id and session_id != expected_id:
        return ParsedOutput(error="Claude 续接会话 ID 不一致")
    if not isinstance(reply, str) or not reply.strip():
        return ParsedOutput(error="Claude 缺少最终回复")
    return ParsedOutput(session_id=session_id, reply=reply.strip())


def parse_codex_output(output: str, expected_id: str | None) -> ParsedOutput:
    session_id = expected_id or ""
    reply = ""
    turn_completed = False
    saw_json = False
    for line in output.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        saw_json = True
        if event.get("type") == "thread.started":
            candidate = event.get("thread_id")
            if isinstance(candidate, str) and candidate:
                session_id = candidate
        if event.get("type") == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    reply = text.strip()
        if event.get("type") == "turn.completed":
            turn_completed = True

    if not saw_json or not session_id or not turn_completed or not reply:
        return ParsedOutput(error="Codex 返回数据不完整")
    return ParsedOutput(session_id=session_id, reply=reply)


def run_agent_turn(
    agent: str, prompt: str, cwd: str, session_id: str | None, timeout: int = 1800
) -> RunnerResult:
    argv = build_argv(agent, prompt, cwd, session_id)
    start = time.monotonic()
    proc = subprocess.Popen(
        argv,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, _ = proc.communicate(timeout=timeout)
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass
        stdout, _ = proc.communicate()
        exit_code = -1

    duration = time.monotonic() - start
    output = stdout or ""

    if timed_out:
        return RunnerResult(
            ok=False,
            parsed=ParsedOutput(error=f"Agent 执行超时 (>{timeout}s)"),
            duration_sec=duration,
            output=output,
        )
    if exit_code != 0:
        return RunnerResult(
            ok=False,
            parsed=ParsedOutput(error=f"Agent 退出码异常 (code={exit_code})"),
            duration_sec=duration,
            output=output,
        )

    if agent == "cc":
        parsed = parse_claude_output(output, session_id)
    else:
        parsed = parse_codex_output(output, session_id)

    return RunnerResult(
        ok=not bool(parsed.error),
        parsed=parsed,
        duration_sec=duration,
        output=output,
    )
