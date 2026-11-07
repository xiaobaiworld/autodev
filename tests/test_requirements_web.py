import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

from requirements.agent import DemoAgent
from requirements.session import SessionStore
from requirements.web import make_server

EXAMPLE = '目标：活动报名\n用户：居民\n功能：报名查询\n范围：不做支付\n约束：匿名本机\n验收：报名后能查询'


class WebTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SessionStore(self.tmp.name, invoke=DemoAgent(), demo=True)
        self.server = make_server(self.store, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.token = self.request('/api/config')['csrf_token']

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.tmp.cleanup()

    def request(self, path, body=None, headers=None):
        h = {'Content-Type': 'application/json'}
        if body is not None:
            h.update({'X-CSRF-Token': getattr(self, 'token', ''), 'Origin': self.url})
        h.update(headers or {})
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode() if body is not None else None, headers=h)
        try:
            response = urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as e:
            e.close()
            raise
        with response as r:
            data = r.read()
            return json.loads(data) if r.headers['Content-Type'].startswith('application/json') else data.decode()

    def wait(self, sid):
        for _ in range(100):
            s = self.request('/api/sessions/' + sid)
            if s['status'] in {'waiting-human', 'error'}:
                return s
            time.sleep(.01)
        self.fail('background step did not finish')

    def test_browser_api_complete_and_cli_backend_continuation(self):
        s = self.request('/api/sessions', dict(project_id='anonymous', text='做个报名网站'))
        sid = s['id']
        self.request(f'/api/sessions/{sid}/step', {})
        self.wait(sid)
        self.store.submit(sid, EXAMPLE, 'from-cli')
        self.request(f'/api/sessions/{sid}/step', {})
        s = self.wait(sid)
        self.assertTrue(s['check']['ready_to_confirm'])
        self.request(f'/api/sessions/{sid}/confirm', dict(version=s['version'], hash=s['hash']))
        self.assertEqual(self.store.status(sid)['status'], 'completed')
        exported = self.request(f'/api/sessions/{sid}/export?version={s["version"]}')
        self.assertIn('报名查询', exported)

    def test_csrf_host_origin_and_invalid_paths(self):
        for headers in [{'X-CSRF-Token': 'wrong'}, {'Origin': 'https://evil.invalid'},
                        {'Host': 'evil.invalid'}, {'Sec-Fetch-Site': 'cross-site'}]:
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.request('/api/sessions', dict(project_id='x', text='y'), headers)
            self.assertEqual(error.exception.code, 403)
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/api/sessions/%2e%2e')
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/../../config.yaml')

    def test_static_page_is_real_interactive_app_and_model_text_not_html(self):
        html = self.request('/')
        js = self.request('/app.js')
        self.assertIn('需求工作台', html)
        self.assertIn('/confirm', js)
        self.assertIn('textContent', js)
        self.assertNotIn('innerHTML', js)
        self.assertEqual(self.request('/api/config')['demo'], True)
