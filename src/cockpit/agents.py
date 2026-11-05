"""从 config.yaml 读 agents、roles，并生成各 CLI 的启动命令（模型规则见 docs/MODELS.md）。
# ponytail: 正则读固定格式，和 config.py 一样；config 变复杂时改 JSON 或引入解析库。
"""
import re
import shlex


def _section(text, name):
    m = re.search(rf"^{name}:[^\n]*\n((?:[ \t]+[^\n]*\n?|\n)*)", text, re.M)
    if not m:
        raise ValueError(f"config.yaml 缺少 {name} 段")
    return re.sub(r"[ \t]+#.*", "", m.group(1))


def parse_agents(text):
    out, cur = {}, None
    for line in _section(text, "agents").splitlines():
        m = re.match(r"^  (\S+):\s*$", line)
        if m:
            cur = out.setdefault(m.group(1), {})
            continue
        m = re.match(r"^    (\w+):\s*(\S.*?)\s*$", line)
        if m and cur is not None:
            cur[m.group(1)] = m.group(2)
    return out


def parse_roles(text):
    out = {}
    for line in _section(text, "roles").splitlines():
        m = re.match(r"^\s+(\w+):\s*\{\s*agent:\s*(\S+?)\s*\}\s*$", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def launch_cmd(agent, workdir, writable=True, add_dirs=()):
    """agent: parse_agents 的一项。审查类角色 writable=False 时 Codex 用只读沙箱。
    add_dirs: Claude 只能读工作目录，input.md 引用的目录外文件要靠 --add-dir 放行（L008）。"""
    cli, model, effort = agent["cli"], agent["model"], agent.get("effort")
    if "/" in model and cli == "codex" and model.split("/")[0] not in ("codex", "ai-code-with"):
        raise ValueError(f"可疑的 Codex 模型名 {model}")
    if cli == "codex":
        sandbox = "workspace-write" if writable else "read-only"
        cmd = f"codex -m {shlex.quote(model)} "
        if effort:
            cmd += f"-c model_reasoning_effort={shlex.quote(effort)} "
        cmd += f"--sandbox {sandbox} --ask-for-approval never"
    elif cli == "claude":
        cmd = f"claude --permission-mode acceptEdits --model {shlex.quote(model)}"
        for d in add_dirs:
            cmd += f" --add-dir {shlex.quote(str(d))}"
    else:
        raise ValueError(f"P4 暂不支持 {cli}（agy 见 P5）")
    return f"cd {shlex.quote(str(workdir))} && {cmd}"


def parse_limits(text):
    """limits 段的整数项，如 step_retries、step_timeout_minutes。"""
    out = {}
    for line in _section(text, "limits").splitlines():
        m = re.match(r"^\s+(\w+):\s*(\d+)\s*$", line)
        if m:
            out[m.group(1)] = int(m.group(2))
    return out
