"""隔离每条需求生成的代码目录，并提供本地 Git 检查点。"""
import hashlib
import os
import subprocess
from pathlib import Path

IGNORE = {".git", "__pycache__", ".pytest_cache", ".mypy_cache"}


class WorkdirError(RuntimeError):
    pass


def project_dir(root, state):
    return Path(root) / "workspace" / "projects" / state["project"] / state["id"]


def _git(path, *args, check=True):
    p = subprocess.run(["git", "-C", str(path), *args], text=True, capture_output=True)
    if check and p.returncode:
        raise WorkdirError(p.stderr.strip() or p.stdout.strip() or f"git {' '.join(args)} failed")
    return p


def prepare(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    if not (path / ".git").exists():
        _git(path, "init", "-q")
        (path / ".gitignore").write_text("__pycache__/\n*.py[cod]\n.pytest_cache/\n", encoding="utf-8")
        _git(path, "add", ".gitignore")
        _git(path, "-c", "user.name=AutoDev", "-c", "user.email=autodev@localhost",
             "commit", "-qm", "Initialize generated project")
    return path


def head(path):
    return _git(path, "rev-parse", "HEAD").stdout.strip()


def checkpoint(path, message):
    _git(path, "add", "-A")
    if _git(path, "diff", "--cached", "--quiet", check=False).returncode == 0:
        return head(path)
    _git(path, "-c", "user.name=AutoDev", "-c", "user.email=autodev@localhost",
         "commit", "-qm", message)
    return head(path)


def fingerprint(path):
    digest = hashlib.sha256()
    path = Path(path)
    for base, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in IGNORE)
        for name in sorted(files):
            p = Path(base) / name
            rel = p.relative_to(path).as_posix()
            digest.update(rel.encode())
            if p.is_symlink():
                digest.update(os.readlink(p).encode())
            else:
                digest.update(str(p.stat().st_mode & 0o111).encode())
                with p.open("rb") as f:
                    for block in iter(lambda: f.read(65536), b""):
                        digest.update(block)
    return digest.hexdigest()


def full_patch(path):
    root = _git(path, "rev-list", "--max-parents=0", "HEAD").stdout.strip()
    return _git(path, "diff", "--binary", "--no-ext-diff", f"{root}..HEAD").stdout


def restore(path, revision):
    _git(path, "reset", "--hard", revision)
    _git(path, "clean", "-fd")


def tag(path, name):
    if _git(path, "show-ref", "--tags", "--verify", "--quiet", f"refs/tags/{name}", check=False).returncode == 0:
        raise WorkdirError(f"标签已存在：{name}")
    _git(path, "tag", name)
