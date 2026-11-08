# 定位: handoff.py 需求澄清阶段（飞书/Web SRS）到主流水线下一阶段（S2 架构设计）的独立桥接交接器（A1，含 O2/O3/C3 优化收敛）。
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from cockpit.agents import parse_agents, parse_limits, parse_roles
from cockpit.controller import allocate_run_id, build_initial_state
from cockpit.kinds import DEFAULT_KIND, check_kind
from cockpit.pipeline import check_vendors, step_dir, template_for
from cockpit.store import Run, acquire_lock, atomic_write, now_iso
from requirements.validator import (
    extract_srs_metadata,
    strip_validation_comment,
    validate_requirement_spec,
)

AUTODEV_ROOT = Path(__file__).resolve().parents[2]


def _build_s1_baseline_analysis(rid: str, srs_text: str, meta: dict[str, Any]) -> str:
    """生成 S1-analysis/round-1/analysis.md 基线产物，使 S2/S3/S4 既能读到结构化分析结论又能感知软件/部署类型差异与完整 SRS。"""
    ac_yaml = "\n".join(f'  - "{item.replace(chr(34), chr(39))}"' for item in meta["acceptance_criteria"])
    safe_summary = meta["summary"].replace('"', "'")
    safe_scope = meta["scope"].replace('"', "'")
    req_type = meta.get("req_type", "SOFTWARE")
    deliverables = meta.get("deliverables") or []
    deliv_note = ""
    if req_type in ("DEPLOYMENT", "HYBRID"):
        deliv_list = "、".join(f"`{d}`" for d in deliverables) if deliverables else "见 SRS 第 4 节部署脚本与配置清单"
        deliv_note = (
            f"\n## 部署工程与脚本交付指令（{req_type}）\n\n"
            f"- **需求交付形态**：`{req_type}`（需生成可执行部署脚本与环境验证探针）\n"
            f"- **关键脚本/配置交付物**：{deliv_list}\n"
            f"- **下游 S2/S4 强制要求**：S2 设计稿与开发计划必须明确部署脚本路径、五步生命周期（预检/安装/启动/幂等重跑/回滚）与安全边界；S4 必须生成对应部署脚本并通过语法与沙箱实跑测试。\n"
        )
    elif req_type == "HARDWARE":
        deliv_note = (
            f"\n## 硬件与设备接入工程指令（{req_type}）\n\n"
            f"- **需求交付形态**：`{req_type}`（需设计硬件抽象层 HAL、断线重连守护与软件模拟器 Mock）\n"
            f"- **下游 S2/S4 强制要求**：S2 设计稿必须将物理设备通信协议（串口/USB/Modbus等）与业务逻辑解耦；S4 必须实现真实驱动适配与脱机可跑的硬件信号模拟器（Mock）测试。\n"
        )
    return (
        f"---\n"
        f"id: {rid}\n"
        f"stage: S1\n"
        f"round: 1\n"
        f"role: analyst\n"
        f"req_type: {req_type}\n"
        f"verdict: ACCEPT\n"
        f'summary: "{safe_summary}"\n'
        f'scope: "{safe_scope}"\n'
        f"acceptance_criteria:\n"
        f"{ac_yaml}\n"
        f"---\n\n"
        f"# 需求分析结论（由飞书/Web 需求分析师 SRS v1.1 定稿直通生成）\n\n"
        f"- **需求标题**：{meta['title']}\n"
        f"- **需求类型**：`{req_type}`\n"
        f"- **一句话摘要**：{meta['summary']}\n"
        f"- **核心范围**：{meta['scope']}\n"
        f"{deliv_note}\n"
        f"## 验收标准清单\n\n"
        + "\n".join(f"- {item}" for item in meta["acceptance_criteria"])
        + "\n\n---\n\n"
        + "## 附：完整软件/部署需求规格说明（SRS 原文）\n\n"
        + srs_text.strip()
        + "\n"
    )


