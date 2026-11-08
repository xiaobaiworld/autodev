"""从 config.yaml 读 agents、roles，（模型规则见 docs/MODELS.md；启动命令由 autoloop 按规则里的 use/model/effort 生成）。
# ponytail: 正则读固定格式，和 config.py 一样；config 变复杂时改 JSON 或引入解析库。
"""
import re


def validate_role(agents, role, name):
    if name not in agents:
        raise ValueError(f'角色 {role} 的模型 {name} 未登记或不可用')
    if 'supported_tasks' in agents[name] and role not in agents[name]['supported_tasks']:
        raise ValueError(f'模型 {name} 没有角色 {role} 的合格能力登记')


def _section(text, name):
    m = re.search(rf"^{name}:[^\n]*\n((?:[ \t]+[^\n]*\n?|\n)*)", text, re.M)
    if not m:
        raise ValueError(f"config.yaml 缺少 {name} 段")
    return re.sub(r"[ \t]+#.*", "", m.group(1))


def parse_agents(text):
    if re.search(r'^agent_registry:', text, re.M):
        from cockpit.registry import load_registry, registry_path
        configured = re.search(r'^agent_registry:\s*(\S+)', text, re.M).group(1)
        return load_registry(registry_path(configured)).available()
    out, cur = {}, None
    for line in _section(text, "agents").splitlines():
        m = re.match(r"^  (\S+):\s*$", line)
        if m:
            cur = out.setdefault(m.group(1), {})
            continue
        m = re.match(r"^    (\w+):\s*(\S.*?)\s*$", line)
        if m and cur is not None:
            cur[m.group(1)] = m.group(2)
    return out


def parse_roles(text):
    out = {}
    if re.search(r'^agent_registry:', text, re.M):
        from cockpit.registry import load_registry, registry_path
        configured = re.search(r'^agent_registry:\s*(\S+)', text, re.M).group(1)
        registry = load_registry(registry_path(configured))
        out = {role: value['model'] for role, value in registry.defaults.items()}
    if not re.search(r'^roles:', text, re.M):
        if out:
            return out
        raise ValueError('配置缺少 roles 或注册表默认值')
    for line in _section(text, "roles").splitlines():
        m = re.match(r"^\s+(\w+):\s*\{\s*agent:\s*(\S+?)\s*\}\s*$", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def parse_limits(text):
    """limits 段的整数项，如 step_retries、step_timeout_minutes。"""
    out = {}
    for line in _section(text, "limits").splitlines():
        m = re.match(r"^\s+(\w+):\s*(\d+)\s*$", line)
        if m:
            out[m.group(1)] = int(m.group(2))
    return out
