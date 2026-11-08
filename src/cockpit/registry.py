"""Machine agent/model catalog; credentials are names until invocation."""
import os
from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parents[2]
ADAPTERS = {'claude', 'codex', 'agy', 'ollama'}
MODES = {'cli_session', 'cli_stateless'}
AVAILABILITY = {'unknown', 'installed_only', 'verified', 'unavailable'}


class Registry:
    def __init__(self, data):
        if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] != 1 or not isinstance(data.get('machine'), str) or not data['machine']:
            raise ValueError('注册表需要 schema_version=1 和 machine')
        self.data = data
        self.agents = data.get('agents', {})
        self.models = data.get('models', {})
        self.defaults = data.get('defaults', {})
        if not all(isinstance(x, dict) for x in [self.agents, self.models, self.defaults]):
            raise ValueError('注册表 agents/models/defaults 必须是表')
        self._validate_secrets(data)
        for name, agent in self.agents.items():
            self._entry(name, agent)
            if agent.get('adapter') not in ADAPTERS or not isinstance(agent.get('executable'), str) or not agent['executable']:
                raise ValueError(f'Agent {name} 调用入口无效')
            modes = agent.get('invocation_modes', [])
            if not isinstance(modes, list) or not modes or not all(isinstance(x, str) and x in MODES for x in modes):
                raise ValueError(f'Agent {name} 调用方式无效')
        for name, model in self.models.items():
            self._entry(name, model)
            for key in ['vendor', 'model_id', 'agent', 'invocation_mode']:
                if not isinstance(model.get(key), str) or not model[key]:
                    raise ValueError(f'模型 {name} 缺少 {key}')
            if model['agent'] not in self.agents:
                raise ValueError(f'模型 {name} 引用未登记 Agent')
            if model['invocation_mode'] not in self.agents[model['agent']]['invocation_modes']:
                raise ValueError(f'模型 {name} 调用方式不匹配')
            if model['model_id'].lower() in {'default', 'sonnet', 'opus', 'haiku', 'claude', 'gpt', 'gemini'}:
                raise ValueError(f'模型 {name} 必须使用完整模型 ID')
            groups = []
            for field in ['supported_tasks', 'unsupported_tasks', 'unverified_tasks']:
                values = model.get(field, [])
                if not isinstance(values, list) or not all(isinstance(x, str) and x for x in values):
                    raise ValueError(f'模型 {name} 的 {field} 无效')
                groups.append(set(values))
            if any(groups[i] & groups[j] for i in range(3) for j in range(i + 1, 3)):
                raise ValueError(f'模型 {name} 的能力集合不能重叠')
            auth = model.get('auth', {'type': 'cli_login'})
            if not isinstance(auth, dict) or auth.get('type') not in {'cli_login', 'environment', 'none'}:
                raise ValueError(f'模型 {name} 凭证方式无效')
            if set(auth) - {'type', 'api_key_env'}:
                raise ValueError('凭证配置仅接受方式和环境变量名')
            env_name = auth.get('api_key_env', '')
            if auth['type'] == 'environment' and (not isinstance(env_name, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', env_name)):
                raise ValueError(f'模型 {name} 需要环境变量名 api_key_env')
        for role, default in self.defaults.items():
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', role):
                raise ValueError('角色标识无效')
            if not isinstance(default, dict) or not isinstance(default.get('model'), str) or default['model'] not in self.models:
                raise ValueError(f'角色 {role} 引用未登记模型')
            if default.get('agent') != self.models[default['model']]['agent']:
                raise ValueError(f'角色 {role} 的 Agent 与模型不匹配')

    @staticmethod
    def _validate_secrets(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower() in {'api_key', 'key', 'token', 'secret', 'password', 'app_secret'}:
                    raise ValueError('注册表不得保存凭证值，请引用环境变量名')
                Registry._validate_secrets(child)
        elif isinstance(value, list):
            for child in value:
                Registry._validate_secrets(child)

    @staticmethod
    def _entry(name, entry):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', name):
            raise ValueError('注册项标识无效')
        if not isinstance(entry, dict) or not isinstance(entry.get('name'), str) or not entry['name']:
            raise ValueError(f'注册项 {name} 缺少名称')
        if type(entry.get('enabled')) is not bool or entry.get('availability') not in AVAILABILITY:
            raise ValueError(f'注册项 {name} 可用性无效')

    def resolve(self, name, task=None):
        if name not in self.models:
            raise ValueError(f'未登记的模型 {name}')
        model = self.models[name]
        agent = self.agents[model['agent']]
        if any(not x['enabled'] or x['availability'] in {'unknown', 'unavailable'} for x in [model, agent]):
            raise ValueError(f'模型 {name} 或其 Agent 未启用/不可用')
        if task and task not in model.get('supported_tasks', []):
            raise ValueError(f'模型 {name} 尚无任务 {task} 的合格能力登记')
        return dict(cli=agent['adapter'], executable=agent['executable'], vendor=model['vendor'],
                    model=model['model_id'], effort=model.get('effort', 'medium'), registry_model=name,
                    invocation_mode=model['invocation_mode'], supported_tasks=model.get('supported_tasks', []),
                    unsupported_tasks=model.get('unsupported_tasks', []), unverified_tasks=model.get('unverified_tasks', []),
                    capability_notes=model.get('capability_notes', ''), availability=model['availability'],
                    auth=dict(model.get('auth', {'type': 'cli_login'})))

    def select(self, role, model=None, inherited=None):
        name = model or inherited or self.defaults.get(role, {}).get('model')
        if not name:
            raise ValueError(f'角色 {role} 没有默认模型')
        return self.resolve(name, task=role)

    def available(self):
        return {name: self.resolve(name) for name, model in self.models.items()
                if model['enabled'] and model['availability'] not in {'unknown', 'unavailable'}
                and self.agents[model['agent']]['enabled']
                and self.agents[model['agent']]['availability'] not in {'unknown', 'unavailable'}}


def registry_path(configured='config/agents.toml'):
    explicit = os.environ.get('AUTODEV_AGENT_REGISTRY')
    local = ROOT / 'workspace' / 'agent-registry.toml'
    return Path(explicit).expanduser() if explicit else local if local.exists() else ROOT / configured


def load_registry(path=None):
    target = Path(path) if path is not None else registry_path()
    try:
        data = tomllib.loads(target.read_text(encoding='utf-8'))
    except tomllib.TOMLDecodeError:
        raise ValueError('Agent 注册表 TOML 格式无效') from None
    return Registry(data)


def invocation_env(agent):
    env = dict(os.environ)
    auth = agent.get('auth', {})
    if not isinstance(auth, dict):
        raise ValueError('凭证配置需要环境变量名，不能包含凭证值')
    if auth.get('type') == 'environment':
        name = auth['api_key_env']
        if not env.get(name):
            raise ValueError(f'缺少模型调用环境变量 {name}')
    return env


def main(argv=None):
    import argparse
    import json
    import sys
    parser = argparse.ArgumentParser(description='检查本机 Agent/模型注册表，不调用模型')
    parser.add_argument('--file', type=Path)
    parser.add_argument('--role')
    parser.add_argument('--model')
    args = parser.parse_args(argv)
    try:
        registry = load_registry(args.file)
        result = registry.select(args.role, model=args.model) if args.role else {
            'machine': registry.data['machine'], 'agents': registry.agents,
            'models': registry.available(), 'defaults': registry.defaults}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
