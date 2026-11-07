"""Platform-neutral allowlist, routing and durable delivery deduplication.

An upstream transport must verify platform signatures and supply authenticated
actor IDs. This component does not expose a public webhook or send messages.
"""
import hashlib
import json
from pathlib import Path

from cockpit.store import acquire_lock, atomic_write


class ChannelError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class MessageGateway:
    def __init__(self, root, applications, allowed_actors):
        self.base = Path(root).resolve() / 'workspace' / 'channels'
        self.base.mkdir(parents=True, exist_ok=True)
        self.applications = applications
        self.allowed = set(allowed_actors)

    def receive(self, channel, actor, conversation, event_id, application, payload):
        if (channel, actor) not in self.allowed:
            raise ChannelError('forbidden', '消息来源不在授权名单中')
        if application not in self.applications:
            raise ChannelError('unknown-application', '未登记的应用')
        if not all(isinstance(x, str) and x and len(x) < 256 for x in [channel, actor, conversation, event_id]):
            raise ChannelError('invalid-message', '消息标识无效')
        identity = json.dumps([channel, actor, conversation, event_id], ensure_ascii=False)
        key = hashlib.sha256(identity.encode()).hexdigest()
        request_hash = hashlib.sha256(json.dumps([application, payload], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        path = self.base / (key + '.json')
        lock = acquire_lock(self.base / (key + '.lock'))
        try:
            if path.exists():
                prior = json.loads(path.read_text())
                if prior['hash'] != request_hash:
                    raise ChannelError('conflict', '同一平台消息 ID 对应不同操作')
                if prior['status'] == 'done':
                    return prior['result']
                raise ChannelError('delivery-uncertain', '上次消息可能已执行，请先查看会话，不自动重复执行')
            atomic_write(path, json.dumps(dict(hash=request_hash, status='processing')))
            context = dict(channel=channel, actor=actor, conversation=conversation, event_id=event_id)
            try:
                result = self.applications[application](context, payload)
            except Exception:
                atomic_write(path, json.dumps(dict(hash=request_hash, status='failed')))
                raise
            atomic_write(path, json.dumps(dict(hash=request_hash, status='done', result=result), ensure_ascii=False))
            return result
        finally:
            lock.close()
