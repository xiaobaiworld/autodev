# 定位: config.py 需求分析模块与专属飞书机器人配置解析（支持模型配置与调用方式）。
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReqConfig:
    app_id: str
    app_secret: str
    allow_users: set[str]
    allow_dirs: tuple[str, ...]
    default_agent: str
    default_mode: str
    default_cwd: str
    task_timeout: int
    output_limit: int
    autoloop_home: str = "/tmp/autodev-demo/home"


def load_req_config(path: str | Path) -> ReqConfig:
    raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    feishu = raw.get("feishu", {})
    allow = raw.get("allow", {})
    llm = raw.get("llm", {})
    raw_agent = llm.get("default_model") or raw.get("default_agent", "claude-sonnet")
    if raw_agent == "cc":
        raw_agent = "claude-sonnet"
    default_mode = llm.get("default_mode") or raw.get("default_mode", "cli_session")
    return ReqConfig(
        app_id=feishu.get("app_id", ""),
        app_secret=feishu.get("app_secret", ""),
        allow_users=set(allow.get("users", [])),
        allow_dirs=tuple(os.path.expanduser(d) for d in allow.get("dirs", [])),
        default_agent=raw_agent,
        default_mode=default_mode,
        default_cwd=os.path.expanduser(raw.get("default_cwd", os.getcwd())),
        task_timeout=int(raw.get("task_timeout", 1800)),
        output_limit=int(raw.get("output_limit", 3500)),
        autoloop_home=os.path.expanduser(raw.get("autoloop_home", "/tmp/autodev-demo/home")),
    )
