"""窗格认领：标签为主，手填地址为备用（设计 2.2）。纯函数，不调用 hc。"""


class ClaimError(Exception):
    pass


def claim_panes(terminals, get_labels, self_addr, roles, fallback=None):
    """返回 {角色: 地址}。

    terminals: `hc ls` 的 terminals 列表
    get_labels: 地址 -> 标签 dict（调用方包装 `hc get`）
    self_addr: 主控自己的窗格地址
    fallback: 手填的 {角色: 地址}，None 表示没有
    """
    by_addr = {t["address"]: t for t in terminals}
    me = by_addr.get(self_addr)
    if me is None:
        raise ClaimError(f"主控窗格 {self_addr} 不在 hc ls 里")
    space = me["where"]
    # 只在同一空间内认领，且不认领自己
    cand = [a for a, t in by_addr.items()
            if t["where"] == space and a != self_addr and t.get("state") == "live"]

    found = {}
    for addr in cand:
        role = get_labels(addr).get("role")
        if role in roles:
            if role in found:
                raise ClaimError(f"角色 {role} 被重复标记：{found[role]}、{addr}")
            found[role] = addr

    fb = _check_fallback(fallback, cand, roles) if fallback else None
    if fb:
        diff = [r for r in found if fb[r] != found[r]]
        if diff:
            raise ClaimError("标签与手填地址不一致：" + "、".join(
                f"{r}（标签 {found[r]}，手填 {fb[r]}）" for r in diff))

    if len(found) == len(roles):
        return found
    if fb:
        return fb
    missing = [r for r in roles if r not in found]
    raise ClaimError("缺少窗格：" + "、".join(missing))


def _check_fallback(fallback, cand, roles):
    missing = [r for r in roles if r not in fallback]
    if missing:
        raise ClaimError("手填地址缺少角色：" + "、".join(missing))
    seen = {}
    for role in roles:
        addr = fallback[role]
        if addr not in cand:
            raise ClaimError(f"手填地址 {addr}（{role}）不是本空间内可用的窗格")
        if addr in seen:
            raise ClaimError(f"手填地址 {addr} 被 {seen[addr]} 和 {role} 重复使用")
        seen[addr] = role
    return {r: fallback[r] for r in roles}
