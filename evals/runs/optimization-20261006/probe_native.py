"""Read-only native discovery preflight for the 2026-10-06 optimization run."""
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import signal
import subprocess
import tempfile
import threading

HERE = Path(__file__).resolve().parent
BUNDLE = HERE / 'bundle'


def main():
    host = Path.home() / '.agents/skills/suffice-patch/SKILL.md'
    config = {'model': 'gpt-6-astra', 'model_reasoning_effort': 'low',
              'approval_policy': 'never', 'web_search': 'disabled',
              'project_doc_max_bytes': 0, 'suppress_unstable_features_warning': True,
              'features.skip_host_skill_discovery': False, 'features.plugins': False,
              'features.hooks': False, 'features.apps': False,
              'features.memories': False, 'features.multi_agent': False}
    results = []
    with tempfile.TemporaryDirectory(prefix='suffice-optimization-probe-') as directory:
        root = Path(directory).resolve()
        subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
        target = root / '.agents/skills/suffice-patch'
        shutil.copytree(BUNDLE, target)
        for enabled in [False, True]:
            override = ('skills.config=[{path=' + json.dumps(str(host)) + ',enabled=false},'
                        '{path=' + json.dumps(str(target / 'SKILL.md')) + ',enabled=' + str(enabled).lower() + '}]')
            command = ['codex', 'app-server', '--stdio', '--strict-config']
            for key, value in config.items():
                command += ['-c', key + '=' + json.dumps(value)]
            command += ['-c', override]
            with (HERE / f'probe-{enabled}-stderr.log').open('w') as err:
                proc = subprocess.Popen(command, cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=err, text=True, start_new_session=True)
                incoming = queue.Queue()
                def receive():
                    for line in proc.stdout:
                        try:
                            incoming.put(json.loads(line))
                        except ValueError:
                            pass
                threading.Thread(target=receive, daemon=True).start()
                def request(id, method, params):
                    proc.stdin.write(json.dumps({'id': id, 'method': method, 'params': params}) + '\n')
                    proc.stdin.flush()
                    while True:
                        item = incoming.get(timeout=15)
                        if item.get('id') == id:
                            return item
                try:
                    initialized = request(1, 'initialize', {'clientInfo': {'name': 'suffice_optimization_probe', 'version': '1'}})
                    assert 'result' in initialized, initialized
                    proc.stdin.write('{"method":"initialized"}\n')
                    proc.stdin.flush()
                    result = request(2, 'skills/list', {'cwds': [str(root)], 'forceReload': True})
                    entries = result['result']['data']
                    matches = [skill for entry in entries for skill in entry['skills']
                               if skill['name'] == 'suffice-patch']
                    states = {entry['path']: entry['enabled'] for entry in matches}
                    assert states[str(target / 'SKILL.md')] == enabled and states[str(host)] is False, states
                    assert sum(entry['enabled'] for entry in matches) == int(enabled)
                    results.append({'expected_repo_enabled': enabled, 'target': matches,
                                    'passed': True, 'command': command,
                                    'skill_errors': [error for entry in entries for error in entry.get('errors', [])],
                                    'enabled_other_skill_names': sorted(skill['name'] for entry in entries
                                         for skill in entry['skills'] if skill['enabled'] and skill['name'] != 'suffice-patch')})
                finally:
                    if proc.poll() is None:
                        os.killpg(proc.pid, signal.SIGTERM)
                        proc.wait(timeout=5)
    evidence = {'cli': subprocess.check_output(['codex', '--version'], text=True).strip(),
                'config': config,
                'note': 'App-server discovery uses explicit overrides; exec additionally uses --ignore-user-config.',
                'bundle_hashes': {str(p.relative_to(BUNDLE)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in BUNDLE.rglob('*') if p.is_file()},
                'results': results}
    (HERE / 'native-discovery.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print('PASS: baseline disables host and repo; implicit enables only the repo candidate.')


if __name__ == '__main__':
    main()
