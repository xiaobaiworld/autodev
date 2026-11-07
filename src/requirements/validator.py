# 定位: validator.py 按照 SPEC-REQ-STANDARD-v1.0 规范，统一负责 SRS 文档的程序化语法/语义校验、章节切分、元数据提取与 RULE-01~09 逐项透视（O2 收敛）。
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


REQUIRED_SECTIONS = [
    "## 1. 需求标识与元数据",
    # 第 2 节在规范中支持 "需求规模分类与需求关联网络" 或 "架构拓扑与近期关联"
    "## 2.",
    "## 3. 核心背景与业务目标 (Why & What)",
    "## 4. 业务用例与核心流程 (Scope)",
    "## 5. 明确非目标与边界 (Non-goals)",
    "## 6. 外部界面原型草图 (UI Wireframe)",
    "## 7. 业务约束与前置依赖",
    "## 8. 可量化验收标准清单 (Acceptance Criteria)",
    "## 9. 下游架构设计关注点",
]

SECTION_SPECS: list[tuple[int, str, list[str]]] = [
    (1, "## 1. 需求标识与元数据", ["## 1. 需求标识与元数据"]),
    (2, "## 2. 需求规模分类与需求关联网络", ["## 2. 需求规模分类与需求关联网络", "## 2. 架构拓扑与近期关联"]),
    (3, "## 3. 核心背景与业务目标 (Why & What)", ["## 3. 核心背景与业务目标 (Why & What)"]),
    (4, "## 4. 业务用例与核心流程 (Scope)", ["## 4. 业务用例与核心流程 (Scope)"]),
    (5, "## 5. 明确非目标与边界 (Non-goals)", ["## 5. 明确非目标与边界 (Non-goals)"]),
    (6, "## 6. 外部界面原型草图 (UI Wireframe)", ["## 6. 外部界面原型草图 (UI Wireframe)"]),
    (7, "## 7. 业务约束与前置依赖", ["## 7. 业务约束与前置依赖"]),
    (8, "## 8. 可量化验收标准清单 (Acceptance Criteria)", ["## 8. 可量化验收标准清单 (Acceptance Criteria)"]),
    (9, "## 9. 下游架构设计关注点", ["## 9. 下游架构设计关注点"]),
]

RULE_DESCRIPTIONS: list[tuple[str, str]] = [
    ("RULE-01", "UTF-8 编码与 REQ-*.md 命名规范"),
    ("RULE-02", "九大标准章节标题完整性"),
    ("RULE-03", "需求规模类别、模块归属与关系矩阵"),
    ("RULE-04", "核心业务背景与业务目标双要素"),
    ("RULE-05", "明确非目标与防膨胀边界声明"),
    ("RULE-06", "外部界面等宽线框图 (```text)"),
    ("RULE-07", "可量化验收标准场景清单"),
    ("RULE-08", "严禁越权编写 SQL 或实现代码"),
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


def extract_srs_metadata(srs_text: str) -> dict[str, Any]:
    """从 9 章节 SRS 文档中提取核心元数据（标题、摘要、范围、验收标准），供 S1 基线与 Web 预览共用。"""
    clean_text = strip_validation_comment(srs_text)
    if not clean_text:
        return {
            "title": "未命名需求",
            "summary": "",
            "scope": "",
            "acceptance_criteria": [],
        }

    title_match = re.search(
        r"^#\s+(?:需求规格说明书|软件需求规格说明(?:书)?(?:（SRS）|（草案）)?)[：:]?\s*(.*?)\s*$",
        clean_text,
        flags=re.MULTILINE,
    )
    title = title_match.group(1).strip() if (title_match and title_match.group(1).strip()) else ""
    if not title:
        name_match = re.search(r"\*\*需求名称\*\*[：:]\s*(.+?)\s*$", clean_text, flags=re.MULTILINE)
        title = name_match.group(1).strip() if name_match else "未命名需求"

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
        "title": title,
        "summary": summary,
        "scope": scope_summary,
        "acceptance_criteria": ac_items or ["满足 SRS 第 8 节全部可量化验收标准"],
    }


