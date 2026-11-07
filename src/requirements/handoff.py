# 定位: handoff.py 需求澄清阶段（飞书 SRS）到主流水线下一阶段（S2 架构设计）的独立桥接交接器（A1）。
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from cockpit.agents import parse_agents, parse_limits, parse_roles
from cockpit.kinds import DEFAULT_KIND, check_kind
from cockpit.pipeline import check_vendors, counters_for, step_dir, template_for
from cockpit.store import Run, atomic_write, now_iso
from requirements.validator import validate_requirement_spec

AUTODEV_ROOT = Path(__file__).resolve().parents[2]


def _extract_section_body(markdown_text: str, section_num: int) -> str:
    pattern = rf"^##\s+{section_num}\.\s+[^\n]+\n(.*?)(?=^##\s+\d+\.|\Z)"
    m = re.search(pattern, markdown_text, flags=re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def extract_srs_metadata(srs_text: str) -> dict[str, Any]:
    """从通过校验的 9 章节 SRS 文档中提取核心元数据，供 S1 基线产物与 S2 架构设计使用。"""
    title_match = re.search(
        r"^#\s+(?:需求规格说明书|软件需求规格说明（SRS）)[：:]\s*(.+?)\s*$",
        srs_text,
        flags=re.MULTILINE,
    )
    if not title_match:
        title_match = re.search(r"\*\*需求名称\*\*[：:]\s*(.+?)\s*$", srs_text, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "未命名需求"

    sec3 = _extract_section_body(srs_text, 3)
    summary_lines = [
        re.sub(r"^[-*>\s]+", "", line.strip())
        for line in sec3.splitlines()
        if line.strip() and not line.strip().startswith("<!--")
    ]
    summary = " ".join(summary_lines)[:200] or title

    sec4 = _extract_section_body(srs_text, 4)
    scope_items = [
        re.sub(r"^[-*\d.]+\s*", "", line.strip())
        for line in sec4.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    scope_summary = "；".join(scope_items[:5])[:240] if scope_items else title

    sec8 = _extract_section_body(srs_text, 8)
    ac_items = [
        re.sub(r"^[-*]\s*(\[[ xX]\]\s*)?", "", line.strip())
        for line in sec8.splitlines()
        if line.strip() and (line.strip().startswith(("-", "*")) or "场景" in line or "Scenario" in line)
    ]

    return {
        "title": title,
        "summary": summary,
        "scope": scope_summary,
        "acceptance_criteria": ac_items or ["满足 SRS 第 8 节全部可量化验收标准"],
    }


def _build_s1_baseline_analysis(rid: str, srs_text: str, meta: dict[str, Any]) -> str:
    """生成 S1-analysis/round-1/analysis.md 基线产物，使 S2/S3 既能读到结构化分析结论又能对照完整 SRS。"""
    ac_yaml = "\n".join(f'  - "{item.replace(chr(34), chr(39))}"' for item in meta["acceptance_criteria"])
    safe_summary = meta["summary"].replace('"', "'")
    safe_scope = meta["scope"].replace('"', "'")
    return (
        f"---\n"
        f"id: {rid}\n"
        f"stage: S1\n"
        f"round: 1\n"
        f"role: analyst\n"
        f"verdict: ACCEPT\n"
        f'summary: "{safe_summary}"\n'
        f'scope: "{safe_scope}"\n'
        f"acceptance_criteria:\n"
        f"{ac_yaml}\n"
        f"---\n\n"
        f"# 需求分析结论（由飞书需求分析师 SRS v1.0 定稿直通生成）\n\n"
        f"- **需求标题**：{meta['title']}\n"
        f"- **一句话摘要**：{meta['summary']}\n"
        f"- **核心范围**：{meta['scope']}\n\n"
        f"## 验收标准清单\n\n"
        + "\n".join(f"- {item}" for item in meta["acceptance_criteria"])
        + "\n\n---\n\n"
        + "## 附：完整软件需求规格说明（SRS 原文）\n\n"
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
    """将定稿并通过契约校验的 REQ-xxx.md 移交至主流水线，跳过重复的 S1，直接初始化为 S2（架构设计）待执行状态。

    步骤：
    1. 校验 SRS 是否满足 REQUIREMENT_SPEC_STANDARD.md (RULE-01 ~ RULE-09)；
    2. 校验流水线 kind 与 config.yaml 中的 D008 异构厂商约束；
    3. 写入 workspace/requests/active/{rid}.md；
    4. 写入 workspace/runs/{rid}/S1-analysis/round-1/{analysis.md, done.json} 基线；
    5. 将 workspace/runs/{rid}/state.json 直接置为 stage="S2", round=1, step=pending(designer)。
    """
    check_kind(kind)
    srs_file = Path(srs_path).resolve()
    if not srs_file.is_file():
        raise FileNotFoundError(f"找不到需求定稿文件: {srs_file}")

    raw_text = srs_file.read_text(encoding="utf-8")
    clean_srs = re.sub(r"\n*<!--\s*SPEC-VALIDATED:.*?-->\s*\Z", "", raw_text, flags=re.DOTALL).strip()

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

    day = (today or datetime.now()).strftime("%Y%m%d")
    active_dir = root_dir / "workspace" / "requests" / "active"
    active_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = root_dir / "workspace" / "runs"
    n = len(list(runs_dir.glob(f"R{day}-*"))) + 1 if runs_dir.exists() else 1
    rid = f"R{day}-{n:03d}"

    req_file = active_dir / f"{rid}.md"
    atomic_write(
        req_file,
        f"---\n"
        f"schema_version: 1\n"
        f"id: {rid}\n"
        f"project: {project}\n"
        f"source_srs: {srs_file.name}\n"
        f"submitted_at: {now_iso()}\n"
        f"---\n\n"
        f"{clean_srs}\n",
    )

    meta = extract_srs_metadata(clean_srs)
    run_dir = runs_dir / rid
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
                "summary": f"飞书需求澄清定稿直通（{srs_file.name}）：{meta['summary'][:80]}",
                "finished_at": now_iso(),
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
    )

    state: dict[str, Any] = {
        "schema_version": 1,
        "id": rid,
        "project": project,
        "kind": kind,
        "status": "active",
        "stage": "S2",
        "round": 1,
        "step": None,
        "counters": counters_for(kind),
        "human": {"waiting": False, "pending_decision": None, "resume_to": None},
    }

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

    reviewer_agent = roles.get("design_reviewer", "")
    reviewer_model = agents.get(reviewer_agent, {}).get("model", "")

    return {
        "run_id": rid,
        "run_dir": str(run_dir),
        "request_file": str(req_file),
        "s1_analysis_file": str(analysis_path),
        "source_srs": str(srs_file),
        "title": meta["title"],
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
    ap = argparse.ArgumentParser(description="将定稿的飞书 SRS 文档直通移交至主流水线 S2 架构设计阶段")
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
