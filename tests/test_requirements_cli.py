import contextlib
import io
import json
import tempfile
import unittest

from requirements.__main__ import main

EXAMPLE = '目标：活动报名\n用户：居民\n功能：报名和查询\n范围：不做支付\n约束：仅本机\n验收：报名后可查询'


class CliTest(unittest.TestCase):
    def test_cli_and_python_share_confirmed_session(self):
        from requirements.session import SessionStore
        from requirements.agent import DemoAgent
        with tempfile.TemporaryDirectory() as root:
            def run(*args):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    code = main(['--root', root, '--demo', '--json', *args])
                self.assertEqual(code, 0, out.getvalue())
                return json.loads(out.getvalue())
            s = run('create', '--project', 'anonymous', '--text', '想做报名网站')
            run('step', s['id'])
            run('reply', s['id'], '--text', EXAMPLE, '--message-id', 'answer-1')
            s = run('step', s['id'])
            api = SessionStore(root, invoke=DemoAgent(), demo=True)
            self.assertEqual(api.status(s['id'])['hash'], s['hash'])
            run('confirm', s['id'], '--version', str(s['version']), '--hash', s['hash'])
            exported = run('export', s['id'], '--version', str(s['version']))
            self.assertIn('报名和查询', exported['markdown'])
