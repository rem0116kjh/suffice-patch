#!/usr/bin/env python3
"""Native skill smoke tests. Does not alter installed skills or historical evals."""
import hashlib
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'evals'))
import run as harness
from tasks import TASKS, DISTRACTORS


def save(name, data):
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def stop(proc):
    if proc.poll() is None:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()


def discovery():
    with (HERE / 'discovery-stderr.log').open('w') as err:
        proc = subprocess.Popen(['codex', 'app-server', '--stdio'], cwd=ROOT,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=err, text=True, start_new_session=True)
        incoming = queue.Queue()
        def reader():
            for line in proc.stdout:
                try:
                    incoming.put(json.loads(line))
                except json.JSONDecodeError:
                    pass
        threading.Thread(target=reader, daemon=True).start()
        def request(id, method, params):
            proc.stdin.write(json.dumps({'id': id, 'method': method, 'params': params}) + '\n')
            proc.stdin.flush()
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                item = incoming.get(timeout=max(.1, deadline - time.monotonic()))
                if item.get('id') == id:
                    return item
            raise TimeoutError(method)
        try:
            initialized = request(1, 'initialize', {'clientInfo': {'name': 'suffice_runtime_audit', 'version': '1'}})
            assert 'result' in initialized, initialized
            proc.stdin.write(json.dumps({'method': 'initialized'}) + '\n')
            proc.stdin.flush()
            result = request(2, 'skills/list', {'cwds': [str(ROOT)], 'forceReload': True})
            assert 'result' in result, result
            entries = result['result']['data']
            relevant = [{'cwd': entry['cwd'], 'skills_total': len(entry['skills']),
                         'target': [s for s in entry['skills'] if s['name'] == 'suffice-patch'],
                         'target_errors': [e for e in entry['errors'] if 'suffice-patch' in e['path']],
                         'other_error_count': sum('suffice-patch' not in e['path'] for e in entry['errors'])}
                        for entry in entries]
            save('discovery.json', relevant)
            print('DISCOVERY', json.dumps(relevant, ensure_ascii=False), flush=True)
        finally:
            stop(proc)


COMMON = '''Work only in this disposable fixture. You may read installed skill instructions
when needed. Do not read sibling directories, hidden evaluator files, or other projects.
Do not use network tools, install dependencies, spawn agents, commit or push.
Use Python's standard library for local checks. Preserve unrelated work.
Report actual changes and checks. Do not modify any installed skills or settings.
'''


def skill_evidence(events, engine):
    """Avoid false positives from fixture paths that contain the project name."""
    installed = str(Path.home() / ('.agents' if engine == 'codex' else '.claude')
                    / 'skills/suffice-patch/SKILL.md')
    evidence = []
    for event in events:
        if engine == 'codex' and event.get('type') == 'item.completed':
            item = event.get('item', {})
            if (item.get('type') == 'agent_message' and 'suffice-patch' in item.get('text', '')) or (
                    item.get('type') == 'command_execution' and installed in item.get('command', '')):
                evidence.append(item)
        elif engine == 'claude' and event.get('type') == 'assistant':
            for block in event.get('message', {}).get('content', []):
                if (block.get('type') == 'tool_use' and block.get('name') == 'Skill'
                        and block.get('input', {}).get('skill') == 'suffice-patch') or (
                        installed in json.dumps(block)):
                    evidence.append(block)
    return evidence