def validate_requirement_spec(content: str) -> ValidationResult:
    """对传入的 Markdown 需求规格说明书进行程序化规则检查。"""
    errors: list[str] = []
    warnings: list[str] = []

    text = strip_validation_comment(content)
    if not text:
        return ValidationResult(is_valid=False, errors=["[RULE-00] 需求文档内容为空"])

    # RULE-02: 检查 9 大必备章节标题
    for sec in REQUIRED_SECTIONS:
        if sec == "## 2.":
            if "## 2. 需求规模分类与需求关联网络" not in text and "## 2. 架构拓扑与近期关联" not in text:
                errors.append("[RULE-02] 缺失必备章节标题: '## 2. 需求规模分类与需求关联网络' (或兼容标题)")
        elif sec not in text:
            errors.append(f"[RULE-02] 缺失必备章节标题: '{sec}'")

    # RULE-03: 需求类别与拓扑矩阵检查
    has_hierarchy = "功能层级归属" in text or "模块归属" in text or "功能层级与模块归属" in text
    has_affinity = any(k in text for k in ("近期功能关联", "需求关联", "需求关系", "关系矩阵", "Parent", "Depends-on", "Relates-to"))
    has_scale = any(k in text for k in ("需求规模", "规模类别", "大需求", "小需求", "Epic", "Feature", "Sub-feature"))

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
    if "非目标" in text:
        sec5_match = re.search(r"## 5\. 明确非目标与边界.*?(\n##|\Z)", text, re.DOTALL)
        if sec5_match:
            sec5_text = sec5_match.group(0)
            if "❌" not in sec5_text and "-" not in sec5_text:
                errors.append("[RULE-05] 第 5 节明确非目标必须包含至少一项带 '❌' 或 '-' 的具体排除条目")
        else:
            errors.append("[RULE-05] 无法定位第 5 节非目标内容")

    # RULE-06: 外部界面原型线框图检查
    if "## 6. 外部界面原型草图" in text:
        sec6_match = re.search(r"## 6\. 外部界面原型草图.*?(\n##|\Z)", text, re.DOTALL)
        if sec6_match:
            sec6_text = sec6_match.group(0)
            if "```text" not in sec6_text:
                errors.append("[RULE-06] 第 6 节必须包含 ```text 代码块形式的低保真线框图")
            else:
                code_lines = [l for l in sec6_text.splitlines() if l.strip()]
                if len(code_lines) < 5:
                    warnings.append("[RULE-06-WARN] 界面原型线框图行数偏少，建议至少 5 行以展示布局")
        else:
            errors.append("[RULE-06] 无法定位第 6 节界面原型内容")

    # RULE-07: 可量化验收标准检查
    if "## 8. 可量化验收标准清单" in text:
        sec8_match = re.search(r"## 8\. 可量化验收标准清单.*?(\n##|\Z)", text, re.DOTALL)
        if sec8_match:
            sec8_text = sec8_match.group(0)
            if "场景" not in sec8_text and "Scenario" not in sec8_text and "1." not in sec8_text:
                errors.append("[RULE-07] 第 8 节验收标准必须包含具体场景条目（如 场景 1、场景 2）")
        else:
            errors.append("[RULE-07] 无法定位第 8 节验收标准内容")

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
    """统一透视 SRS 文档的 9 大章节状态、RULE-01~09 逐条结果、规模类别、关系矩阵与原型线框图。"""
    clean_text = strip_validation_comment(content)
    v_res = validate_requirement_spec(clean_text)

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
    wf_match = re.search(r"## 6\.\s+外部界面原型草图.*?```text\n(.*?)```", clean_text, flags=re.S)
    if wf_match:
        wireframe = wf_match.group(1).rstrip()

    return {
        "is_valid": v_res.is_valid,
        "errors": v_res.errors,
        "warnings": v_res.warnings,
        "sections": sections_status,
        "sections_ready_count": sum(1 for s in sections_status if s["present"]),
        "rules": rules_status,
        "scale": scale,
        "relations": relations,
        "wireframe": wireframe,
        "metadata": extract_srs_metadata(clean_text),
    }
