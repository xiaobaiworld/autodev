# 定位: validator.py 按照 SPEC-REQ-STANDARD-v1.1 规范，统一负责 SRS/部署需求文档的程序化语法/语义校验、需求类型识别（SOFTWARE/DEPLOYMENT/HYBRID）、章节切分、元数据提取与 RULE-01~09 逐项透视。
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from requirements.flow import classify_requirement_type, extract_agent_classified_type


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


SECTION_SPECS: list[tuple[int, str, list[str]]] = [
    (1, "## 1. 需求标识与元数据", ["## 1. 需求标识与元数据"]),
    (
        2,
        "## 2. 需求规模分类与需求关联网络",
        ["## 2. 需求规模分类与需求关联网络", "## 2. 架构拓扑与近期关联"],
    ),
    (3, "## 3. 核心背景与业务目标 (Why & What)", ["## 3. 核心背景与业务目标 (Why & What)"]),
    (
        4,
        "## 4. 业务用例与核心流程 (Scope)",
        [
            "## 4. 业务用例与核心流程 (Scope)",
            "## 4. 部署流程与脚本交付清单 (Deployment Scope)",
            "## 4. 核心流程与交付范围 (Scope)",
        ],
    ),
    (5, "## 5. 明确非目标与边界 (Non-goals)", ["## 5. 明确非目标与边界 (Non-goals)"]),
    (
        6,
        "## 6. 外部界面原型草图 (UI Wireframe)",
        [
            "## 6. 外部界面原型草图 (UI Wireframe)",
            "## 6. 部署架构拓扑与命令交互草图 (Deployment Topology)",
            "## 6. 外部界面原型或部署拓扑草图",
        ],
    ),
    (
        7,
        "## 7. 业务约束与前置依赖",
        [
            "## 7. 业务约束与前置依赖",
            "## 7. 目标环境基线与安全权限约束",
        ],
    ),
    (8, "## 8. 可量化验收标准清单 (Acceptance Criteria)", ["## 8. 可量化验收标准清单 (Acceptance Criteria)"]),
    (
        9,
        "## 9. 下游架构设计关注点",
        [
            "## 9. 下游架构设计关注点",
            "## 9. 下游架构与部署脚本设计关注点",
        ],
    ),
]

RULE_DESCRIPTIONS: list[tuple[str, str]] = [
    ("RULE-00", "明确项目与需求身份 (D016)"),
    ("RULE-01", "UTF-8 编码与 REQ-*.md 命名规范"),
    ("RULE-02", "九大标准章节标题完整性"),
    ("RULE-03", "需求类型(软件/部署)、规模与关系矩阵"),
    ("RULE-04", "核心业务背景与业务目标双要素"),
    ("RULE-05", "明确非目标与防膨胀边界声明"),
    ("RULE-06", "界面线框图或部署拓扑草图 (```text)"),
    ("RULE-07", "可量化验收标准(含部署探针/幂等)"),
    ("RULE-08", "严禁越权编写 SQL 或业务实现代码"),
    ("RULE-09", "文档有效篇幅区间 (≥ 300 字符)"),
]

FORBIDDEN_TECH_PATTERNS = [
    r"CREATE\s+TABLE",
    r"ALTER\s+TABLE",
    r"SELECT\s+.+\s+FROM",
    r"INSERT\s+INTO",
    r"def\s+[a-zA-Z0-9_]+\s*\(",
    r"class\s+[a-zA-Z0-9_]+[:\(]",
]


def strip_validation_comment(content: str) -> str:
    """去除末尾附加的 <!-- SPEC-VALIDATED: ... --> 元数据注释。"""
    return re.sub(r"\n*<!--\s*SPEC-VALIDATED:.*?-->\s*\Z", "", content or "", flags=re.DOTALL).strip()


