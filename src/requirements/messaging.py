"""Requirement application adapter for an authenticated generic message gateway."""
import hashlib
import json

from cockpit.store import acquire_lock, atomic_write
from .session import SessionError


class RequirementsMessages:
    def __init__(self, store):
        self.store = store
        self.base = store.root / 'workspace' / 'channels' / 'requirements'
        self.base.mkdir(parents=True, exist_ok=True)

    def __call__(self, context, command):
        identity = json.dumps([context['channel'], context['actor'], context['conversation']])
        key = hashlib.sha256(identity.encode()).hexdigest()
        path = self.base / (key + '.json')
        lock = acquire_lock(self.base / (key + '.lock'))
        try:
            bindings = json.loads(path.read_text()) if path.exists() else []
            action = command.get('action')
            sid = command.get('session_id')
            if action == 'create':
                result = self.store.create(command.get('project_id'), command.get('text'),
                                           analyst=command.get('analyst'), reviewer=command.get('reviewer'),
                                           review_limit=command.get('review_limit'))
                bindings.append(result['id'])
                atomic_write(path, json.dumps(bindings))
            elif action == 'list':
                result = [s for s in self.store.list_sessions() if s['id'] in bindings]
            else:
                if sid not in bindings:
                    raise SessionError('forbidden', '该会话未绑定当前用户和对话；请从此入口创建需求')
                if action == 'show':
                    result = self.store.status(sid)
                elif action == 'reply':
                    result = self.store.submit(sid, command.get('text'), 'channel:' + context['event_id'])
                elif action == 'step':
                    result = self.store.advance(sid)
                elif action == 'confirm':
                    result = self.store.confirm(sid, command.get('version'), command.get('hash'))
                elif action == 'export':
                    result = self.store.export(sid, command.get('version'))
                elif action in {'retry', 'reopen'}:
                    result = getattr(self.store, action)(sid)
                else:
                    raise SessionError('invalid-action', '不支持的需求操作')
            return dict(application='requirements', session=result)
        finally:
            lock.close()
