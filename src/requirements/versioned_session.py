"""Transport-independent, file-backed requirement sessions and review loop."""
import copy
import json
import os
import re
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from cockpit.store import LockError, acquire_lock, atomic_write, now_iso
from .document import (CHECKLIST, DocumentError, check_draft, digest, encoded,
                       fields, render, require, validate_draft, validate_review)


class SessionError(ValueError):
    def __init__(self, code, message=None):
        self.code = code
        super().__init__(message or code)


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise SessionError('corrupt-data', '记录缺失或损坏，请检查会话文件') from None


class SessionStore:
    def __init__(self, root, invoke=None, settings=None, wall_clock=now_iso, monotonic=time.monotonic, demo=False):
        if settings is None:
            from .agent import load_settings
            settings = load_settings()
        self.root = Path(root).resolve()
        self.base = self.root / 'workspace' / 'requirements'
        self.base.mkdir(parents=True, exist_ok=True)
        if self.base.is_symlink() or self.base.resolve() != self.base:
            raise SessionError('invalid-path', '数据目录不能经过符号链接')
        self.settings = copy.deepcopy(settings)
        self.invoke, self.wall_clock, self.monotonic = invoke, wall_clock, monotonic
        self.demo = demo

    def _path(self, sid, *parts):
        if not isinstance(sid, str) or not re.fullmatch(r'Q[0-9a-f]{12}', sid):
            raise SessionError('invalid-id', '会话 ID 无效')
        path = self.base / sid
        for part in parts:
            path /= part
        try:
            path.resolve().relative_to(self.base)
        except (ValueError, OSError):
            raise SessionError('invalid-path', '文件路径越界') from None
        for candidate in [path, *path.parents]:
            if candidate == self.base:
                break
            if candidate.is_symlink():
                raise SessionError('invalid-path', '会话文件不能是符号链接')
        return path

    @contextmanager
    def _lock(self, sid):
        try:
            lock = acquire_lock(self._path(sid, '.lock'))
        except LockError:
            raise SessionError('busy', '此会话正在处理，请稍后再试') from None
        try:
            yield
        finally:
            lock.close()

    def _load(self, sid):
        path = self._path(sid, 'events.jsonl')
        if not path.exists():
            raise SessionError('not-found', '会话不存在')
        latest = None
        lines = path.read_text(encoding='utf-8').splitlines()
        for index, line in enumerate(lines):
            try:
                ev = json.loads(line)
            except ValueError:
                if index != len(lines) - 1:
                    raise SessionError('corrupt-data', '历史事件损坏，不能跳过') from None
                break  # A partial last append is not a committed state.
            if ev.get('seq') != (latest['seq'] + 1 if latest else 1):
                raise SessionError('corrupt-data', '会话事件序号不连续')
            latest = ev['state_after']
        if latest is None:
            raise SessionError('corrupt-data', '会话没有有效状态')
        if latest['demo'] != self.demo:
            raise SessionError('mode-mismatch', '演示会话与真实会话不能混用')
        return latest

    def _save(self, state, action):
        state['seq'] += 1
        state['updated_at'] = self.wall_clock()
        path = self._path(state['id'], 'events.jsonl')
        # Remove only a torn final append while the session lock is held.
        valid = []
        if path.exists():
            lines = path.read_bytes().splitlines(keepends=True)
            for index, line in enumerate(lines):
                try:
                    json.loads(line)
                except ValueError:
                    if index != len(lines) - 1:
                        raise SessionError('corrupt-data', '历史事件损坏，不能截断') from None
                    break
                valid.append(line.rstrip(b'\r\n') + b'\n')
            if b''.join(valid) != path.read_bytes():
                with path.open('wb') as f:
                    f.write(b''.join(valid)); f.flush(); os.fsync(f.fileno())
        event = dict(seq=state['seq'], timestamp=state['updated_at'], session_id=state['id'],
                     action=action, state_after=state)
        with path.open('a', encoding='utf-8') as f:
            f.write(encoded(event) + '\n'); f.flush(); os.fsync(f.fileno())
        atomic_write(self._path(state['id'], 'session.json'), encoded(state) + '\n')

    def _write_json(self, sid, rel, value):
        atomic_write(self._path(sid, rel), encoded(value) + '\n')

    def _messages(self, state):
        return [read_json(self._path(state['id'], x['path'])) for x in state['messages']]

    def _version(self, state, number=None):
        number = state['version'] if number is None else number
        if type(number) is not int or number < 1 or number > len(state['versions']):
            raise SessionError('invalid-version', '需求版本不存在')
        meta = state['versions'][number - 1]
        draft = read_json(self._path(state['id'], f'versions/{number:04}/requirements.json'))
        if digest(draft) != meta['hash']:
            raise SessionError('corrupt-data', '需求内容已被外部修改，不能使用旧审核或确认')
        return draft

    def _review(self, state):
        if state['review'] is None:
            return None
        return read_json(self._path(state['id'], f"reviews/{state['review']:04}.json"))

    def _check(self, state):
        missing = check_draft(self._version(state), state['checklist']) if state['version'] else ['draft']
        review = self._review(state)
        if review:
            validate_review({k: review[k] for k in ['reply', 'version', 'hash', 'verdict', 'findings']},
                            review['version'], review['hash'])
        approved = bool(review and review['verdict'] == 'PASS' and review['version'] == state['version']
                        and review['hash'] == state['hash'] and review['input_round'] == state['round'])
        return dict(structure_ready=not missing, ready_to_confirm=not missing and approved,
                    missing=missing, version=state['version'], hash=state['hash'])

    def _view(self, state):
        out = copy.deepcopy(state)
        out['messages'] = self._messages(state)
        out['check'] = self._check(state)
        out['draft'] = self._version(state) if state['version'] else None
        out['markdown'] = render(out['draft']) if out['draft'] else ''
        out['latest_review'] = self._review(state)
        calls = []
        for entry in state['calls']:
            p = self._path(state['id'], entry['dir'], 'call.json')
            call = read_json(p)
            raw = self._path(state['id'], entry['dir'], 'raw-output.txt')
            call['raw_output'] = raw.read_text(encoding='utf-8') if raw.exists() else None
            try:
                call['reply'] = json.loads(call['raw_output'])['reply']
            except (ValueError, TypeError, KeyError):
                call['reply'] = ''
            calls.append(call)
        out['calls'] = calls
        out['total_elapsed_ms'] = sum(c['elapsed_ms'] for c in calls if c['elapsed_ms'] is not None)
        out['unknown_elapsed_count'] = sum(c['elapsed_ms'] is None for c in calls)
        return out

    def status(self, sid):
        return self._view(self._load(sid))

    def check(self, sid):
        """Local validation only; never invokes either model."""
        return self._check(self._load(sid))

    def list_sessions(self):
        out = []
        for p in self.base.glob('Q*'):
            try:
                s = self._load(p.name)
                out.append({k: s[k] for k in ['id', 'project_id', 'status', 'version', 'updated_at', 'demo']})
            except SessionError:
                continue
        return sorted(out, key=lambda x: x['updated_at'], reverse=True)

    def create(self, project_id, initial_text, analyst=None, reviewer=None, review_limit=None):
        self._text(initial_text)
        if not isinstance(project_id, str) or not project_id.strip() or len(project_id) > 100:
            raise SessionError('invalid-project', '请输入项目名称，最多 100 个字符')
        settings = copy.deepcopy(self.settings)
        settings['analyst'] = analyst or settings['analyst']
        settings['reviewer'] = reviewer or settings['reviewer']
        settings['review_limit'] = settings['review_limit'] if review_limit is None else review_limit
        if type(settings['review_limit']) is not int or not 1 <= settings['review_limit'] <= 20:
            raise SessionError('invalid-config', '自动审核轮数必须是 1 到 20 的整数')
        try:
            a, b = [settings['agents'][settings[k]] for k in ['analyst', 'reviewer']]
            for role, agent in [('requirements_analyst', a), ('requirements_reviewer', b)]:
                if 'supported_tasks' in agent and role not in agent['supported_tasks']:
                    raise KeyError('capability')
            if not a.get('vendor') or not b.get('vendor') or a['vendor'] == b['vendor']:
                raise KeyError('vendor')
            for agent in [a, b]:
                if agent['cli'] not in {'claude', 'codex'} or not agent.get('model') or agent['model'] in {'opus', 'sonnet', 'haiku'}:
                    raise KeyError('model')
        except KeyError:
            raise SessionError('invalid-config', '梳理与审核须选择已登记、符合角色能力且不同厂商的完整模型') from None
        sid = 'Q' + uuid.uuid4().hex[:12]
        self._path(sid).mkdir(mode=0o700)
        with self._lock(sid):
            self._write_json(sid, 'checklist.json', CHECKLIST)
            message = dict(id='message:1', text=initial_text, client_id='initial', at=self.wall_clock())
            self._write_json(sid, 'messages/0001.json', message)
            state = dict(schema_version=1, id=sid, project_id=project_id, status='ready', phase='clarify',
                         demo=self.demo, settings=settings, checklist=copy.deepcopy(CHECKLIST), round=1,
                         version=0, hash=None, versions=[], messages=[dict(id='message:1', client_id='initial', path='messages/0001.json')],
                         calls=[], active=None, retry_of=None, review=None, reviews=[], review_rounds=0,
                         confirmations=[], waiting_reason=None, error=None, seq=0)
            self._save(state, 'session.created')
            return self._view(state)

    @staticmethod
    def _text(value):
        if not isinstance(value, str) or not value.strip() or len(value.encode()) > 128000:
            raise SessionError('invalid-input', '输入不能为空，且不能超过 128KB')

    def submit(self, sid, text, message_id):
        self._text(text)
        if not isinstance(message_id, str) or not message_id or len(message_id) > 120:
            raise SessionError('invalid-input', '需要有效的消息幂等 ID')
        with self._lock(sid):
            s = self._load(sid)
            for old in self._messages(s):
                if old['client_id'] == message_id:
                    if old['text'] != text:
                        raise SessionError('conflict', '同一消息 ID 对应不同内容')
                    return self._view(s)
            if s['status'] != 'waiting-human':
                raise SessionError('conflict', '当前状态不接受新回答；完成后请先开启修订')
            n = len(s['messages']) + 1
            message = dict(id=f'message:{n}', text=text, client_id=message_id, at=self.wall_clock())
            path = f'messages/{n:04}.json'
            self._write_json(sid, path, message)
            s['messages'].append(dict(id=message['id'], client_id=message_id, path=path))
            s.update(status='ready', phase='clarify', round=s['round'] + 1, review=None,
                     review_rounds=0, waiting_reason=None, error=None, retry_of=None)
            self._save(s, 'message.submitted')
            return self._view(s)

    def _input(self, s, kind, key):
        from .agent import prompt_text
        draft = self._version(s) if s['version'] else None
        role = 'reviewer' if kind == 'review' else 'analyst'
        prompt, prompt_version = prompt_text(kind)
        return dict(schema_version=1, session_id=s['id'], call_id=key, kind=kind, role=role,
                    project_id=s['project_id'], messages=self._messages(s),
                    history=[dict(kind=c['kind'], output=self._path(s['id'], c['dir'], 'raw-output.txt').read_text())
                             for c in s['calls'] if self._path(s['id'], c['dir'], 'raw-output.txt').exists()],
                    draft=draft, version=s['version'], hash=s['hash'], checklist=s['checklist'],
                    check=self._check(s), review=self._review(s), agent=s['settings']['agents'][s['settings'][role]],
                    prompt=prompt, prompt_version=prompt_version)

    def _process(self, s, call, data, raw):
        payload = json.loads(raw)
        sid = s['id']
        if call['kind'] == 'review':
            review = validate_review(payload, s['version'], s['hash'])
            review = dict(review, input_round=s['round'], call_id=data['call_id'],
                          id=len(s['reviews']) + 1)
            self._write_json(sid, f"reviews/{review['id']:04}.json", review)
            s['reviews'].append(review['id'])
            s['review'] = review['id']
            s['review_rounds'] += 1
            if review['verdict'] == 'PASS':
                s.update(status='waiting-human', waiting_reason='confirmation')
            elif review['verdict'] == 'NEEDS_HUMAN':
                s.update(status='waiting-human', waiting_reason='review-decision')
            elif s['review_rounds'] >= s['settings']['review_limit']:
                s.update(status='waiting-human', waiting_reason='review-limit')
            else:
                s.update(status='ready', phase='revise')
        else:
            fields(payload, ['reply', 'draft'], ['responses'])
            require(isinstance(payload['reply'], str), 'reply 必须是文本')
            if call['kind'] == 'revise':
                responses = payload.get('responses', [])
                require(isinstance(responses, list), '需要逐项回应审核意见')
                for x in responses:
                    fields(x, ['id', 'text'])
                    require(isinstance(x['id'], str) and isinstance(x['text'], str) and bool(x['text'].strip()), '审核回应不能为空')
                require({x['id'] for x in responses} == {x['id'] for x in data['review']['findings']}, '审核意见未逐项回应')
            validate_draft(payload['draft'], {x['id'] for x in data['messages']}, s['checklist'])
            h = digest(payload['draft'])
            if h != s['hash']:
                n = len(s['versions']) + 1
                folder = f'versions/{n:04}'
                self._write_json(sid, folder + '/requirements.json', payload['draft'])
                atomic_write(self._path(sid, folder, 'requirements.md'), render(payload['draft']))
                self._write_json(sid, folder + '/check.json', dict(missing=check_draft(payload['draft'], s['checklist'])))
                s['versions'].append(dict(version=n, hash=h, call_id=data['call_id']))
                s.update(version=n, hash=h, review=None)
            missing = check_draft(payload['draft'], s['checklist'])
            if missing:
                s.update(status='waiting-human', waiting_reason='clarification')
            else:
                s.update(status='ready', phase='review')
        s.update(active=None, retry_of=None, error=None)
        self._save(s, 'review.saved' if call['kind'] == 'review' else 'draft.saved')

    def advance(self, sid):
        with self._lock(sid):
            s = self._load(sid)
            if s['status'] in {'waiting-human', 'completed', 'error'}:
                return self._view(s)
            while s['status'] in {'ready', 'working', 'reviewing'}:
                recovery = s['status'] in {'working', 'reviewing'}
                if recovery:
                    call = s['calls'][s['active']]
                    folder = self._path(sid, call['dir'])
                    data = read_json(folder / 'input.json')
                    meta = read_json(folder / 'call.json')
                    if meta['status'] == 'running':
                        meta.update(status='interrupted', finished_at=None, elapsed_ms=None)
                    self._write_json(sid, call['dir'] + '/call.json', meta)
                    if not (folder / 'raw-output.txt').exists() and not getattr(self.invoke, 'can_resume', False):
                        s.update(status='error', error=dict(code='interrupted', message='上次调用中断，不能确定结果，请显式重试'))
                        self._save(s, 'call.interrupted')
                        return self._view(s)
                else:
                    previous = s['retry_of']
                    number = previous['number'] if previous else max([c['number'] for c in s['calls']], default=0) + 1
                    attempt = previous['attempt'] + 1 if previous else 1
                    key = f'{sid}-r{s["round"]}-c{number}-a{attempt}'
                    rel = f'rounds/{s["round"]:04}/calls/{number:04}/attempt-{attempt}'
                    folder = self._path(sid, rel)
                    folder.mkdir(parents=True, exist_ok=True)
                    data = self._input(s, s['phase'], key)
                    self._write_json(sid, rel + '/input.json', data)
                    call = dict(number=number, attempt=attempt, dir=rel, kind=s['phase'], round=s['round'])
                    meta = dict(call, call_id=key, agent=data['agent'], prompt_version=data['prompt_version'],
                                status='running', started_at=self.wall_clock(), finished_at=None, elapsed_ms=None, error=None)
                    self._write_json(sid, rel + '/call.json', meta)
                    s['calls'].append(call)
                    s.update(active=len(s['calls']) - 1, status='reviewing' if call['kind'] == 'review' else 'working')
                    self._save(s, 'call.started')
                raw_path = self._path(sid, call['dir'], 'raw-output.txt')
                start = self.monotonic()
                try:
                    if raw_path.exists():
                        raw = raw_path.read_text(encoding='utf-8')
                    else:
                        if self.invoke is None:
                            raise SessionError('not-configured', '未配置模型调用器')
                        raw = self.invoke(data, folder, s['settings']['timeout_s'])
                    elapsed = max(0, round((self.monotonic() - start) * 1000))
                    if not isinstance(raw, str) or len(raw.encode()) > 2000000:
                        raise SessionError('invalid-output', '模型回复为空或过大')
                    if not recovery:
                        meta.update(status='succeeded', finished_at=self.wall_clock(), elapsed_ms=elapsed)
                    atomic_write(raw_path, raw)
                    self._write_json(sid, call['dir'] + '/call.json', meta)
                except Exception as e:
                    code = 'timed-out' if isinstance(e, TimeoutError) else getattr(e, 'code', 'call-failed')
                    if not recovery:
                        meta.update(status=code if code == 'timed-out' else 'failed', finished_at=self.wall_clock(),
                                    elapsed_ms=max(0, round((self.monotonic() - start) * 1000)), error=code)
                    self._write_json(sid, call['dir'] + '/call.json', meta)
                    s.update(status='error', error=dict(code=code, message='调用未完成，请检查模型配置或中台，再显式重试'))
                    self._save(s, 'call.failed')
                    return self._view(s)
                try:
                    self._process(s, call, data, raw)
                except (ValueError, TypeError, KeyError) as e:
                    s.update(status='error', error=dict(code='invalid-output', message='回复不符合协议：' + str(e)[:180]))
                    self._save(s, 'output.invalid')
                    return self._view(s)
            return self._view(s)

    def retry(self, sid):
        with self._lock(sid):
            s = self._load(sid)
            if s['status'] != 'error' or s['active'] is None:
                raise SessionError('conflict', '只有调用错误可以显式重试')
            old = s['calls'][s['active']]
            if s['error']['code'] != 'invalid-output' and self._path(sid, old['dir'], 'raw-output.txt').is_file():
                s.update(status='reviewing' if old['kind'] == 'review' else 'working', error=None)
                self._save(s, 'call.recover-requested')
                return self._view(s)
            s.update(status='ready', phase=old['kind'], retry_of=old, error=None, active=None)
            self._save(s, 'call.retry-requested')
            return self._view(s)

    def confirm(self, sid, version, content_hash):
        with self._lock(sid):
            s = self._load(sid)
            if type(version) is not int or version != s['version'] or content_hash != s['hash']:
                raise SessionError('stale-version', '文档版本已经变化，请重新阅读并确认当前版本')
            if s['status'] == 'completed':
                return self._view(s)
            if s['status'] != 'waiting-human' or not self._check(s)['ready_to_confirm']:
                raise SessionError('not-ready', '当前版本须结构完整且经过另一模型审核通过，才能确认')
            c = dict(version=version, hash=content_hash, confirmed_at=self.wall_clock(), review_id=s['review'])
            n = len(s['confirmations']) + 1
            self._write_json(sid, f'confirmations/{n:04}.json', c)
            s['confirmations'].append(c)
            s.update(status='completed', waiting_reason=None)
            self._save(s, 'version.confirmed')
            return self._view(s)

    def export(self, sid, version):
        s = self._load(sid)
        draft = self._version(s, version)
        confirmation = next((c for c in s['confirmations'] if c['version'] == version), None)
        if not confirmation:
            raise SessionError('not-confirmed', '只能导出已确认版本')
        if confirmation['hash'] != digest(draft):
            raise SessionError('corrupt-data', '确认哈希与需求不匹配')
        review = read_json(self._path(sid, f"reviews/{confirmation['review_id']:04}.json"))
        validate_review({k: review[k] for k in ['reply', 'version', 'hash', 'verdict', 'findings']},
                        version, digest(draft))
        if review['verdict'] != 'PASS':
            raise SessionError('corrupt-data', '已确认版本的审核记录无效')
        return dict(session_id=sid, project_id=s['project_id'], version=version, hash=digest(draft),
                    draft=draft, markdown=render(draft), confirmation=confirmation, review=review, demo=s['demo'])

    def reopen(self, sid):
        with self._lock(sid):
            s = self._load(sid)
            if s['status'] != 'completed':
                raise SessionError('conflict', '只有已完成会话可以开启新修订')
            s.update(status='waiting-human', waiting_reason='revision', review=None)
            self._save(s, 'session.reopened')
            return self._view(s)
