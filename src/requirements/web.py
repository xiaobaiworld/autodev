"""Loopback HTTP adapter. Business rules stay in SessionStore."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import threading
from urllib.parse import parse_qs, unquote, urlsplit

from .versioned_session import SessionError

STATIC = Path(__file__).with_name('static')
FILES = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
         '/style.css': ('style.css', 'text/css; charset=utf-8')}


class WorkbenchServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, store, host, port):
        if host not in {'127.0.0.1', 'localhost'}:
            raise ValueError('网页仅允许监听 127.0.0.1 或 localhost')
        self.store = store
        self.csrf = secrets.token_urlsafe(32)
        self.tasks = set()
        self.tasks_lock = threading.Lock()
        super().__init__((host, port), Handler)

    def start_step(self, sid):
        self.store.status(sid)
        with self.tasks_lock:
            if sid in self.tasks:
                raise SessionError('busy', '正在处理中，请稍后查看')
            self.tasks.add(sid)
        def work():
            try:
                self.store.advance(sid)
            except (SessionError, OSError):
                pass  # The call/session record remains the recovery source.
            finally:
                with self.tasks_lock:
                    self.tasks.discard(sid)
        threading.Thread(target=work, daemon=True).start()
        return dict(accepted=True, id=sid)


def make_server(store, host='127.0.0.1', port=8765):
    return WorkbenchServer(store, host, port)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Do not put raw user content or request data in terminal logs.

    def _reply(self, value, status=200, content_type='application/json; charset=utf-8', filename=None):
        body = value if isinstance(value, bytes) else (
            value.encode() if isinstance(value, str) else json.dumps(value, ensure_ascii=False).encode())
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if filename:
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def _guard(self, write=False):
        allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
        host = self.headers.get('Host', '')
        if host not in allowed or self.headers.get('Sec-Fetch-Site') == 'cross-site':
            raise SessionError('forbidden', '仅允许从本机工作台访问')
        origin = self.headers.get('Origin')
        if origin is not None and origin != 'http://' + host:
            raise SessionError('forbidden', '拒绝跨站请求')
        if write and not secrets.compare_digest(self.headers.get('X-CSRF-Token', ''), self.server.csrf):
            raise SessionError('forbidden', '页面令牌已失效，请刷新后重试')

    def do_GET(self):
        self._handle(False)

    def do_POST(self):
        self._handle(True)

    def _handle(self, write):
        try:
            self._guard(write)
            url = urlsplit(self.path)
            path = unquote(url.path)
            if not write and path in FILES:
                name, mime = FILES[path]
                return self._reply((STATIC / name).read_bytes(), content_type=mime)
            store = self.server.store
            if not write and path == '/api/config':
                return self._reply(dict(csrf_token=self.server.csrf, demo=store.demo, settings=store.settings,
                                        model_connected=store.invoke is not None))
            if not write and path == '/api/sessions':
                return self._reply(store.list_sessions())
            body = None
            if write:
                if self.headers.get_content_type() != 'application/json':
                    raise SessionError('invalid-input', '请求必须为 JSON')
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 256000:
                    raise SessionError('invalid-input', '请求为空或过大')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise SessionError('invalid-input', '请求必须为 JSON 对象')
            if write and path == '/api/sessions':
                return self._reply(store.create(body.get('project_id'), body.get('text'),
                                               analyst=body.get('analyst'), reviewer=body.get('reviewer'),
                                               review_limit=body.get('review_limit')), status=201)
            parts = path.strip('/').split('/')
            if len(parts) not in {3, 4} or parts[:2] != ['api', 'sessions']:
                raise SessionError('not-found', '页面或接口不存在')
            sid = parts[2]
            if not write and len(parts) == 3:
                return self._reply(store.status(sid))
            if len(parts) != 4:
                raise SessionError('not-found', '接口不存在')
            action = parts[3]
            if not write and action == 'export':
                version = int(parse_qs(url.query).get('version', ['0'])[0])
                result = store.export(sid, version)
                return self._reply(result['markdown'], content_type='text/markdown; charset=utf-8',
                                   filename=f'{sid}-v{version}.md')
            if not write:
                raise SessionError('not-found', '接口不存在')
            if action == 'step':
                return self._reply(self.server.start_step(sid), status=202)
            if action == 'reply':
                result = store.submit(sid, body.get('text'), body.get('message_id'))
            elif action == 'confirm':
                result = store.confirm(sid, body.get('version'), body.get('hash'))
            elif action == 'pair':
                from .messaging import issue_pairing
                result = issue_pairing(store, sid)
            elif action in {'retry', 'reopen'}:
                result = getattr(store, action)(sid)
            else:
                raise SessionError('not-found', '接口不存在')
            self._reply(result)
        except (SessionError, ValueError, TypeError, OSError) as e:
            code = getattr(e, 'code', 'invalid-input')
            status = {'forbidden': 403, 'not-found': 404, 'busy': 409, 'conflict': 409, 'stale-version': 409}.get(code, 400)
            message = str(e) if isinstance(e, SessionError) else '请求格式错误或本地记录无法读取'
            self._reply(dict(error=dict(code=code, message=message)), status=status)
        except Exception:
            self._reply(dict(error=dict(code='internal-error', message='处理失败，请查看会话记录并重试')), status=500)
