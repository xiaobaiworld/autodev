import copy
import json
import tempfile
import unittest
from pathlib import Path

from requirements.session import SessionError, SessionStore

DRAFT = json.loads((Path(__file__).parent / 'fixtures/requirements/complete.json').read_text())
SETTINGS = {'agents': {'writer': {'cli': 'claude', 'vendor': 'anthropic', 'model': 'test/writer', 'effort': 'low'},
                       'reader': {'cli': 'codex', 'vendor': 'openai', 'model': 'test/reader', 'effort': 'low'}},
            'analyst': 'writer', 'reviewer': 'reader', 'review_limit': 3, 'timeout_s': 10}


class FakeAgent:
    def __init__(self, reviews=None):
        self.calls = []
        self.reviews = list(reviews or ['PASS'])
        self.bad = False

    def __call__(self, data, folder, timeout):
        self.calls.append(copy.deepcopy(data))
        if self.bad:
            return 'not JSON'
        if data['kind'] == 'review':
            verdict = self.reviews.pop(0) if self.reviews else 'REWORK'
            findings = [] if verdict == 'PASS' else [dict(id='F1', location='functions', evidence='原始需求',
                        problem='需说明', expected='补上说明', blocking=True)]
            return json.dumps(dict(reply='审核意见', version=data['version'], hash=data['hash'],
                                   verdict=verdict, findings=findings))
        draft = copy.deepcopy(DRAFT)
        if data['kind'] == 'revise':
            draft['sections']['goal'] += '（修订）'
        return json.dumps(dict(reply='请检查需求', draft=draft,
                               **({'responses': [{'id': 'F1', 'text': '已补上说明'}]} if data['kind'] == 'revise' else {})))


class SessionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fake = FakeAgent()
        self.store = SessionStore(self.tmp.name, invoke=self.fake, settings=SETTINGS)
        self.created = self.store.create('anonymous', '活动报名网站')
        self.sid = self.created['id']

    def test_two_models_then_explicit_current_version_confirmation(self):
        s = self.store.advance(self.sid)
        self.assertEqual([c['kind'] for c in self.fake.calls], ['clarify', 'review'])
        self.assertEqual(s['status'], 'waiting-human')
        self.assertTrue(s['check']['ready_to_confirm'])
        self.assertEqual(self.store.confirm(self.sid, s['version'], s['hash'])['status'], 'completed')
        exported = self.store.export(self.sid, s['version'])
        self.assertEqual(exported['confirmation']['hash'], s['hash'])
        self.assertIn('居民填写昵称报名', exported['markdown'])
        self.store.confirm(self.sid, s['version'], s['hash'])
        self.store.status(self.sid)
        self.assertTrue(self.store.check(self.sid)['ready_to_confirm'])
        self.assertEqual(len(self.fake.calls), 2)

    def test_cannot_confirm_before_review_or_export_unconfirmed(self):
        with self.assertRaises(SessionError):
            self.store.confirm(self.sid, 0, 'x')
        with self.assertRaises(SessionError):
            self.store.export(self.sid, 1)

    def test_rework_response_and_review_use_new_hash(self):
        self.fake.reviews = ['REWORK', 'PASS']
        s = self.store.advance(self.sid)
        self.assertEqual([c['kind'] for c in self.fake.calls], ['clarify', 'review', 'revise', 'review'])
        self.assertEqual(s['version'], 2)
        self.assertTrue(s['check']['ready_to_confirm'])
        self.assertNotEqual(self.fake.calls[1]['hash'], self.fake.calls[3]['hash'])

    def test_review_limit_pauses_and_does_not_call_again_while_waiting(self):
        self.fake.reviews = ['REWORK'] * 6
        s = self.store.advance(self.sid)
        self.assertEqual(s['status'], 'waiting-human')
        self.assertEqual(s['waiting_reason'], 'review-limit')
        self.assertFalse(s['check']['ready_to_confirm'])
        n = len(self.fake.calls)
        self.store.advance(self.sid)
        self.assertEqual(len(self.fake.calls), n)

    def test_business_decision_goes_to_human(self):
        self.fake.reviews = ['NEEDS_HUMAN']
        s = self.store.advance(self.sid)
        self.assertEqual(s['waiting_reason'], 'review-decision')
        self.assertEqual(len(self.fake.calls), 2)

    def test_reopen_keeps_old_export_but_new_input_invalidates_review(self):
        s = self.store.advance(self.sid)
        self.store.confirm(self.sid, s['version'], s['hash'])
        self.store.reopen(self.sid)
        new = self.store.submit(self.sid, '改为学校活动', 'client-1')
        self.assertFalse(new['check']['ready_to_confirm'])
        with self.assertRaises(SessionError):
            self.store.confirm(self.sid, s['version'], s['hash'])
        self.assertEqual(self.store.export(self.sid, s['version'])['hash'], s['hash'])

    def test_repeated_message_id_is_idempotent_and_different_text_conflicts(self):
        self.store.advance(self.sid)
        a = self.store.submit(self.sid, '补充', 'client-1')
        b = self.store.submit(self.sid, '补充', 'client-1')
        self.assertEqual(a['messages'], b['messages'])
        with self.assertRaises(SessionError):
            self.store.submit(self.sid, '不同内容', 'client-1')

    def test_invalid_output_keeps_raw_text_and_retry_is_explicit(self):
        self.fake.bad = True
        s = self.store.advance(self.sid)
        self.assertEqual(s['status'], 'error')
        self.assertEqual(s['error']['code'], 'invalid-output')
        self.assertEqual(s['calls'][0]['status'], 'succeeded')
        self.assertEqual(s['calls'][0]['raw_output'], 'not JSON')
        self.fake.bad = False
        self.store.retry(self.sid)
        s = self.store.advance(self.sid)
        self.assertEqual(s['calls'][1]['attempt'], 2)
        self.assertTrue(s['check']['ready_to_confirm'])

    def test_configuration_validation_and_snapshot(self):
        with self.assertRaises(SessionError):
            self.store.create('p', 'x', analyst='writer', reviewer='writer')
        for limit in [True, 0, -1]:
            with self.assertRaises(SessionError):
                self.store.create('p', 'x', review_limit=limit)
        self.store.settings['agents']['writer']['effort'] = 'high'
        self.assertEqual(self.store.status(self.sid)['settings']['agents']['writer']['effort'], 'low')

    def test_path_and_tampered_version_are_rejected(self):
        with self.assertRaises(SessionError):
            self.store.status('../escape')
        s = self.store.advance(self.sid)
        p = self.store.base / self.sid / 'versions/0001/requirements.json'
        p.write_text(json.dumps(dict(DRAFT, sections=dict(DRAFT['sections'], goal='tampered'))))
        with self.assertRaises(SessionError):
            self.store.confirm(self.sid, s['version'], s['hash'])

    def test_injected_monotonic_clock_not_wall_clock_controls_elapsed(self):
        ticks = iter([10.0, 10.125, 20.0, 20.25])
        self.store.monotonic = lambda: next(ticks)
        self.store.wall_clock = lambda: '2026-11-07T00:00:00+08:00'
        s = self.store.advance(self.sid)
        self.assertEqual([c['elapsed_ms'] for c in s['calls']], [125, 250])
        self.store.status(self.sid)
        self.assertEqual(len(self.fake.calls), 2)

    def test_timeout_recorded_and_restart_does_not_lose_version(self):
        def timeout(*args):
            raise TimeoutError('timeout')
        self.store.invoke = timeout
        s = self.store.advance(self.sid)
        self.assertEqual(s['calls'][0]['status'], 'timed-out')
        other = SessionStore(self.tmp.name, invoke=self.fake, settings=SETTINGS)
        self.assertEqual(other.status(self.sid)['status'], 'error')
        other.retry(self.sid)
        self.assertTrue(other.advance(self.sid)['check']['ready_to_confirm'])

    def test_torn_last_event_recovers_but_corrupt_history_is_rejected(self):
        path = self.store.base / self.sid / 'events.jsonl'
        with path.open('a') as f:
            f.write('{"seq":')
        self.assertEqual(self.store.status(self.sid)['status'], 'ready')
        self.assertTrue(self.store.advance(self.sid)['check']['ready_to_confirm'])
        lines = path.read_text().splitlines()
        lines[1] = 'broken history'
        path.write_text('\n'.join(lines) + '\n')
        with self.assertRaises(SessionError):
            self.store.status(self.sid)

    def test_interrupted_call_with_saved_output_resumes_without_new_model_call(self):
        from unittest.mock import patch
        with patch.object(self.store, '_process', side_effect=OSError('simulated disk failure')):
            with self.assertRaises(OSError):
                self.store.advance(self.sid)
        self.assertEqual(len(self.fake.calls), 1)
        other = SessionStore(self.tmp.name, invoke=self.fake, settings=SETTINGS)
        result = other.advance(self.sid)
        self.assertEqual(len(self.fake.calls), 2)  # Only the reviewer is newly invoked.
        self.assertTrue(result['check']['ready_to_confirm'])
        self.assertEqual(result['calls'][0]['status'], 'succeeded')

    def test_interrupted_call_without_result_waits_for_explicit_retry(self):
        def crash(*args):
            raise KeyboardInterrupt()
        self.store.invoke = crash
        with self.assertRaises(KeyboardInterrupt):
            self.store.advance(self.sid)
        other = SessionStore(self.tmp.name, invoke=self.fake, settings=SETTINGS)
        s = other.advance(self.sid)
        self.assertEqual(s['error']['code'], 'interrupted')
        self.assertEqual(s['calls'][0]['status'], 'interrupted')
        self.assertIsNone(s['calls'][0]['elapsed_ms'])
        self.assertEqual(len(self.fake.calls), 0)

    def test_model_cannot_create_confirmation_by_returning_an_extra_field(self):
        self.store.invoke = lambda *args: json.dumps(dict(reply='已确认', draft=DRAFT, confirmed=True))
        s = self.store.advance(self.sid)
        self.assertEqual(s['status'], 'error')
        self.assertEqual(s['confirmations'], [])

    def test_busy_session_rejects_second_writer_without_overwriting(self):
        from cockpit.store import acquire_lock
        lock=acquire_lock(self.store.base/self.sid/'.lock')
        try:
            with self.assertRaises(SessionError) as error:
                self.store.advance(self.sid)
            self.assertEqual(error.exception.code,'busy')
            self.assertEqual(self.store.status(self.sid)['status'],'ready')
        finally:
            lock.close()

    def test_symlink_version_is_rejected(self):
        self.store.advance(self.sid)
        path=self.store.base/self.sid/'versions/0001/requirements.json'
        target=Path(self.tmp.name)/'outside.json'
        target.write_text(path.read_text());path.unlink();path.symlink_to(target)
        with self.assertRaises(SessionError):
            self.store.status(self.sid)
