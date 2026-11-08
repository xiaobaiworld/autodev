import tempfile
import unittest
from channels.gateway import ChannelError, MessageGateway
from requirements.agent import DemoAgent
from requirements.messaging import RequirementsMessages
from requirements.session import SessionError, SessionStore


class MessagingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SessionStore(self.tmp.name, invoke=DemoAgent(), demo=True)
        self.app = RequirementsMessages(self.store)
        self.gateway = MessageGateway(self.tmp.name, {'requirements': self.app}, {('feishu','owner')})

    def send(self, event_id, action, **data):
        return self.gateway.receive('feishu','owner','chat-1',event_id,'requirements',dict(action=action,**data))

    def test_channel_identity_dedup_and_shared_backend(self):
        first = self.send('1','create',project_id='匿名',text='活动报名')
        self.assertEqual(first, self.send('1','create',project_id='匿名',text='活动报名'))
        sid = first['session']['id']
        self.assertEqual(len(self.store.list_sessions()),1)
        self.send('2','step',session_id=sid)
        self.assertEqual(self.store.status(sid)['status'],'waiting-human')
        with self.assertRaises(ChannelError):
            self.send('1','create',project_id='不同',text='不同')

    def test_unauthorized_and_unbound_session_access_rejected(self):
        with self.assertRaises(ChannelError):
            self.gateway.receive('feishu','intruder','chat-1','1','requirements',{'action':'list'})
        s=self.store.create('private','private idea')
        with self.assertRaises(SessionError):
            self.send('1','show',session_id=s['id'])

    def test_confirm_requires_explicit_action_version_hash_and_user(self):
        first=self.send('1','create',project_id='匿名',text='目标：报名\n用户：居民\n功能：报名查询\n范围：不做支付\n约束：匿名\n验收：可查询')
        sid=first['session']['id']
        self.send('2','step',session_id=sid)
        s=self.store.status(sid)
        with self.assertRaises(SessionError):
            self.send('3','confirm',session_id=sid,version=1,hash='stale')
        self.send('4','confirm',session_id=sid,version=s['version'],hash=s['hash'])
        self.assertEqual(self.store.status(sid)['status'],'completed')