def native_case(engine, task_name, explicit=True):
    name = engine + '-' + ('explicit' if explicit else 'implicit') + '-' + task_name
    folder = HERE / name
    folder.mkdir(exist_ok=False)
    work = folder / 'workspace'
    work.mkdir()
    task = TASKS[task_name]
    harness.seed(work, task)
    for args in [['init', '-q'], ['add', '.'],
                 ['-c', 'user.name=Eval Fixture', '-c', 'user.email=eval@invalid.local',
                  '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'fixture']]:
        subprocess.run(['git', *args], cwd=work, check=True, capture_output=True)
    before = harness.snapshot(work)
    # The body of SKILL.md is intentionally NOT inserted into this prompt.
    invocation = ('$suffice-patch' if engine == 'codex' else '/suffice-patch') + ' ' if explicit else ''
    prompt = invocation + task['prompt'] + '\n\n' + COMMON
    (folder / 'prompt.txt').write_text(prompt)
    if engine == 'codex':
        command = ['codex', 'exec', '--ignore-user-config', '--ephemeral', '--json',
                   '--skip-git-repo-check', '-s', 'workspace-write', '-m', 'gpt-6-astra', '-C', str(work)]
        config = {'model_reasoning_effort': 'low', 'approval_policy': 'never',
                  'web_search': 'disabled', 'project_doc_max_bytes': 0,
                  'suppress_unstable_features_warning': True,
                  'features.skip_host_skill_discovery': False,
                  'features.plugins': False, 'features.hooks': False,
                  'features.apps': False, 'features.multi_agent': False, 'features.memories': False}
        for key, value in config.items():
            command += ['-c', key + '=' + json.dumps(value)]
        command += ['-']
    else:
        command = ['claude', '-p', '--output-format', 'stream-json', '--verbose',
                   '--no-session-persistence', '--strict-mcp-config',
                   '--setting-sources', 'user',
                   '--settings', json.dumps({'disableAllHooks': True}),
                   '--tools', 'Read,Edit,Write,Bash,Glob,Grep,Skill',
                   '--allowedTools', 'Read,Edit,Write,Bash(python3 *),Bash(git diff*),Bash(git status*),Skill',
                   '--permission-mode', 'acceptEdits']
    start = time.monotonic()
    with (folder / 'events.jsonl').open('w') as out, (folder / 'stderr.log').open('w') as err:
        proc = subprocess.Popen(command, cwd=work, stdin=subprocess.PIPE,
                                stdout=out, stderr=err, text=True, start_new_session=True)
        timed_out = False
        try:
            proc.communicate(prompt, timeout=240)
        except subprocess.TimeoutExpired:
            timed_out = True
            stop(proc)
    after = harness.snapshot(work)
    metrics, diff = harness.diff_metrics(before, after)
    (folder / 'changes.diff').write_text(diff)
    checks = harness.grade(work, task)
    raw = (folder / 'events.jsonl').read_text()
    events = [json.loads(line) for line in raw.splitlines() if line.startswith('{')]
    if engine == 'codex':
        parsed = harness.parse_events(raw)
        completed = parsed['completed']
        evidence = skill_evidence(events, engine)
    else:
        final = next((e for e in reversed(events) if e.get('type') == 'result'), {})
        completed = final.get('subtype') == 'success' and not final.get('is_error', True)
        parsed = {'result': final}
        evidence = skill_evidence(events, engine)
        init = next((e for e in events if e.get('type') == 'system' and e.get('subtype') == 'init'), {})
        parsed['native_skill_list_contains_target'] = 'suffice-patch' in init.get('skills', [])
        parsed['native_slash_commands_contains_target'] = 'suffice-patch' in init.get('slash_commands', [])
        parsed['model'] = init.get('model')
    protected = all(after.get(f) == content for f, content in DISTRACTORS.items())
    noop = task_name != 'noop' or before == after
    result = {'engine': engine, 'task': task_name, 'explicit_invocation': explicit,
              'skill_body_injected_by_harness': False, 'returncode': proc.returncode,
              'timed_out': timed_out, 'duration_seconds': round(time.monotonic() - start, 3),
              'checks': checks, 'unrelated_preserved': protected, 'noop_preserved': noop,
              'success': proc.returncode == 0 and not timed_out and completed
                         and all(c['passed'] for c in checks) and protected and noop,
              **metrics, 'runtime': parsed, 'skill_evidence': evidence, 'command': command}
    (folder / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print('CASE', json.dumps({k: result[k] for k in ['engine', 'task', 'explicit_invocation', 'success',
                         'returncode', 'timed_out', 'duration_seconds', 'modified_paths']}, ensure_ascii=False), flush=True)
    return result


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'discovery':
        discovery()
    else:
        rows = []
        for case in [('codex', 'reuse', True), ('codex', 'auth', True),
                     ('codex', 'noop', True), ('codex', 'localized', False),
                     ('claude', 'reuse', True)]:
            rows.append(native_case(*case))
            save('results.json', rows)
