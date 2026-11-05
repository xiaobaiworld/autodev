"""读取 config.yaml 的 cockpit 段。本机无 PyYAML，只解析这一段的三个键。
# ponytail: 正则读固定格式；config 变复杂时改用 JSON 或引入解析库。
"""
import re


class ConfigError(Exception):
    pass


def parse_cockpit(text):
    m = re.search(r"^cockpit:[^\n]*\n((?:[ \t]+[^\n]*\n?|\n)*)", text, re.M)
    if not m:
        raise ConfigError("config.yaml 缺少 cockpit 段")
    body = re.sub(r"[ \t]+#.*", "", m.group(1))

    def key(name):
        k = re.search(rf"^[ \t]+{name}:[ \t]*(.+?)[ \t]*$", body, re.M)
        return k.group(1) if k else None

    claim = key("claim")
    if claim not in ("label", "address"):
        raise ConfigError(f"cockpit.claim 必须是 label 或 address，得到 {claim!r}")
    refresh = key("refresh_seconds")
    if not refresh or not refresh.isdigit() or int(refresh) < 1:
        raise ConfigError(f"cockpit.refresh_seconds 必须是正整数，得到 {refresh!r}")
    panes = key("panes")
    pm = re.fullmatch(r"\[(.*)\]", panes or "")
    roles = [r.strip() for r in pm.group(1).split(",") if r.strip()] if pm else []
    if not roles:
        raise ConfigError("cockpit.panes 必须是非空列表，如 [a, b]")
    return {"claim": claim, "refresh_seconds": int(refresh), "panes": roles}
