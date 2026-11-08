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
    executable: str = ""
    supported_tasks: tuple[str, ...] = ()
    unsupported_tasks: tuple[str, ...] = ()
    unverified_tasks: tuple[str, ...] = ()
    capability_notes: str = ""
    auth: dict | None = None
    invocation_mode: str = 'cli_session'

    @property
    def full_model_id(self) -> str:
        return self.model

    def validate(self) -> None:
        if not self.model or self.model.lower() in FORBIDDEN_ALIASES:
            raise ValueError(
                f"模型配置 {self.name!r} 使用了被禁止的短别名 {self.model!r}，必须使用完整模型 ID（见 docs/MODELS.md）"
            )
        if self.cli not in ("claude", "codex", "agy", "ollama"):
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


def load_model_registry(config_yaml_path: str | Path | None = None) -> dict[str, ModelSpec]:
    """Read configured models only; invalid catalogs never enable hidden fallbacks."""
    target = Path(config_yaml_path) if config_yaml_path else DEFAULT_CONFIG_YAML
    raw_agents = parse_agents(target.read_text(encoding="utf-8"))
    registry = {}
    for name, cfg in raw_agents.items():
        spec = ModelSpec(name=name, cli=cfg.get("cli", ""), vendor=cfg.get("vendor", ""),
                         model=cfg.get("model", ""), effort=cfg.get("effort", "medium"),
                         executable=cfg.get("executable", cfg.get("cli", "")),
                         supported_tasks=tuple(cfg.get("supported_tasks", [])),
                         unsupported_tasks=tuple(cfg.get("unsupported_tasks", [])),
                         unverified_tasks=tuple(cfg.get("unverified_tasks", [])),
                         capability_notes=cfg.get("capability_notes", ""), auth=cfg.get("auth"),
                         invocation_mode=cfg.get('invocation_mode', 'cli_session'))
        spec.validate()
        registry[name] = spec
    return registry


def resolve_model_spec(
    agent_or_model_name: str,
    registry: dict[str, ModelSpec] | None = None,
) -> ModelSpec:
    """将配置的代号（如 'cc'、'claude-sonnet'、'codex'）解析为经过校验的 ModelSpec。"""
    reg = registry if registry is not None else load_model_registry()
    requested = agent_or_model_name.strip()
    normalized = requested if requested in reg else LEGACY_AGENT_MAP.get(requested, requested)
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
    mode: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> list[str]:
    """根据独立的 ModelSpec 和调用模式（cli_session / cli_stateless）生成只读沙箱命令参数。"""
    mode = mode or spec.invocation_mode
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
        return [spec.executable or spec.cli, *argv[1:]]

    if spec.cli == "codex":
        effort_arg = f"model_reasoning_effort={spec.effort}"
        if use_session and session_id:
            return [
                spec.executable or "codex", "exec", "resume",
                "-m", spec.model,
                "-c", effort_arg,
                "-c", 'sandbox_mode="read-only"',
                "--skip-git-repo-check", "--json",
                session_id, effective_prompt,
            ]
        return [
            spec.executable or "codex", "exec",
            "-C", cwd,
            "-s", "read-only",
            "-m", spec.model,
            "-c", effort_arg,
            "--skip-git-repo-check", "--json",
            effective_prompt,
        ]

    if spec.cli == "agy":
        return [
            spec.executable or "agy",
            "--model", spec.model,
            "-p", effective_prompt,
            "--mode", "plan",
        ]

    if spec.cli == "ollama":
        if mode != 'cli_stateless':
            raise ValueError('ollama 仅支持无状态文本调用')
        return [spec.executable or 'ollama', 'run', spec.model, effective_prompt]

    raise ValueError(f"未知 CLI 类型: {spec.cli}")
