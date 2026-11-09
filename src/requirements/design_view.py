"""设计机器人的只读视图：按项目列出运行、查看状态、查看设计包。渠道无关，返回纯文本，不改任何状态。"""
from __future__ import annotations

import re

from web.api import get_run_detail, list_pipeline_runs, redact_secrets

RUN_ID = re.compile(r"R\d{8}-\d{3}")
DESIGN_FILES = (
    ("design.md", "设计稿"),
    ("dev-plan.md", "开发计划"),
    ("prototype.md", "界面原型或不适用说明"),
)
DEFAULT_LIMIT = 1200


def render_list(root, project: str) -> str:
    if not project:
        return "未选择项目：请先用 /project 选择目标项目，我不会猜测。"
    runs = [r for r in list_pipeline_runs(root) if r.get("project") == project]
    if not runs:
        return f"项目 {project} 下没有运行记录。"
    lines = [f"项目 {project} 的运行（共 {len(runs)} 个）："]
    for r in runs[:10]:
        mark = r.get("status", "")
        if r.get("waiting_human"):
            mark = "⚠️ 等你决定"
        lines.append(f"• {r['id']}  {r.get('stage', '')} 第{r.get('round', 1)}轮  {mark}  {r.get('title', '')}")
    if len(runs) > 10:
        lines.append(f"… 还有 {len(runs) - 10} 个未显示")
    return "\n".join(lines)


def _load(root, run_id: str, project: str):
    """返回 (detail, 错误文本)；编号格式、存在性、项目归属都在这里核对。"""
    if not RUN_ID.fullmatch(run_id or ""):
        return None, "运行编号格式应为 R20261109-001。"
    try:
        detail = get_run_detail(root, run_id)
    except FileNotFoundError:
        return None, f"找不到运行 {run_id}。"
    if detail["state"].get("project") != project:
        return None, f"运行 {run_id} 不属于当前项目 {project or '（未选择）'}，不显示其内容。"
    return detail, None


def render_status(root, run_id: str, project: str) -> str:
    detail, err = _load(root, run_id, project)
    if err:
        return err
    st = detail["state"]
    lines = [
        f"运行 {run_id}（项目 {project}）",
        f"阶段 {st.get('stage')} 第{st.get('round')}轮，状态 {st.get('status')}",
    ]
    if detail.get("wait_reason"):
        lines.append("⚠️ 等你决定：" + detail["wait_reason"])
    step = st.get("step")
    if step and step.get("agent"):
        lines.append(f"当前执行：{step['agent']} / {step.get('model', '')}")
    return "\n".join(lines)


def _clip(text: str, limit: int) -> str:
    text = redact_secrets(text.strip())
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n…（已截断，共 {len(text)} 字）"


def _rounds(detail, code: str):
    for stage in detail["stages"]:
        if stage["code"] == code:
            return stage["rounds"]
    return []


def render_design(root, run_id: str, project: str, limit: int = DEFAULT_LIMIT) -> str:
    detail, err = _load(root, run_id, project)
    if err:
        return err
    s2 = _rounds(detail, "S2")
    s3 = _rounds(detail, "S3")
    arts = dict()
    if s2:
        arts = s2[-1]["artifacts"]
    lines = [f"运行 {run_id} 的设计包（项目 {project}）"]
    for fname, label in DESIGN_FILES:
        if fname in arts:
            lines.append(f"\n【{label}】{fname}\n" + _clip(arts[fname], limit))
        else:
            lines.append(f"\n【{label}】{fname}：尚未生成")
    if s3:
        done = s3[-1].get("done")
        if not done:
            done = dict()
        lines.append(f"\n【审查结论】{done.get('verdict', '未给出')}  {done.get('summary', '')}")
    else:
        lines.append("\n【审查结论】尚未审查")
    return "\n".join(lines)
