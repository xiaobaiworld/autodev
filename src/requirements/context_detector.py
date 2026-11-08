# 定位: context_detector.py 采集目标项目的模块概貌、近期需求文档与 Git 提交历史，为大模型提供架构拓扑与近期关联判断依据。
from __future__ import annotations

import logging
import os
import subprocess
from typing import Any

log = logging.getLogger("autodev.req")


def get_recent_git_commits(cwd: str, limit: int = 5) -> list[str]:
    """获取目标项目最近的 Git 提交记录摘要。"""
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, "log", f"-n{limit}", "--oneline"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if proc.returncode == 0:
            lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
            return lines
    except Exception as e:
        log.debug("读取 git log 失败 (项目可能未纳入 git 或无提交): %s", e)
    return []


def get_recent_requirement_docs(cwd: str, limit: int = 5) -> list[dict[str, str]]:
    """读取 docs/requirements/ 下最近修改的需求规格说明文档。"""
    req_dir = os.path.join(cwd, "docs", "requirements")
    if not os.path.isdir(req_dir):
        return []

    try:
        files = [
            f for f in os.listdir(req_dir)
            if f.endswith(".md") and not f.startswith(".")
        ]
        # 按修改时间倒序
        files.sort(key=lambda x: os.path.getmtime(os.path.join(req_dir, x)), reverse=True)
        recent_files = files[:limit]

        results: list[dict[str, str]] = []
        for fn in recent_files:
            fp = os.path.join(req_dir, fn)
            summary = ""
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    for line in f:
                        stripped = line.strip()
                        if stripped and not stripped.startswith("#"):
                            summary = stripped[:80]
                            break
            except Exception:
                pass
            results.append({"filename": fn, "summary": summary})
        return results
    except Exception as e:
        log.debug("读取需求文档失败: %s", e)
        return []


def get_project_modules(cwd: str) -> list[str]:
    """探测项目中的主要代码模块与业务域目录。"""
    modules: list[str] = []
    # 优先看 src/
    src_dir = os.path.join(cwd, "src")
    scan_target = src_dir if os.path.isdir(src_dir) else cwd

    try:
        for entry in sorted(os.listdir(scan_target)):
            if entry.startswith(".") or entry.startswith("_"):
                continue
            entry_path = os.path.join(scan_target, entry)
            if os.path.isdir(entry_path):
                # 排除一些常见非业务目录
                if entry not in ("tests", "venv", ".venv", "node_modules", "build", "dist", "logs", "workspace"):
                    modules.append(entry)
    except Exception:
        pass
    return modules[:10]


def get_deployment_assets(cwd: str) -> list[str]:
    """自动搜寻目标项目中的部署、运维、守护服务与环境配置资产，供 Agent 自动判断软件/部署分类与关联。"""
    assets: list[str] = []
    try:
        # 1. 探测根目录下常见的部署相关文件或目录
        deploy_dirs = ("deploy", "scripts", "ops", "infra", "k8s", "helm", "docker", "systemd")
        root_markers = (
            "Dockerfile",
            "docker-compose.yml",
            "docker-compose.yaml",
            "Makefile",
            "Procfile",
            ".env.example",
            "config.yaml",
            "config.req.toml",
        )
        for d in deploy_dirs:
            dpath = os.path.join(cwd, d)
            if os.path.isdir(dpath):
                sub_items = [
                    f"{d}/{sub}"
                    for sub in sorted(os.listdir(dpath))
                    if not sub.startswith(".") and not sub.startswith("_")
                ][:8]
                if sub_items:
                    assets.extend(sub_items)
                else:
                    assets.append(f"{d}/")
        for m in root_markers:
            if os.path.exists(os.path.join(cwd, m)):
                assets.append(m)
    except Exception:
        pass
    return assets[:12]


def build_project_context_summary(cwd: str) -> str:
    """组装提供给大模型的项目架构、部署资产与近期演进脉络概要。"""
    lines: list[str] = []

    # 1. 项目现有代码模块概览
    modules = get_project_modules(cwd)
    if modules:
        lines.append(f"• 项目现有软件模块/业务域 (src/)：{', '.join(modules)}")

    # 2. 项目现有环境部署与脚本资产
    deploy_assets = get_deployment_assets(cwd)
    if deploy_assets:
        lines.append(f"• 项目现有环境部署与配置资产：{', '.join(deploy_assets)}")

    # 3. 近期提交历史
    commits = get_recent_git_commits(cwd, limit=4)
    if commits:
        lines.append("• 最近代码与功能变更记录 (Git)：")
        for c in commits:
            lines.append(f"  - {c}")

    # 4. 近期落盘的需求文档
    req_docs = get_recent_requirement_docs(cwd, limit=3)
    if req_docs:
        lines.append("• 近期已定稿的需求规格列表 (docs/requirements/)：")
        for doc in req_docs:
            desc = f" ({doc['summary']})" if doc["summary"] else ""
            lines.append(f"  - {doc['filename']}{desc}")

    if not lines:
        return ""

    return "\n".join(lines)
