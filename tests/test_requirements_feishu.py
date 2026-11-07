import json
import tempfile
import unittest
from pathlib import Path

from channels.feishu import FeishuRequirements, parse_command
from channels.gateway import ChannelError, MessageGateway
from requirements.agent import DemoAgent
from requirements.messaging import RequirementsMessages, issue_pairing
from requirements.session import SessionError, SessionStore

TEXT='目标：活动报名\n用户：居民\n功能：报名查询\n范围：不做支付\n约束：匿名本机\n验收：可查询报名'


class FeishuTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=SessionStore(self.tmp.name,invoke=DemoAgent(),demo=True)
        self.gateway=MessageGateway(self.tmp.name,{'requirements':RequirementsMessages(self.store)},{('feishu','owner')})
        self.client=FeishuRequirements(self.gateway)

    def send(self,mid,text,chat='chat'):
        return self.client.handle('owner',chat,mid,text)

    def test_commands_are_explicit_and_confirmation_requires_exact_hash(self):
        self.assertEqual(parse_command('/req 列表'),{'action':'list'})
        self.assertEqual(parse_command('/需求 回复 Q111111111111 | 包含 | 符号')['text'],'包含 | 符号')
        for value in ['/需求 确认 Q111111111111','/需求 确认 Q111111111111 1 stale','/需求 删除 全部']:
            with self.assertRaises(SessionError):parse_command(value)

    def test_create_reply_review_confirm_export_full_mobile_flow(self):
        out=self.send('m1','/需求 新建 匿名活动 | 想做网站')
        sid=self.store.list_sessions()[0]['id']
        self.assertEqual(self.store.status(sid)['status'],'waiting-human')
        self.assertIn('模拟',out['text'])
        self.send('m2',f'/需求 回复 {sid} | '+TEXT)
        s=self.store.status(sid)
        self.assertTrue(s['check']['ready_to_confirm'])
        self.send('m3',f'/需求 确认 {sid} {s["version"]} {s["hash"]}')
        out=self.send('m4',f'/需求 导出 {sid} {s["version"]}')
        self.assertIn('报名查询',out['file']['text'])
        self.assertTrue(out['file']['filename'].endswith('.md'))

    def test_message_redelivery_does_not_create_or_call_twice(self):
        a=self.send('same','/需求 新建 匿名 | 想法')
        b=self.send('same','/需求 新建 匿名 | 想法')
        self.assertEqual(a,b)
        self.assertEqual(len(self.store.list_sessions()),1)
        self.assertEqual(len(self.store.status(self.store.list_sessions()[0]['id'])['calls']),1)

    def test_whitelist_applies_even_to_help_and_cross_chat_access_denied(self):
        with self.assertRaises(ChannelError):self.client.handle('intruder','chat','m','/需求')
        self.send('1','/需求 新建 匿名 | 想法')
        sid=self.store.list_sessions()[0]['id']
        with self.assertRaises(SessionError):self.send('2',f'/需求 查看 {sid}',chat='other')

    def test_existing_cli_session_pairing_is_one_time_and_expires(self):
        s=self.store.create('CLI项目','想法')
        pair=issue_pairing(self.store,s['id'],clock=lambda:100)
        app=RequirementsMessages(self.store,clock=lambda:101)
        gateway=MessageGateway(self.tmp.name,{'requirements':app},{('feishu','owner')})
        client=FeishuRequirements(gateway)
        out=client.handle('owner','chat','bind-1','/需求 绑定 '+pair['code'])
        self.assertIn(s['id'],out['text'])
        with self.assertRaises(SessionError):client.handle('owner','other','bind-2','/需求 绑定 '+pair['code'])
        pair=issue_pairing(self.store,s['id'],clock=lambda:100)
        expired=RequirementsMessages(self.store,clock=lambda:1000)
        with self.assertRaises(SessionError):expired(dict(channel='feishu',actor='owner',conversation='other',event_id='x'),dict(action='bind',code=pair['code']))

    def test_long_view_returns_readable_document_file_and_no_model_raw_logs(self):
        self.send('1','/需求 新建 匿名 | '+TEXT)
        sid=self.store.list_sessions()[0]['id']
        out=self.send('2',f'/需求 查看 {sid}')
        self.assertIn('需求说明书',out['file']['text'])
        self.assertNotIn('raw_output',out['text'])

    def test_subprocess_entry_uses_stdin_and_no_sdk_dependency(self):
        import subprocess,sys
        worker=Path(__file__).resolve().parents[1]/'src/requirements/feishu.py'
        envelope=dict(actor='owner',chat_id='chat',message_id='process-1',text='/需求 列表',allowed_users=['owner'])
        p=subprocess.run([sys.executable,str(worker),'--root',self.tmp.name,'--demo'],input=json.dumps(envelope),text=True,capture_output=True,timeout=5)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('text',json.loads(p.stdout))
