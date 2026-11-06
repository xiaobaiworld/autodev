"""需求类型（kind）：用路径写法，前面是大类，后面是子类，如 pipeline/design。

先只登记一个。以后同一大类下分子类，只是多登记一行，不改字段，也不改读取代码。
讨论记录见 docs/design/2026-11-06-ticket-model.md。
"""
import re

# 路径 -> 一句话说明。只登记真正在用的；新类型先在这里加，再写进 docs/DATA_SPEC.md。
KINDS = {
    "pipeline/design": "需求分析、设计、设计审查（S1 到 S3），产物是一份可审查的设计和开发计划",
    "pipeline/build": "在 design 之后继续编码（S1 到 S4），产物是代码目录里的改动和执行报告；检查、代码审查等后续阶段待接",
}
DEFAULT_KIND = "pipeline/design"
_PATH = re.compile(r"[a-z][a-z0-9_-]*(/[a-z][a-z0-9_-]*)*")


class UnknownKind(ValueError):
    pass


def check_kind(kind):
    """返回合法且已登记的类型，否则抛 UnknownKind，并列出已登记的。"""
    if not isinstance(kind, str) or not _PATH.fullmatch(kind):
        raise UnknownKind(f"类型 {kind!r} 的写法不对：用小写字母、数字、-、_，层级用 /，如 pipeline/design")
    if kind not in KINDS:
        raise UnknownKind(f"类型 {kind!r} 没有登记。已登记：{', '.join(sorted(KINDS))}")
    return kind


def kind_matches(kind, prefix):
    """kind 是不是 prefix 本身或它的子类。按整段比较：pipeline/design 属于 pipeline，不属于 pipe。"""
    return isinstance(kind, str) and (kind == prefix or kind.startswith(prefix + "/"))


def kind_of(state):
    """读 state.json 里的类型。老记录没有这个字段时返回 None，不替它猜一个。"""
    return state.get("kind")


def kind_label(kind):
    if kind is None:
        return "未分类"
    return f"{kind}（{KINDS[kind].split('，')[0]}）" if kind in KINDS else kind
