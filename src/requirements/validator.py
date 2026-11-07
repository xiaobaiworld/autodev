# 定位: validator.py 按照 SPEC-REQ-STANDARD-v1.0 规范，对需求规格说明书产出物进行确定性程序化语法与语义校验。
from __future__ import annotations

import re
from dataclasses import dataclass, field


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

FORBIDDEN_TECH_PATTERNS = [
    r"CREATE\s+TABLE",
    r"ALTER\s+TABLE",
    r"SELECT\s+.+\s+FROM",
    r"INSERT\s+INTO",
    r"def\s+[a-zA-Z0-9_]+\s*\(",
    r"class\s+[a-zA-Z0-9_]+[:\(]",
]


def validate_requirement_spec(content: str) -> ValidationResult:
    """对传入的 Markdown 需求规格说明书进行程序化规则检查。"""
    errors: list[str] = []
    warnings: list[str] = []

    text = content.strip()
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
    has_hierarchy = "功能层级归属" in text or "模块归属" in text
    has_affinity = any(k in text for k in ("近期功能关联", "需求关联", "需求关系", "Parent", "Depends-on", "Relates-to"))
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
        # 截取第 5 节内容
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
