import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cockpit.registry import Registry, load_registry


def fixture():
    return {
        'schema_version': 1, 'machine': 'anonymous-test',
        'agents': {'local': {'name': 'Local', 'adapter': 'ollama', 'executable': 'ollama',
                             'enabled': True, 'availability': 'installed_only',
                             'invocation_modes': ['cli_stateless']}},
        'models': {'small': {'name': 'Small fixture', 'vendor': 'fixture', 'model_id': 'fixture:30b',
                              'agent': 'local', 'enabled': True, 'availability': 'installed_only',
                              'invocation_mode': 'cli_stateless', 'supported_tasks': ['simple_text'],
                              'unsupported_tasks': ['designer'], 'unverified_tasks': ['coder'],
                              'auth': {'type': 'none'}}},
        'defaults': {'simple_text': {'agent': 'local', 'model': 'small'}},
    }


class RegistryTest(unittest.TestCase):
    def test_resolve_default_and_reject_weak_model_for_complex_work(self):
        registry = Registry(fixture())
        self.assertEqual(registry.select('simple_text')['model'], 'fixture:30b')
        for role in ['designer', 'coder']:
            with self.subTest(role=role), self.assertRaisesRegex(ValueError, '能力'):
                registry.select(role, model='small')

    def test_explicit_and_inherited_choices_precede_default(self):
        data = fixture()
        data['models']['other'] = dict(data['models']['small'], model_id='fixture:other')
        registry = Registry(data)
        self.assertEqual(registry.select('simple_text', inherited='other')['registry_model'], 'other')
        self.assertEqual(registry.select('simple_text', model='small', inherited='other')['registry_model'], 'small')

    def test_disabled_and_unavailable_models_are_not_candidates(self):
        for field, value in [('enabled', False), ('availability', 'unavailable')]:
            data = fixture()
            data['models']['small'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                Registry(data).select('simple_text')

    def test_invalid_references_capability_overlap_and_plaintext_credentials_rejected(self):
        for mutate in [lambda d: d['models']['small'].update(agent='missing'),
                       lambda d: d['defaults']['simple_text'].update(model='missing'),
                       lambda d: d['models']['small'].update(unsupported_tasks=['simple_text']),
                       lambda d: d['models']['small']['auth'].update(api_key='private-fixture')]:
            data = fixture()
            mutate(data)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError) as caught:
                Registry(data)
            self.assertNotIn('private-fixture', str(caught.exception))

    def test_environment_credential_only_resolved_at_execution(self):
        data = fixture()
        data['models']['small']['auth'] = {'type': 'environment', 'api_key_env': 'REGISTRY_TEST_KEY'}
        chosen = Registry(data).select('simple_text')
        from cockpit.registry import invocation_env
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'REGISTRY_TEST_KEY'):
                invocation_env(chosen)
        with patch.dict(os.environ, {'REGISTRY_TEST_KEY': 'private-fixture'}):
            self.assertEqual(invocation_env(chosen)['REGISTRY_TEST_KEY'], 'private-fixture')
            self.assertNotIn('private-fixture', json.dumps(chosen))

    def test_explicit_missing_or_malformed_registry_never_uses_hidden_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'registry.toml'
            with self.assertRaises(FileNotFoundError):
                load_registry(path)
            path.write_text('invalid = [')
            with self.assertRaises(ValueError):
                load_registry(path)

    def test_real_defaults_preserve_existing_roles(self):
        registry = load_registry()
        self.assertEqual(registry.select('designer')['model'], 'ai-code-with/claude-opus-5-5')
        self.assertEqual(registry.select('design_reviewer')['model'], 'gpt-6-sol')

    def test_registered_only_loading_and_empty_explicit_catalog(self):
        from requirements.llm_provider import load_model_registry, resolve_model_spec
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.yaml'
            path.write_text('agents:\n  only:\n    cli: codex\n    vendor: fixture\n    model: fixture/full-id\n')
            self.assertEqual(set(load_model_registry(path)), {'only'})
            with self.assertRaises(ValueError):
                resolve_model_spec('codex', {})
            path.write_text('invalid configuration')
            with self.assertRaises(ValueError):
                load_model_registry(path)

    def test_machine_override_and_cli_arguments_do_not_contain_credentials(self):
        from requirements.llm_provider import ModelSpec, build_model_argv
        spec = ModelSpec('local', 'ollama', 'fixture', 'fixture:30b', executable='/tmp/mock-ollama', invocation_mode='cli_stateless',
                         auth={'type': 'environment', 'api_key_env': 'REGISTRY_TEST_KEY'})
        argv = build_model_argv(spec, 'classify', '/tmp', mode='cli_stateless')
        self.assertEqual(argv, ['/tmp/mock-ollama', 'run', 'fixture:30b', 'classify'])
        self.assertEqual(build_model_argv(spec, 'classify', '/tmp'), argv)
        with self.assertRaisesRegex(ValueError, '无状态'):
            build_model_argv(spec, 'classify', '/tmp', mode='cli_session')
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'AUTODEV_AGENT_REGISTRY': str(Path(tmp)/'absent.toml')}):
            from cockpit.agents import parse_agents
            with self.assertRaises(FileNotFoundError):
                parse_agents('agent_registry: config/agents.toml\n')

    def test_denied_capability_never_starts_a_process(self):
        from requirements.agent_runner import run_agent_turn
        from requirements.llm_provider import ModelSpec
        spec = ModelSpec('small', 'ollama', 'fixture', 'fixture:30b', supported_tasks=('simple_text',),
                         unsupported_tasks=('requirements_analyst',))
        with patch('requirements.agent_runner.subprocess.Popen') as start:
            with self.assertRaisesRegex(ValueError, '能力'):
                run_agent_turn('small', 'design', '/tmp', None, registry={'small': spec}, mode='cli_stateless')
            start.assert_not_called()
        from requirements.worker import run_model
        with patch('requirements.worker.subprocess.Popen') as start:
            with self.assertRaisesRegex(ValueError, 'unsupported-task'):
                run_model({'prompt': 'review', 'role': 'reviewer', 'agent': {'supported_tasks': ['simple_text']}}, 1)
            start.assert_not_called()

    def test_role_override_preserves_registry_reference(self):
        from web.api import get_config_view, update_roles_config
        from cockpit.registry import ROOT
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'config.yaml').write_text((ROOT/'config.yaml').read_text())
            before = get_config_view(root)
            after = update_roles_config(root, {'analyst': 'claude-sonnet'}, before['version_hash'])
            self.assertEqual(after['roles']['analyst'], 'claude-sonnet')
            self.assertEqual(after['roles']['designer'], 'claude-opus')
            self.assertIn('agent_registry: config/agents.toml', (root/'config.yaml').read_text())

    def test_local_text_worker_returns_raw_reply(self):
        import sys
        from requirements.worker import command, final_text, run_model
        self.assertEqual(command({'cli': 'ollama', 'model': 'fixture:30b'})[:2], ['ollama', 'run'])
        self.assertEqual(final_text('ollama', ' answer\n'), 'answer')
        with patch('requirements.worker.command', return_value=[sys.executable, '-c', 'import sys;sys.stdin.read();print("fixture answer")']):
            self.assertEqual(run_model({'prompt': 'test', 'agent': {'cli': 'ollama', 'model': 'fixture:30b'}}, 2), 'fixture answer')


if __name__ == '__main__':
    unittest.main()
