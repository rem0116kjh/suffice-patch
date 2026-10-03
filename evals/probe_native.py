"""Verify repo-skill activation overrides without changing user configuration."""
import json
import os
from pathlib import Path
import queue
import shutil
import signal
import subprocess
import tempfile
import threading


def main():
    bundle = Path('candidates/v3-tools/suffice-patch').resolve()
    host = Path.home() / '.agents/skills/suffice-patch/SKILL.md'
    results = []
    with tempfile.TemporaryDirectory(prefix='suffice-native-probe-') as directory:
        root = Path(directory).resolve()
        subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
        target = root / '.agents/skills/suffice-patch'
        shutil.copytree(bundle, target)
        for enabled in [False, True]:
            override = ('skills.config=[{path=' + json.dumps(str(host)) + ',enabled=false},'
                        '{path=' + json.dumps(str(target / 'SKILL.md')) + ',enabled=' + str(enabled).lower() + '}]')
            command = ['codex', 'app-server', '--stdio', '--strict-config', '-c', override, '-c', 'features.plugins=false']
            with open(os.devnull, 'w') as err:
                proc = subprocess.Popen(command, cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=err, text=True, start_new_session=True)
                incoming = queue.Queue()
                def receive(proc, incoming):
                    for line in proc.stdout:
                        try:
                            incoming.put(json.loads(line))
                        except ValueError:
                            pass
                threading.Thread(target=receive, args=(proc, incoming), daemon=True).start()
                def request(id, method, params):
                    proc.stdin.write(json.dumps({'id': id, 'method': method, 'params': params}) + '\n')
                    proc.stdin.flush()
                    while True:
                        item = incoming.get(timeout=15)
                        if item.get('id') == id:
                            return item
                try:
                    result = request(1, 'initialize', {'clientInfo': {'name': 'suffice_probe', 'version': '1'}})
                    assert 'result' in result, result
                    proc.stdin.write('{"method":"initialized"}\n')
                    proc.stdin.flush()
                    result = request(2, 'skills/list', {'cwds': [str(root)], 'forceReload': True})
                    matches = [skill for entry in result['result']['data'] for skill in entry['skills']
                               if skill['name'] == 'suffice-patch']
                    states = {entry['path']: entry['enabled'] for entry in matches}
                    assert states[str(target / 'SKILL.md')] == enabled and states[str(host)] is False, states
                    assert sum(entry['enabled'] for entry in matches) == int(enabled)
                    results.append({'expected_repo_enabled': enabled, 'target': matches, 'passed': True})
                finally:
                    if proc.poll() is None:
                        os.killpg(proc.pid, signal.SIGTERM)
                        proc.wait(timeout=5)
    Path('evals/v3-native-discovery.json').write_text(json.dumps(results, indent=2) + '\n')
    print('PASS: baseline disables both copies; native conditions enable only the repo candidate.')


if __name__ == '__main__':
    main()
