"""AutoLoop command adapter: tools disabled, only the final model text is retained."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import tomllib
import shutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cockpit.store import atomic_write


def command(agent):
    model = agent['model']
    if agent['cli'] == 'claude':
        return ['claude', '-p', '--output-format', 'json', '--model', model,
                '--effort', agent.get('effort', 'low'), '--tools', '', '--safe-mode',
                '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                '--disable-slash-commands', '--no-session-persistence',
                '--settings', '{"disableAllHooks":true}']
    if agent['cli'] != 'codex':
        raise ValueError('unsupported-cli')
    argv = ['codex', 'exec', '--json', '--ephemeral', '--skip-git-repo-check', '--ignore-rules',
            '--sandbox', 'read-only', '-m', model, '-c', 'approval_policy="never"',
            '-c', 'model_reasoning_effort=' + json.dumps(agent.get('effort', 'low')),
            '-c', 'project_doc_max_bytes=0', '-c', 'developer_instructions=""',
            '-c', 'web_search="disabled"', '-c', 'notify=[]', '-c', 'mcp_servers={}']
    for feature in ['shell_tool', 'unified_exec', 'code_mode_host', 'browser_use', 'browser_use_external',
                    'browser_use_full_cdp_access', 'computer_use', 'apps', 'plugins', 'remote_plugin',
                    'hooks', 'skill_search', 'image_generation', 'view_image', 'sleep_tool', 'goals']:
        argv += ['--disable', feature]
    return argv + ['-']


def isolated_codex_home(folder):
    """Keep provider/auth configuration, excluding user tools, hooks and plugins."""
    source = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
    target = folder / 'codex-home'
    target.mkdir(mode=0o700)
    def literal(value):
        if isinstance(value, dict):
            return '{' + ','.join(json.dumps(k) + '=' + literal(v) for k, v in value.items()) + '}'
        if isinstance(value, list):
            return '[' + ','.join(literal(v) for v in value) + ']'
        return json.dumps(value, ensure_ascii=False)
    path = source / 'config.toml'
    config = tomllib.loads(path.read_text()) if path.exists() else {}
    safe = {k: v for k, v in config.items() if k in {
        'model_provider', 'model_providers', 'openai_base_url', 'model_catalog_json', 'service_tier'}}
    dest = target / 'config.toml'
    dest.write_text('\n'.join(k + '=' + literal(v) for k, v in safe.items()))
    dest.chmod(0o600)
    for name in ['auth.json']:
        if (source / name).exists():
            shutil.copyfile(source / name, target / name)
            (target / name).chmod(0o600)
    return str(target)


def final_text(cli, stdout):
    if cli == 'claude':
        result = json.loads(stdout)
        if result.get('is_error'):
            raise ValueError('model-error')
        return result.get('result') or json.dumps(result.get('structured_output'))
    final = None
    for line in stdout.splitlines():
        event = json.loads(line)
        item = event.get('item', {})
        if item.get('type') in {'command_execution', 'file_change', 'mcp_tool_call', 'web_search'}:
            raise ValueError('unexpected-tool-use')
        if event['type'] == 'item.completed' and item.get('type') == 'agent_message':
            final = item['text']
        if event['type'] in {'turn.failed', 'error'}:
            raise ValueError('model-error')
    if final is None:
        raise ValueError('missing-final-response')
    return final


def run_model(data, timeout):
    prompt = data['prompt'] + '\n\n输入资料 JSON：\n' + json.dumps(data, ensure_ascii=False)
    if len(prompt.encode()) > 128000:
        raise ValueError('context-too-large')
    with tempfile.TemporaryDirectory(prefix='requirements-model-') as cwd:
        env = dict(os.environ)
        if data['agent']['cli'] == 'codex':
            env['CODEX_HOME'] = isolated_codex_home(Path(cwd))
        proc = subprocess.Popen(command(data['agent']), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, cwd=cwd, env=env, start_new_session=True)
        try:
            stdout, _ = proc.communicate(prompt, timeout=timeout)
            if proc.returncode:
                raise ValueError('cli-failed')
            return final_text(data['agent']['cli'], stdout)
        except BaseException:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            raise
        finally:
            for stream in [proc.stdin, proc.stdout, proc.stderr]:
                if stream is not None:
                    stream.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--input-root', required=True)
    ap.add_argument('--context', required=True)
    args = ap.parse_args(argv)
    root = Path(args.input_root).resolve()
    context = json.loads(Path(args.context).read_text())
    events = context.get('events', [])
    if len(events) != 1:
        raise ValueError('one-event-required')
    rel = Path(events[0]['subject'])
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('invalid-subject')
    folder = root / rel
    folder.resolve().relative_to(root)
    if any(p.is_symlink() for p in [folder, *folder.parents] if p != root and root in p.parents):
        raise ValueError('symlink-subject')
    if (folder / 'cancelled').exists():
        return 1
    data = json.loads((folder / 'input.json').read_text())
    if not (folder / 'raw-output.txt').exists():
        raw = run_model(data, data.get('timeout_s', 900))
        if (folder / 'cancelled').exists():
            return 1
        atomic_write(folder / 'raw-output.txt', raw)
    print('需求模型调用完成')
    return 0


if __name__ == '__main__':
    def interrupted(signum, frame):
        raise InterruptedError('worker interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.TimeoutExpired, InterruptedError):
        print('需求调用失败，请检查登录、模型参数或超时；未采纳任何不完整回复', file=sys.stderr)
        sys.exit(1)