def handoff_srs_to_pipeline(
    srs_path: str | Path,
    root: str | Path | None = None,
    project: str = "toy",
    kind: str = DEFAULT_KIND,
    config_yaml: str | Path | None = None,
    today: datetime | None = None,
) -> dict[str, Any]:
    """将定稿并通过契约校验的 REQ-xxx.md 移交至主流水线，跳过重复的 S1，直接初始化为 S2（架构设计）待执行状态。"""
    check_kind(kind)
    srs_file = Path(srs_path).resolve()
    if not srs_file.is_file():
        raise FileNotFoundError(f"找不到需求定稿文件: {srs_file}")

    raw_text = srs_file.read_text(encoding="utf-8")
    clean_srs = strip_validation_comment(raw_text)

    v_res = validate_requirement_spec(clean_srs)
    if not v_res.is_valid:
        raise ValueError(f"需求文档未通过 SRS v1.0 程序化契约校验，拒绝移交 S2：{'; '.join(v_res.errors)}")

    root_dir = Path(root).resolve() if root else AUTODEV_ROOT
    cfg_file = Path(config_yaml).resolve() if config_yaml else (root_dir / "config.yaml")
    if not cfg_file.is_file():
        cfg_file = AUTODEV_ROOT / "config.yaml"

    cfg_text = cfg_file.read_text(encoding="utf-8")
    agents = parse_agents(cfg_text)
    roles = parse_roles(cfg_text)
    limits = parse_limits(cfg_text)
    check_vendors(agents, roles)

    lock = acquire_lock(root_dir / "workspace" / ".lock")
    try:
        active_dir = root_dir / "workspace" / "requests" / "active"
        active_dir.mkdir(parents=True, exist_ok=True)
        rid = allocate_run_id(root_dir, today=today)
        meta = extract_srs_metadata(clean_srs)
        req_type = meta.get("req_type", "SOFTWARE")

        req_file = active_dir / f"{rid}.md"
        atomic_write(
            req_file,
            f"---\n"
            f"schema_version: 1\n"
            f"id: {rid}\n"
            f"project: {project}\n"
            f"req_type: {req_type}\n"
            f"source_srs: {srs_file.name}\n"
            f"submitted_at: {now_iso()}\n"
            f"---\n\n"
            f"{clean_srs}\n",
        )

        run_dir = root_dir / "workspace" / "runs" / rid
        s1_dir = run_dir / step_dir("S1", 1, kind)
        analysis_path = s1_dir / "analysis.md"
        atomic_write(analysis_path, _build_s1_baseline_analysis(rid, clean_srs, meta))
        atomic_write(
            s1_dir / "done.json",
            json.dumps(
                {
                    "id": rid,
                    "stage": "S1",
                    "round": 1,
                    "role": "analyst",
                    "outputs": ["analysis.md"],
                    "verdict": "ACCEPT",
                    "summary": f"需求澄清定稿直通（{srs_file.name}）：{meta['summary'][:80]}",
                    "finished_at": now_iso(),
                },
                ensure_ascii=False,
                indent=1,
            )
            + "\n",
        )

        state = build_initial_state(rid, project, kind=kind, stage="S2", round_num=1)
        s2_spec = template_for(state)["stages"]["S2"]
        designer_role = s2_spec["role"]
        designer_agent = roles[designer_role]
        designer_model = agents[designer_agent].get("model")

        state["step"] = {
            "state": "pending",
            "role": designer_role,
            "agent": designer_agent,
            "model": designer_model,
            "dir": step_dir("S2", 1, kind),
            "started_at": None,
            "deadline_at": None,
            "attempt": 1,
            "fail_reason": None,
        }

        run = Run(run_dir)
        run.commit(
            state,
            "request.claimed",
            data={"source_srs": str(srs_file), "skipped_stage": "S1", "title": meta["title"]},
        )
        run.commit(
            state,
            "stage.entered",
            data={"verdict": "ACCEPT", "from_stage": "S1", "to_stage": "S2", "handoff": "feishu_srs_v1"},
        )
    finally:
        lock.close()

    reviewer_agent = roles.get("design_reviewer", "")
    reviewer_model = agents.get(reviewer_agent, {}).get("model", "")

    return {
        "run_id": rid,
        "run_dir": str(run_dir),
        "request_file": str(req_file),
        "s1_analysis_file": str(analysis_path),
        "source_srs": str(srs_file),
        "title": meta["title"],
        "req_type": req_type,
        "deliverables": meta.get("deliverables", []),
        "project": project,
        "kind": kind,
        "stage": "S2",
        "round": 1,
        "designer_agent": designer_agent,
        "designer_model": designer_model,
        "reviewer_agent": reviewer_agent,
        "reviewer_model": reviewer_model,
        "limits": limits,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="将定稿的飞书/Web SRS 文档直通移交至主流水线 S2 架构设计阶段")
    ap.add_argument("--req", required=True, help="定稿的 REQ-xxx.md 文件路径")
    ap.add_argument("--root", default=str(AUTODEV_ROOT), help="AutoDev 根目录（默认当前仓库根）")
    ap.add_argument("--project", default="toy", help="目标项目名（默认 toy）")
    ap.add_argument("--kind", default=DEFAULT_KIND, help="流水线类型（pipeline/design 或 pipeline/build）")
    args = ap.parse_args(argv)

    try:
        info = handoff_srs_to_pipeline(
            srs_path=args.req,
            root=args.root,
            project=args.project,
            kind=args.kind,
        )
    except Exception as e:
        print(f"移交失败：{e}", file=sys.stderr)
        return 1

    print(
        f"✅ 已成功移交至 S2 架构设计！\n"
        f"• 运行编号：{info['run_id']}\n"
        f"• 需求标题：{info['title']}\n"
        f"• 当前阶段：{info['stage']} (第 {info['round']} 轮，已跳过重复的 S1)\n"
        f"• 架构设计（S2）：{info['designer_agent']} ({info['designer_model']})\n"
        f"• 设计审查（S3）：{info['reviewer_agent']} ({info['reviewer_model']})\n"
        f"• 运行目录：{info['run_dir']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
