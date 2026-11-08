"""登记供 AutoDev 使用的项目，并保持 config.yaml 可被现有解析器读取。"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from cockpit.store import atomic_write


class RegistryError(ValueError):
    """项目登记失败，消息可直接展示给用户。"""


def _version_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _entries(text: str) -> list[tuple[str, str]]:
    block = re.search(r"(?ms)^projects:\s*\n(.*?)(?=^[^ \t#\n]|\Z)", text)
    if not block:
        return []
    result = []
    for item in re.split(r"(?=^  - name:\s*)", block.group(1), flags=re.M):
        name = re.search(r"^  - name:\s*([^\s#]+)", item, re.M)
        repo = re.search(r'^    repo:\s*(?:"([^"]+)"|([^\s#]+))', item, re.M)
        if name and repo:
            result.append((name.group(1), repo.group(1) or repo.group(2)))
    return result


def register_project(root, name, path, *, init_git=False, expected_hash=None):
    """登记项目；非 Git 目录在 init_git=False 时返回 needs_init 且不改配置。"""
    root = Path(root).resolve()
    config = root / "config.yaml"
    if not config.is_file():
        raise RegistryError(f"找不到配置文件: {config}")
    name = str(name).strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
        raise RegistryError("项目名称只能包含字母、数字、-、_，以字母或数字开头，最长 64 字符")
    target = Path(str(path)).expanduser()
    if not target.is_absolute():
        target = root / target
    target = target.resolve()
    if not target.exists() or not target.is_dir():
        raise RegistryError(f"项目路径不存在或不是目录: {target}")

    raw = config.read_text(encoding="utf-8")
    current_hash = _version_hash(raw)
    if expected_hash is not None and current_hash != expected_hash:
        raise RegistryError("配置文件已被其他进程修改，请刷新后重试（乐观锁冲突）")
    existing = _entries(raw)
    if any(existing_name == name for existing_name, _ in existing):
        raise RegistryError(f"项目名称已登记: {name}")
    if any(Path(repo).expanduser().resolve() == target for _, repo in existing):
        raise RegistryError(f"项目路径已登记: {target}")

    try:
        git_root = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RegistryError(f"无法检查 Git 仓库: {exc}") from exc
    is_git = git_root.returncode == 0 and Path(git_root.stdout.strip()).resolve() == target
    if not is_git and not init_git:
        return {"status": "needs_init"}
    if not is_git:
        try:
            proc = subprocess.run(["git", "-C", str(target), "init"], capture_output=True, text=True, check=False)
        except OSError as exc:
            raise RegistryError(f"无法执行 git init: {exc}") from exc
        if proc.returncode:
            raise RegistryError(f"git init 失败: {(proc.stderr or proc.stdout).strip()}")

    projects_block = re.search(r"(?ms)^projects:\s*\n(.*?)(?=^[^ \t#\n]|\Z)", raw)
    if projects_block:
        pos = projects_block.end(1)
        prefix = "" if raw[:pos].endswith("\n") else "\n"
        updated = raw[:pos] + prefix + f"  - name: {name}\n    repo: {json.dumps(str(target))}\n" + raw[pos:]
    else:
        updated = f"projects:\n  - name: {name}\n    repo: {json.dumps(str(target))}\n\n" + raw
    atomic_write(config, updated)
    try:
        written = config.read_text(encoding="utf-8")
        if (name, str(target)) not in _entries(written):
            raise RegistryError("写入后无法从配置中读取新项目")
    except Exception as exc:
        atomic_write(config, raw)
        if isinstance(exc, RegistryError):
            raise
        raise RegistryError(f"写入后校验失败，已恢复原配置: {exc}") from exc
    return {"status": "registered", "version_hash": _version_hash(written)}
