import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from requirements.agent import AgentError, HubAgent, load_settings
from requirements.worker import command, final_text, run_model


class FakeHub:
    def __init__(self, root, home, failed=False):
        self.root, self.home, self.failed = Path(root), Path(home), failed
        self.emitted = []
        self.cancelled = []

    def state(self):
        rules = json.loads((self.home / 'rules.json').read_text())
        return {'lines': [{'id': r['name'], 'types': r.get('when', {}).get('types', [])} for r in rules['rules']]}

    def emit(self, key, etype, subject, summary):
        self.emitted.append(key)
        (self.root / 'workspace' / subject / 'raw-output.txt').write_text('{"reply":"匿名测试"}')

    def facts(self, after=0, timeout=1):
        key = self.emitted[-1]
        yield {'seq': 1, 'changes': [
            {'table': 'events', 'row': {'id': 1, 'key': key}},
            {'table': 'run_events', 'row': {'event_id': 1, 'run_id': 1}},
            {'table': 'runs', 'row': {'id': 1, 'state': 'queued' if self.failed else 'done', 'attempts': 1 if self.failed else 0}}]}

    def cancel(self, rid):
        self.cancelled.append(rid)


class AgentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.original = {'sources': {'local': {'name': 'local'}}, 'agents': {'old': {'name': 'existing', 'worker': 'mac1', 'use': 'command', 'command': ['true']}},
                         'rules': [{'name': 'existing-rule', 'when': {'source': 'local', 'types': ['stage.s1']}, 'to': 'old', 'cwd': '/tmp'}]}
        (self.home / 'rules.json').write_text(json.dumps(self.original))
        self.folder = self.root / 'workspace/requirements/Q111111111111/rounds/0001/calls/0001/attempt-1'
        self.folder.mkdir(parents=True)
        self.data = dict(session_id='Q111111111111', kind='clarify', role='analyst', call_id='call-1', agent={'cli': 'claude', 'model': 'test/model'})

    def test_rules_preserve_existing_pipeline_and_install_idempotently(self):
        hub = FakeHub(self.root, self.home)
        agent = HubAgent(self.root, self.home, hub=hub)
        kind = agent.install(self.data)
        agent.install(self.data)
        current = json.loads((self.home / 'rules.json').read_text())
        self.assertEqual(current['agents']['old'], self.original['agents']['old'])
        self.assertIn(self.original['rules'][0], current['rules'])
        self.assertEqual(len(current['rules']), 2)
        self.assertTrue(kind.startswith('requirements.'))
        self.assertEqual(current['rules'][1]['tell'], 'never')

    def test_fact_stream_result_and_failed_call_cancellation(self):
        hub = FakeHub(self.root, self.home)
        agent = HubAgent(self.root, self.home, hub=hub)
        self.assertEqual(json.loads(agent(self.data, self.folder, 1))['reply'], '匿名测试')
        hub.failed = True
        with self.assertRaises(AgentError):
            agent(self.data, self.folder, 1)
        self.assertEqual(hub.cancelled, [1])
        self.assertTrue((self.folder / 'cancelled').exists())

    def test_tool_permissions_are_explicit_and_model_response_only(self):
        a = dict(cli='claude', model='test/model', effort='low')
        argv = command(a)
        self.assertEqual(argv[argv.index('--tools') + 1], '')
        self.assertIn('--safe-mode', argv)
        self.assertIn('--strict-mcp-config', argv)
        a['cli'] = 'codex'
        argv = command(a)
        self.assertIn('read-only', argv)
        self.assertIn('shell_tool', argv)
        self.assertIn('hooks', argv)
        self.assertEqual(final_text('claude', '{"result":"raw text"}'), 'raw text')
        with self.assertRaises(ValueError):
            final_text('codex', '{"type":"item.completed","item":{"type":"command_execution"}}')

    def test_worker_uses_stdin_not_shell_and_extracts_model_reply(self):
        program = 'import json,sys;d=sys.stdin.read();assert "输入资料" in d;print(json.dumps({"result":"raw response"}))'
        with patch('requirements.worker.command', return_value=[sys.executable, '-c', program]):
            self.assertEqual(run_model(dict(prompt='no tools', agent={'cli': 'claude'}), 3), 'raw response')

    def test_worker_timeout_ends_child(self):
        with patch('requirements.worker.command', return_value=[sys.executable, '-c', 'import time; time.sleep(20)']):
            import subprocess
            with self.assertRaises(subprocess.TimeoutExpired):
                run_model(dict(prompt='test', agent={'cli': 'claude'}), .05)

    def test_settings_do_not_expose_extra_agent_credentials(self):
        settings = load_settings()
        self.assertTrue(all(set(a) <= {'cli', 'vendor', 'model', 'effort', 'executable', 'auth', 'supported_tasks'}
                            for a in settings['agents'].values()))

    def test_isolated_codex_config_omits_mcp_hooks_and_private_files(self):
        import os
        from requirements.worker import isolated_codex_home
        source = self.root / 'codex-source'
        source.mkdir()
        (source / 'config.toml').write_text('openai_base_url="http://localhost:1234/v1"\n[hooks]\nexample="do not run"\n[mcp_servers.private]\ncommand="do not run"\n[model_providers.test]\nname="test"\nbase_url="http://localhost:1234/v1"\n')
        (source / 'auth.json').write_text('{"fixture":"anonymous-test"}')
        cwd=self.root/'isolated';cwd.mkdir()
        with patch.dict(os.environ, {'CODEX_HOME': str(source)}):
            target=Path(isolated_codex_home(cwd))
        import tomllib
        config=tomllib.loads((target/'config.toml').read_text())
        self.assertNotIn('mcp_servers',config)
        self.assertNotIn('hooks',config)
        self.assertEqual(config['model_providers']['test']['name'],'test')
        self.assertEqual((target/'auth.json').stat().st_mode & 0o777,0o600)
