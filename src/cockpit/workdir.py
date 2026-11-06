"""S4 编码阶段的 git 操作：全部由程序做，Agent 只改文件、不碰 git。

每个需求一个独立仓库目录 workspace/projects/<项目>/<需求号>/（放在 workspace 里，Agent 的沙箱才允许写）。
- prepare：建目录、git init、提交起点（可带初始文件），返回起点提交。重复调用不重建。
- reset：回到起点并清掉未跟踪文件。重做编码步骤前用，保证每次从同一状态开始（设计 5.4）。
- snapshot：把当前所有改动写成 diff.patch，列出改动文件，用于核对 Agent 报告的 files_changed。
# ponytail: 每个需求一个新仓库，不从目标项目的真实仓库克隆。接真实项目（personagent）时改成
# `git worktree add` 或 clone，prepare 的接口不变。
"""
import subprocess
from pathlib import Path

from cockpit.store import atomic_write

_ID = ["-c", "user.name=autodev", "-c", "user.email=autodev@localhost", "-c", "commit.gpgsign=false"]


class GitError(Exception):
    pass


def _git(cwd, *args, check=True):
    r = subprocess.run(["git", *_ID, *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise GitError(f"git {' '.join(args)} 失败：{r.stderr.strip() or r.stdout.strip()}")
    return r.stdout


def head(workdir):
    return _git(workdir, "rev-parse", "HEAD").strip()


def prepare(workdir, seed_files=None):
    """返回起点提交。已经是仓库就直接返回它的第一个提交（起点不变）。seed_files: {相对路径: 内容}。"""
    workdir = Path(workdir)
    if (workdir / ".git").exists():
        return _git(workdir, "rev-list", "--max-parents=0", "HEAD").strip().splitlines()[0]
    workdir.mkdir(parents=True, exist_ok=True)
    _git(workdir, "init", "-q", "-b", "main")
    seed_files = {".gitignore": "__pycache__/\n*.pyc\n", **(seed_files or {})}  # 运行测试会产生缓存，不能进补丁
    for rel, text in seed_files.items():
        p = workdir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    _git(workdir, "add", "-A")
    _git(workdir, "commit", "-q", "--allow-empty", "-m", "起点")
    return head(workdir)


def reset(workdir, base):
    """回到起点：丢弃所有改动和未跟踪文件。只用在程序自己建的代码目录里。"""
    workdir = Path(workdir)
    if not (workdir / ".git").exists():
        raise GitError(f"{workdir} 不是 git 仓库，拒绝清理")
    _git(workdir, "reset", "-q", "--hard", base)
    _git(workdir, "clean", "-q", "-fdx")


def snapshot(workdir, base, patch_path):
    """把相对起点的全部改动（含新文件）写成 patch，返回改动的文件列表（相对路径，已排序）。"""
    workdir = Path(workdir)
    _git(workdir, "add", "-A")  # 暂存只是为了让新文件进 diff，不提交
    patch = _git(workdir, "diff", "--cached", base)
    files = sorted(_git(workdir, "diff", "--cached", "--name-only", base).splitlines())
    _git(workdir, "reset", "-q")  # 取消暂存，保持“Agent 改完的原样”
    atomic_write(Path(patch_path), patch)
    return files
