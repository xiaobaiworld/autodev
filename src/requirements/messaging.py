"""Requirement application adapter for an authenticated generic message gateway."""
import hashlib
import json

from cockpit.store import acquire_lock, atomic_write
from .versioned_session import SessionError


class RequirementsMessages:
    def __init__(self, store, clock=None):
        import time
        self.clock = clock or time.time
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
            if action == 'bind':
                import re
                code=command.get('code','')
                if not isinstance(code,str) or not re.fullmatch('[a-f0-9]{12}',code):
                    raise SessionError('invalid-pairing','配对码无效或已过期')
                token=hashlib.sha256(code.encode()).hexdigest()
                pairing_path=self.base.parent/'pairings'/(token+'.json')
                pairing_lock=acquire_lock(pairing_path.with_suffix('.lock'))
                try:
                    if not pairing_path.is_file() or pairing_path.is_symlink():
                        raise SessionError('invalid-pairing','配对码无效或已过期')
                    pairing=json.loads(pairing_path.read_text())
                    if pairing['used_by'] is not None or pairing['expires_at']<=self.clock() or pairing['demo']!=self.store.demo:
                        raise SessionError('invalid-pairing','配对码无效或已过期')
                    result=self.store.status(pairing['session_id'])
                    pairing['used_by']=key
                    atomic_write(pairing_path,json.dumps(pairing))
                    if result['id'] not in bindings:
                        bindings.append(result['id'])
                    atomic_write(path,json.dumps(bindings))
                finally:
                    pairing_lock.close()
            elif action == 'create':
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


def issue_pairing(store, sid, clock=None):
    """Trusted local operation: grant one channel a short-lived, one-use binding."""
    import secrets
    import time
    state=store.status(sid)
    code=secrets.token_hex(6)
    folder=store.root/'workspace'/'channels'/'pairings'
    folder.mkdir(parents=True,exist_ok=True)
    key=hashlib.sha256(code.encode()).hexdigest()
    expires=(clock or time.time)()+300
    atomic_write(folder/(key+'.json'),json.dumps(dict(session_id=sid,demo=state['demo'],expires_at=expires,used_by=None)))
    (folder/(key+'.json')).chmod(0o600)
    return dict(session_id=sid,code=code,expires_at=expires,command='/需求 绑定 '+code)
