"""Configuration and prompts; AutoLoop adapter is added after local protocol tests."""
from pathlib import Path
from cockpit.agents import parse_agents, parse_limits, parse_roles

ROOT = Path(__file__).resolve().parents[2]


def load_settings(config=None):
    text = Path(config or ROOT / 'config.yaml').read_text(encoding='utf-8')
    agents, roles, limits = parse_agents(text), parse_roles(text), parse_limits(text)
    agents = {name: {k: v for k, v in a.items() if k in {'cli', 'vendor', 'model', 'effort', 'executable', 'auth', 'supported_tasks'}}
              for name, a in agents.items()}
    return dict(agents=agents, analyst=roles.get('requirements_analyst', roles['analyst']),
                reviewer=roles.get('requirements_reviewer', roles['design_reviewer']),
                review_limit=limits.get('requirements_review_rounds', 3),
                timeout_s=60 * limits.get('step_timeout_minutes', 15))


def prompt_text(kind):
    name = 'review' if kind == 'review' else 'clarify'
    return (ROOT / 'templates/requirements' / (name + '.md')).read_text(), 'v1'


class AgentError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class DemoAgent:
    """Explicit no-network simulator; its sessions are marked demo, never real reviews."""
    def __call__(self, data, folder, timeout):
        import copy
        import json
        import re
        from .document import CHECKLIST, SECTIONS
        if data['kind'] == 'review':
            return json.dumps(dict(reply='演示审核通过（模拟结果，不代表真实模型审核）', version=data['version'],
                                   hash=data['hash'], verdict='PASS', findings=[]), ensure_ascii=False)
        draft = copy.deepcopy(data['draft']) if data['draft'] else dict(
            schema_version=1, sections={k: '' for k in SECTIONS}, functions=[], acceptance=[],
            checklist=[dict(id=x['id'], status='open', answer='', sources=[]) for x in CHECKLIST],
            suggestions=[], open_questions=[])
        aliases = {'目标': 'goal', '用户': 'audience', '功能': 'functions', '范围': 'scope', '约束': 'constraints', '验收': 'acceptance'}
        for message in data['messages']:
            for line in message['text'].splitlines():
                match = re.match(r'^(目标|用户|功能|范围|约束|验收)\s*[:：]\s*(.+)$', line.strip())
                if not match:
                    continue
                key, value = aliases[match[1]], match[2]
                sources = [message['id']]
                if key in SECTIONS:
                    draft['sections'][key] = value
                else:
                    draft[key] = [dict(id='F1' if key == 'functions' else 'A1', text=value, sources=sources)]
                item = next(x for x in draft['checklist'] if x['id'] == key)
                item.update(status='answered', answer=value, sources=sources)
        missing = [x['id'] for x in draft['checklist'] if x['status'] == 'open']
        reply = ('这是无费用模拟。请按“目标：…、用户：…、功能：…、范围：…、约束：…、验收：…”分行补充。尚缺：'
                 + '、'.join(missing)) if missing else '演示草稿已整理，将送模拟审核；请阅读后明确确认。'
        return json.dumps(dict(reply=reply, draft=draft), ensure_ascii=False)


class HubAgent:
    can_resume = True

    def __init__(self, root, home, hub=None, clock=None):
        import time
        from driver.hub import Hub, load_config
        self.root, self.home = Path(root).resolve(), Path(home).resolve()
        self.hub = hub or Hub(load_config(self.home))
        self.clock = clock or time.monotonic

    def install(self, data):
        import hashlib
        import json
        import sys
        import time
        from cockpit.store import acquire_lock
        from driver.setup import install_rules
        namespace = hashlib.sha256((str(self.root) + data['session_id']).encode()).hexdigest()[:12]
        prefix = 'requirements-' + namespace
        etype = 'requirements.' + namespace + '.' + data['kind']
        with acquire_lock(self.root / 'workspace' / '.lock'):
            home_lock = acquire_lock(self.home / '.requirements-rules.lock')
            try:
                path = self.home / 'rules.json'
                base = json.loads(path.read_text())
                self.hub.state()  # Fail before touching rules if the hub is unavailable.
                worker = next(iter(base['agents'].values()))['worker']
                name = prefix + '-' + data['role']
                agent = dict(name=name, worker=worker, use='command', access='read',
                             timeout=max(1, round(data.get('timeout_s', 900) / 60) + 1),
                             command=[sys.executable, str(Path(__file__).with_name('worker.py')),
                                      '--input-root', str(self.root / 'workspace'), '--context', '{context}'])
                if name in base['agents'] and base['agents'][name] != agent:
                    raise AgentError('rule-conflict', '需求模块规则冲突，不能覆盖正在使用的配置')
                base['agents'][name] = agent
                rule = dict(name=prefix + '-' + data['kind'], when=dict(source='local', types=[etype]),
                            to=name, cwd=str(self.root / 'workspace'), tell='never')
                base['rules'] = [r for r in base['rules'] if r['name'] != rule['name']] + [rule]
                install_rules(self.home, base)
            finally:
                home_lock.close()
            until = time.monotonic() + 10
            while not any(line['id'] == rule['name'] and etype in line.get('types', [])
                          for line in self.hub.state().get('lines', [])):
                if time.monotonic() >= until:
                    raise AgentError('rules-not-loaded', '中台未加载新规则，未派发模型调用')
                time.sleep(.1)
        return etype

    def __call__(self, data, folder, timeout):
        from cockpit.store import atomic_write
        from driver.hub import RunTracker
        folder = Path(folder).resolve()
        subject = folder.relative_to(self.root / 'workspace').as_posix()
        data['timeout_s'] = timeout
        atomic_write(folder / 'input.json', __import__('json').dumps(data, ensure_ascii=False))
        etype = self.install(data)
        tracker = RunTracker()
        deadline = self.clock() + timeout
        self.hub.emit(data['call_id'], etype, subject, '需求梳理与审核')
        while self.clock() < deadline:
            try:
                for fact in self.hub.facts(after=tracker.seq, timeout=min(2, max(.1, deadline - self.clock()))):
                    tracker.feed(fact)
                    st = tracker.status(data['call_id'])
                    if not st:
                        continue
                    if st['state'] == 'retrying' or st['raw'] == 'cancelled':
                        atomic_write(folder / 'cancelled', 'cancelled')
                        self.hub.cancel(st['run'])
                        raise AgentError('agent-failed', 'Agent 运行失败，请检查 CLI 登录及配置后重试')
                    if st['state'] == 'ended':
                        out = folder / 'raw-output.txt'
                        if not out.is_file() or out.is_symlink():
                            raise AgentError('missing-output', 'Agent 未留下回复')
                        return out.read_text(encoding='utf-8')
                    if self.clock() >= deadline:
                        break
            except AgentError:
                raise
            except Exception:
                atomic_write(folder / 'cancelled', 'cancelled')
                st = tracker.status(data['call_id'])
                if st:
                    self.hub.cancel(st['run'])
                raise AgentError('hub-unavailable', '中台连接中断，请恢复连接后重试') from None
        atomic_write(folder / 'cancelled', 'cancelled')
        st = tracker.status(data['call_id'])
        if st:
            self.hub.cancel(st['run'])
        raise TimeoutError('Agent timeout')
