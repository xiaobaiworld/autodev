# 定位: llm_provider.py 独立的大模型注册表与多模式调用层（遵循 docs/MODELS.md 完整模型 ID 规范，支持 cli_session 与 cli_stateless）。
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cockpit.agents import parse_agents

log = logging.getLogger("autodev.req")

INVOCATION_MODES = ("cli_session", "cli_stateless")
FORBIDDEN_ALIASES = {"sonnet", "opus", "haiku", "claude", "gpt", "gemini", "default"}

# 兼容旧配置或常用代号的映射
LEGACY_AGENT_MAP = {
    "cc": "claude-sonnet",
    "claude": "claude-sonnet",
    "gpt": "codex",
    "gemini": "agy",
}

DEFAULT_CONFIG_YAML = Path(__file__).resolve().parents[2] / "config.yaml"


@dataclass(frozen=True)
class ModelSpec:
    name: str
    cli: str
    vendor: str
    model: str
    effort: str = "medium"

    @property
    def full_model_id(self) -> str:
        return self.model

    def validate(self) -> None:
        if not self.model or self.model.lower() in FORBIDDEN_ALIASES:
            raise ValueError(
                f"模型配置 {self.name!r} 使用了被禁止的短别名 {self.model!r}，必须使用完整模型 ID（见 docs/MODELS.md）"
            )
        if self.cli not in ("claude", "codex", "agy"):
            raise ValueError(f"模型配置 {self.name!r} 的 cli 未知: {self.cli!r}")


@dataclass(frozen=True)
class LLMInvokeResult:
    ok: bool
    reply: str
    session_id: str
    model_name: str
    full_model_id: str
    vendor: str
    mode: str
    duration_sec: float
    error: str = ""


BUILTIN_FALLBACK_SPECS: dict[str, ModelSpec] = {
    "claude-sonnet": ModelSpec(
        name="claude-sonnet",
        cli="claude",
        vendor="anthropic",
        model="ai-code-with/claude-sonnet-5-5",
        effort="medium",
    ),
    "claude-opus": ModelSpec(
        name="claude-opus",
        cli="claude",
        vendor="anthropic",
        model="ai-code-with/claude-opus-5-5",
        effort="high",
    ),
    "codex": ModelSpec(
        name="codex",
        cli="codex",
        vendor="openai",
        model="gpt-6-sol",
        effort="low",
    ),
    "agy": ModelSpec(
        name="agy",
        cli="agy",
        vendor="google",
        model="gemini-4-argon-high",
        effort="high",
    ),
}


def load_model_registry(config_yaml_path: str | Path | None = None) -> dict[str, ModelSpec]:
    """从项目的 config.yaml 读取模型注册表，确保完整模型 ID 唯一真源。"""
    registry = dict(BUILTIN_FALLBACK_SPECS)
    target = Path(config_yaml_path) if config_yaml_path else DEFAULT_CONFIG_YAML
    if target.is_file():
        try:
            raw_agents = parse_agents(target.read_text(encoding="utf-8"))
            for name, cfg in raw_agents.items():
                spec = ModelSpec(
                    name=name,
                    cli=cfg.get("cli", ""),
                    vendor=cfg.get("vendor", ""),
                    model=cfg.get("model", ""),
                    effort=cfg.get("effort", "medium"),
                )
                spec.validate()
                registry[name] = spec
        except Exception as e:
            log.warning("解析 config.yaml 模型注册表失败 (%s)，使用内置完整 ID 注册表", e)
    return registry


def resolve_model_spec(
    agent_or_model_name: str,
    registry: dict[str, ModelSpec] | None = None,
) -> ModelSpec:
    """将配置的代号（如 'cc'、'claude-sonnet'、'codex'）解析为经过校验的 ModelSpec。"""
    reg = registry or load_model_registry()
    normalized = LEGACY_AGENT_MAP.get(agent_or_model_name.strip(), agent_or_model_name.strip())
    if normalized in reg:
        spec = reg[normalized]
        spec.validate()
        return spec
    raise ValueError(
        f"未注册的模型名称 {agent_or_model_name!r}。可选模型: {', '.join(sorted(reg.keys()))}"
    )


def inject_stateless_history(prompt: str, history: list[dict[str, str]] | None) -> str:
    """在无状态模式（cli_stateless）或跨模型切换时，将最近的历史对话上下文合成到 Prompt 中。"""
    if not history:
        return prompt
    lines = ["【前序多轮对话上下文（供本轮衔接参考）】"]
    for idx, turn in enumerate(history[-6:], start=1):
        u = turn.get("user", "").strip()
        a = turn.get("assistant", "").strip()
        if u:
            lines.append(f"- 第 {idx} 轮用户输入：{u[:300]}")
        if a:
            lines.append(f"  第 {idx} 轮分析师结论：{a[:400]}")
    lines.append("")
    lines.append(prompt)
    return "\n".join(lines)


def build_model_argv(
    spec: ModelSpec,
    prompt: str,
    cwd: str,
    session_id: str | None = None,
    mode: str = "cli_session",
    history: list[dict[str, str]] | None = None,
) -> list[str]:
    """根据独立的 ModelSpec 和调用模式（cli_session / cli_stateless）生成只读沙箱命令参数。"""
    if mode not in INVOCATION_MODES:
        raise ValueError(f"不支持的调用模式 {mode!r}，可选: {INVOCATION_MODES}")
    spec.validate()

    use_session = (mode == "cli_session") and bool(session_id)
    effective_prompt = prompt if use_session else inject_stateless_history(prompt, history)

    if spec.cli == "claude":
        argv = [
            "claude",
            "--model", spec.model,
            "-p", effective_prompt,
            "--permission-mode", "plan",
            "--output-format", "json",
        ]
        if use_session and session_id:
            argv.extend(["--resume", session_id])
        return argv

    if spec.cli == "codex":
        effort_arg = f"model_reasoning_effort={spec.effort}"
        if use_session and session_id:
            return [
                "codex", "exec", "resume",
                "-m", spec.model,
                "-c", effort_arg,
                "-c", 'sandbox_mode="read-only"',
                "--skip-git-repo-check", "--json",
                session_id, effective_prompt,
            ]
        return [
            "codex", "exec",
            "-C", cwd,
            "-s", "read-only",
            "-m", spec.model,
            "-c", effort_arg,
            "--skip-git-repo-check", "--json",
            effective_prompt,
        ]

    if spec.cli == "agy":
        return [
            "agy",
            "--model", spec.model,
            "-p", effective_prompt,
            "--mode", "plan",
        ]

    raise ValueError(f"未知 CLI 类型: {spec.cli}")
