"""Isolated real AutoLoop + fake command integration. Never calls a paid model."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from requirements.agent import HubAgent
from driver.hub import Hub, load_config


def main():
    with tempfile.TemporaryDirectory(prefix='requirements-hub-') as tmp:
        tmp = Path(tmp)
        home, root = tmp / 'home', tmp / 'root'
        (root / 'workspace').mkdir(parents=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        bindir = tmp / 'bin'; bindir.mkdir()
        notify = bindir / 'osascript'; notify.write_text('#!/bin/sh\nexit 0\n'); notify.chmod(0o755)
        env = dict(os.environ, AGENT_AUTOLOOP_HOME=str(home), PATH=str(bindir) + ':' + os.environ['PATH'])
        cli = ['node', '--disable-warning=ExperimentalWarning', str(Path('~/code/agent-autoloop/bin/agent-autoloop.ts').expanduser())]
        subprocess.run(cli + ['init', '--command', 'true {prompt}', '--no-service', '--port', str(port)], env=env, check=True, capture_output=True)
        fake = tmp / 'fake.py'
        fake.write_text('import json,sys;from pathlib import Path\nc=json.loads(Path(sys.argv[2]).read_text());p=Path(sys.argv[1])/c["events"][0]["subject"];(p/"raw-output.txt").write_text("{\\"reply\\":\\"fake hub verified\\"}");print("done")\n')
        class TestAgent(HubAgent):
            def install(self, data):
                etype = super().install(data)
                rules = json.loads((home / 'rules.json').read_text())
                for name, agent in rules['agents'].items():
                    if name.startswith('requirements-'):
                        agent['command'] = [sys.executable, str(fake), str(root / 'workspace'), '{context}']
                from driver.setup import install_rules
                install_rules(home, rules)
                time.sleep(.3)
                return etype
        proc = subprocess.Popen(cli + ['up'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            hub = Hub(load_config(home))
            for _ in range(60):
                try:
                    hub.state(); break
                except Exception:
                    time.sleep(.1)
            folder = root / 'workspace/requirements/Q111111111111/rounds/0001/calls/0001/attempt-1'
            folder.mkdir(parents=True)
            adapter = TestAgent(root, home, hub=hub)
            result = adapter(dict(session_id='Q111111111111', kind='clarify', role='analyst', call_id='requirements-isolated-test', agent={}), folder, 15)
            assert json.loads(result)['reply'] == 'fake hub verified'
            print('PASS: isolated AutoLoop rules, dispatch, facts and raw reply')
        finally:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL); proc.wait()


if __name__ == '__main__':
    main()