def extract_section_body(markdown_text: str, section_num: int) -> str:
    """提取指定章节编号（1~9）的正文内容。"""
    pattern = rf"^##\s+{section_num}\.\s+[^\n]+\n(.*?)(?=^##\s+\d+\.|\Z)"
    m = re.search(pattern, markdown_text, flags=re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def extract_req_type(markdown_text: str) -> str:
    """从 SRS 文档中提取或自动推断需求类型（SOFTWARE / DEPLOYMENT / HARDWARE / HYBRID）。"""
    clean_text = strip_validation_comment(markdown_text)
    explicit = extract_agent_classified_type(clean_text)
    if explicit in ("SOFTWARE", "DEPLOYMENT", "HARDWARE", "HYBRID"):
        return explicit
    if re.search(r"REQ-HW-", clean_text, re.I):
        return "HARDWARE"
    if re.search(r"REQ-DEPLOY-", clean_text, re.I):
        return "DEPLOYMENT"
    if re.search(r"REQ-HYBRID-", clean_text, re.I):
        return "HYBRID"
    inferred, _ = classify_requirement_type(clean_text)
    return inferred


def extract_project(srs_text: str) -> str:
    """提取归属项目标识（优先 Frontmatter 中的 project，其次第 1 节元数据，D016 不变量）。"""
    clean_text = strip_validation_comment(srs_text)
    fm_match = re.match(r"^---\n(.*?)\n---", clean_text, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).splitlines():
            line = line.strip()
            if line.startswith("project:"):
                val = line.split(":", 1)[1].strip().strip("\"'`")
                if val and not (val.startswith("（") or val.startswith("(")):
                    return val
    sec1 = extract_section_body(clean_text, 1)
    if sec1:
        m = re.search(r"[-*]\s*\*\*(?:归属项目|项目标识|目标项目|项目名称)\*\*[：:]\s*`?([^\n`]+)`?", sec1)
        if m:
            val = m.group(1).strip().strip("\"'`")
            if val and not (val.startswith("（") or val.startswith("(")):
                return val
    return ""


def extract_req_id(srs_text: str) -> str:
    """提取需求编号（优先 Frontmatter 中的 id/req_id，其次第 1 节元数据，D016 不变量）。"""
    clean_text = strip_validation_comment(srs_text)
    fm_match = re.match(r"^---\n(.*?)\n---", clean_text, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).splitlines():
            line = line.strip()
            if line.startswith("id:") or line.startswith("req_id:"):
                val = line.split(":", 1)[1].strip().strip("\"'`")
                if val and not (val.startswith("（") or val.startswith("(")):
                    return val
    sec1 = extract_section_body(clean_text, 1)
    if sec1:
        m = re.search(r"[-*]\s*\*\*(?:需求编号|需求ID|REQ编号|编号)\*\*[：:]\s*`?([^\n`]+)`?", sec1)
        if m:
            val = m.group(1).strip().strip("\"'`")
            if val and not (val.startswith("（") or val.startswith("(")):
                return val
    return ""


def extract_deliverables(markdown_text: str) -> list[str]:
    """提取第 4 节或全文中声明的脚本/配置交付物（如 deploy/*.sh, *.plist, *.service, Dockerfile）。"""
    clean_text = strip_validation_comment(markdown_text)
    sec4 = extract_section_body(clean_text, 4) or clean_text
    found: list[str] = []
    for m in re.finditer(
        r"`([a-zA-Z0-9_./*-]+(?:\.sh|\.plist|\.service|\.yaml|\.yml|\.toml|\.conf|Dockerfile|\.env\.example))`",
        sec4,
    ):
        val = m.group(1).strip()
        if val not in found:
            found.append(val)
    return found[:10]


def extract_srs_metadata(srs_text: str) -> dict[str, Any]:
    """从 9 章节 SRS 文档中提取核心元数据（标题、需求类型、交付物、摘要、范围、验收标准），供 S1 基线与 Web 预览共用。"""
    clean_text = strip_validation_comment(srs_text)
    if not clean_text:
        return {
            "title": "未命名需求",
            "req_type": "SOFTWARE",
            "deliverables": [],
            "summary": "",
            "scope": "",
            "acceptance_criteria": [],
        }

    title_match = re.search(
        r"^#\s+(?:需求规格说明书|软件需求规格说明(?:书)?(?:（[^）]+）)?)[：:]?\s*(.*?)\s*$",
        clean_text,
        flags=re.MULTILINE,
    )
    title = title_match.group(1).strip() if (title_match and title_match.group(1).strip()) else ""
    if not title:
        name_match = re.search(r"\*\*需求名称\*\*[：:]\s*(.+?)\s*$", clean_text, flags=re.MULTILINE)
        title = name_match.group(1).strip() if name_match else "未命名需求"

    req_id = extract_req_id(clean_text)
    project = extract_project(clean_text)
    req_type = extract_req_type(clean_text)
    deliverables = extract_deliverables(clean_text)

    sec3 = extract_section_body(clean_text, 3)
    summary_lines = [
        re.sub(r"^[-*>\s]+", "", line.strip())
        for line in sec3.splitlines()
        if line.strip() and not line.strip().startswith("<!--")
    ]
    summary = " ".join(summary_lines)[:200] or title

    sec4 = extract_section_body(clean_text, 4)
    scope_items = [
        re.sub(r"^[-*\d.]+\s*", "", line.strip())
        for line in sec4.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    scope_summary = "；".join(scope_items[:5])[:240] if scope_items else title

    sec8 = extract_section_body(clean_text, 8)
    ac_items = [
        re.sub(r"^[-*]\s*(\[[ xX]\]\s*)?", "", line.strip())
        for line in sec8.splitlines()
        if line.strip() and (line.strip().startswith(("-", "*")) or "场景" in line or "Scenario" in line)
    ]

    return {
        "id": req_id,
        "project": project,
        "title": title,
        "req_type": req_type,
        "deliverables": deliverables,
        "summary": summary,
        "scope": scope_summary,
        "acceptance_criteria": ac_items or ["满足 SRS 第 8 节全部可量化验收标准"],
    }


def validate_requirement_spec(content: str) -> ValidationResult:
    """对传入的 Markdown 需求规格说明书（兼容 SOFTWARE / DEPLOYMENT / HYBRID）进行程序化规则检查。"""
    errors: list[str] = []
    warnings: list[str] = []

    text = strip_validation_comment(content)
    if not text:
        return ValidationResult(is_valid=False, errors=["[RULE-00] 需求文档内容为空"])

    # RULE-00: 检查明确项目身份与需求身份 (D016 不变量)
    proj_val = extract_project(text)
    id_val = extract_req_id(text)
    if not proj_val:
        errors.append("[RULE-00] 缺少明确的项目身份 (project/归属项目)，严禁隐式推断")
    if not id_val:
        errors.append("[RULE-00] 缺少明确的需求身份 (id/需求编号)，严禁隐式推断")

    req_type = extract_req_type(text)

    # RULE-02: 检查 9 大必备章节标题（支持软件与部署双形态兼容标题）
    for num, canonical_title, variants in SECTION_SPECS:
        if not any(v in text for v in variants):
            errors.append(f"[RULE-02] 缺失第 {num} 节必备标题: '{canonical_title}'")

    # RULE-03: 需求类别与拓扑矩阵检查
    has_hierarchy = any(k in text for k in ("功能层级归属", "模块归属", "功能层级与模块归属", "部署目标归属"))
    has_affinity = any(
        k in text
        for k in ("近期功能关联", "需求关联", "需求关系", "关系矩阵", "Parent", "Depends-on", "Relates-to")
    )
    has_scale = any(k in text for k in ("需求规模", "规模类别", "大需求", "小需求", "Epic", "Feature", "Sub-feature", "Enhancement"))

    if not has_hierarchy:
        errors.append("[RULE-03] 第 2 节必须显式包含【功能层级与模块归属】分析")
    if not has_affinity:
        errors.append("[RULE-03] 第 2 节必须显式包含【需求关联网络/近期功能关联】(Parent/Depends-on/Relates-to/None)")
    if not has_scale and "## 2. 需求规模分类与需求关联网络" in text:
        errors.append("[RULE-03] 第 2 节必须显式标明【需求规模类别】(大需求/标准功能/小需求/增强)")

    # RULE-04: 核心背景与业务目标检查
    if "业务背景" not in text or "业务目标" not in text:
        errors.append("[RULE-04] 第 3 节必须同时包含【业务背景】与【业务目标】")

    # RULE-05: 非目标边界声明检查
    sec5_body = extract_section_body(text, 5)
    if sec5_body:
        if "❌" not in sec5_body and "-" not in sec5_body:
            errors.append("[RULE-05] 第 5 节明确非目标必须包含至少一项带 '❌' 或 '-' 的具体排除条目")
    elif any(v in text for v in SECTION_SPECS[4][2]):
        errors.append("[RULE-05] 无法定位第 5 节非目标内容")

    # RULE-06: 外部界面原型线框图或部署架构拓扑草图检查
    sec6_body = extract_section_body(text, 6)
    if sec6_body:
        if "```text" not in sec6_body:
            errors.append("[RULE-06] 第 6 节必须包含 ```text 代码块形式的低保真线框图或部署架构拓扑草图")
        else:
            code_lines = [l for l in sec6_body.splitlines() if l.strip()]
            if len(code_lines) < 5:
                warnings.append("[RULE-06-WARN] 原型或部署拓扑草图行数偏少，建议至少 5 行以展示清晰结构")
    elif any(v in text for v in SECTION_SPECS[5][2]):
        errors.append("[RULE-06] 无法定位第 6 节界面原型或部署拓扑草图内容")

    # RULE-07: 可量化验收标准检查（对 DEPLOYMENT 类型额外断言幂等/健康探针/回滚要求）
    sec8_body = extract_section_body(text, 8)
    if sec8_body:
        if "场景" not in sec8_body and "Scenario" not in sec8_body and "1." not in sec8_body:
            errors.append("[RULE-07] 第 8 节验收标准必须包含具体场景条目（如 场景 1、场景 2）")
        if req_type == "DEPLOYMENT":
            deploy_ac_signals = ("幂等", "重复", "探针", "健康", "回滚", "卸载", "退出码", "进程", "端口")
            if not any(sig in sec8_body for sig in deploy_ac_signals):
                errors.append(
                    "[RULE-07] 偏环境部署需求 (DEPLOYMENT) 的第 8 节验收标准必须包含部署验证要素（如健康探针、幂等重跑、退出码或回滚验证）"
                )
        elif req_type == "HARDWARE":
            hw_ac_signals = ("设备", "重连", "断线", "热插拔", "模拟", "Mock", "采集", "串口", "延迟", "传感器")
            if not any(sig in sec8_body for sig in hw_ac_signals):
                errors.append(
                    "[RULE-07] 偏硬件工程需求 (HARDWARE) 的第 8 节验收标准必须包含硬件验证要素（如设备采集响应、断线重连自愈或模拟器 Mock 验证）"
                )
    elif any(v in text for v in SECTION_SPECS[7][2]):
        errors.append("[RULE-07] 无法定位第 8 节验收标准内容")

    # 针对 DEPLOYMENT 类型检查第 4 节是否说明了部署脚本或配置产物
    if req_type == "DEPLOYMENT":
        sec4_body = extract_section_body(text, 4)
        deploy_scope_signals = (".sh", "脚本", "plist", "service", "docker", "预检", "启动", "守护", "配置")
        if sec4_body and not any(sig in sec4_body.lower() for sig in deploy_scope_signals):
            warnings.append("[RULE-04-DEPLOY-WARN] 偏部署需求建议在第 4 节明确列出拟生成的部署脚本名称（如 deploy/*.sh）与部署步骤")

    # RULE-08: 禁止技术越权代码
    for pattern in FORBIDDEN_TECH_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            errors.append(f"[RULE-08] 需求阶段严禁越权编写技术实现代码/SQL: 命中模式 '{match.group(0)}'")

    # RULE-09: 篇幅有效性检查
    char_count = len(text)
    if char_count < 300:
        errors.append(f"[RULE-09] 需求文档字数过少（{char_count} 字符），内容不完备")
    elif char_count > 15000:
        warnings.append(f"[RULE-09-WARN] 需求文档字数过大（{char_count} 字符），建议保持精炼")

    return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)


def inspect_srs_document(content: str) -> dict[str, Any]:
    """统一透视 SRS 文档的 9 大章节状态、RULE-01~09 逐条结果、需求类型（SOFTWARE/DEPLOYMENT/HYBRID）、规模类别、关系矩阵与线框/拓扑草图。"""
    clean_text = strip_validation_comment(content)
    v_res = validate_requirement_spec(clean_text)
    req_type = extract_req_type(clean_text)
    deliverables = extract_deliverables(clean_text)

    sections_status = []
    for num, title, matches in SECTION_SPECS:
        present = any(m in clean_text for m in matches)
        body = extract_section_body(clean_text, num) if present else ""
        sections_status.append({
            "num": num,
            "title": title,
            "present": present and len(body) > 5,
            "preview": body[:300],
        })

    rules_status = []
    for code, desc in RULE_DESCRIPTIONS:
        failed_msgs = [e for e in v_res.errors if f"[{code}]" in e]
        rules_status.append({
            "code": code,
            "description": desc,
            "passed": len(failed_msgs) == 0 and bool(clean_text),
            "errors": failed_msgs,
        })

    scale_match = re.search(r"\b(Epic|Feature|Sub-feature|Enhancement)\b", clean_text)
    if not scale_match:
        scale_match = re.search(r"(史诗级大需求|标准功能|子功能|改动增强)", clean_text)
    scale = scale_match.group(1) if scale_match else "未标定"

    relations = []
    for rel_type in ("Parent", "Extends", "Connects-to", "Depends-on", "Relates-to", "Blocks", "Supersedes"):
        for m in re.finditer(rf"`?{rel_type}[^`\n]*`?[：:]\s*([^\n]+)", clean_text):
            relations.append({"type": rel_type, "target": m.group(1).strip()})

    wireframe = ""
    sec6_body = extract_section_body(clean_text, 6)
    if sec6_body:
        wf_match = re.search(r"```text\n(.*?)```", sec6_body, flags=re.S)
        if wf_match:
            wireframe = wf_match.group(1).rstrip()

    return {
        "is_valid": v_res.is_valid,
        "errors": v_res.errors,
        "warnings": v_res.warnings,
        "req_type": req_type,
        "deliverables": deliverables,
        "sections": sections_status,
        "sections_ready_count": sum(1 for s in sections_status if s["present"]),
        "rules": rules_status,
        "scale": scale,
        "relations": relations,
        "wireframe": wireframe,
        "metadata": extract_srs_metadata(clean_text),
    }
