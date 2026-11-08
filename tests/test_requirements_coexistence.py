"""Main chat sessions and versioned workbench sessions keep their contracts."""
import json
import tempfile
import unittest
from pathlib import Path

from requirements.session import ReqSessionStore
from requirements.versioned_session import SessionStore
from requirements.agent import DemoAgent


class CoexistenceTests(unittest.TestCase):
    def test_public_imports(self):
        from requirements import ReqConfig, SessionError, SessionStore as public_store
        from requirements.session import SessionError as legacy_error, SessionStore as legacy_store
        from requirements.versioned_session import SessionError as versioned_error
        self.assertIs(public_store, SessionStore)
        self.assertIs(legacy_store, SessionStore)
        self.assertIs(SessionError, versioned_error)
        self.assertIs(legacy_error, versioned_error)
        self.assertTrue(ReqConfig)

    def test_stores_survive_restart_without_overwriting_each_other(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chat_file = root / '.req_session.json'
            chat = ReqSessionStore(str(chat_file), tmp, 'claude-sonnet')
            chat.set_agent('anonymous-chat', 'codex')
            before = chat_file.read_bytes()
            workbench = SessionStore(root, invoke=DemoAgent(), demo=True)
            created = workbench.create('anonymous-project', 'anonymous request')
            self.assertEqual(chat_file.read_bytes(), before)
            version_file = root / 'workspace' / 'requirements' / created['id'] / 'session.json'
            version_before = version_file.read_bytes()
            chat.append_history('anonymous-chat', 'anonymous input', 'anonymous output')
            self.assertEqual(version_file.read_bytes(), version_before)
            restored = SessionStore(root, invoke=DemoAgent(), demo=True)
            self.assertEqual(restored.status(created['id'])['id'], created['id'])
            self.assertEqual(ReqSessionStore(str(chat_file), tmp, 'claude-sonnet').get('anonymous-chat')['agent'], 'codex')
            self.assertNotIn(created['id'], json.loads(chat_file.read_text()))
