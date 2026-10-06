#!/usr/bin/env python3
"""Frozen, paired external-repository evaluation; prepare never calls a model."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import platform
import queue
import random
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIRS = {'.git', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache'}
BUNDLE = ('SKILL.md', 'scripts/collect_context.py', 'scripts/context_languages.py')
CONFIG = {'approval_policy': 'never', 'web_search': 'disabled', 'project_doc_max_bytes': 0,
          'suppress_unstable_features_warning': True, 'features.skip_host_skill_discovery': False,
          'features.plugins': False, 'features.hooks': False, 'features.apps': False,
          'features.memories': False, 'features.multi_agent': False,
          'sandbox_workspace_write.network_access': False}


def sha(body):
    return hashlib.sha256(body).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def checked(command, cwd=None, env=None):
    return subprocess.check_output(command, cwd=cwd, env=env, stderr=subprocess.STDOUT).decode().strip()


def snapshot(work):
    """Preserve raw bytes, symlink targets, and permission bits without following links."""
    result = {}
    for folder, directories, files in os.walk(work, followlinks=False):
        directories[:] = sorted(d for d in directories if d not in CACHE_DIRS)
        for name in files + [d for d in directories if (Path(folder) / d).is_symlink()]:
            path = Path(folder) / name
            mode = path.lstat().st_mode
            kind = 'link' if stat.S_ISLNK(mode) else 'file'
            body = os.fsencode(os.readlink(path)) if kind == 'link' else path.read_bytes()
            result[str(path.relative_to(work))] = (kind, stat.S_IMODE(mode), body)
    return result


def snapshot_hashes(items):
    return {name: {'kind': row[0], 'mode': row[1], 'sha256': sha(row[2])}
            for name, row in sorted(items.items())}


def compare(before, after, task):
    changed = sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))
    forbidden, patches = [], []
    counts = {'loc_added': 0, 'loc_deleted': 0}
    for name in changed:
        new_test = (name not in before and name.startswith('tests/') and name.endswith('.py')
                    and after[name][0] == 'file' and task.get('allow_new_tests', True))
        allowed = name in task['allowed_source_paths'] or new_test
        if task.get('expected_noop') or not allowed:
            forbidden.append(name)
        left, right = before.get(name, ('', 0, b''))[2], after.get(name, ('', 0, b''))[2]
        patch = list(difflib.unified_diff(left.decode(errors='replace').splitlines(True),
                                        right.decode(errors='replace').splitlines(True),
                                        fromfile='a/' + name, tofile='b/' + name))
        patches.extend(patch or [f'File type/mode changed: {name}\n'])
        counts['loc_added'] += sum(line.startswith('+') and not line.startswith('+++') for line in patch)
        counts['loc_deleted'] += sum(line.startswith('-') and not line.startswith('---') for line in patch)
    return {'modified_paths': changed, 'files_modified': len(changed),
            'forbidden_changes': forbidden, **counts}, ''.join(patches)


def stop(proc):
    if proc.poll() is None:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()


def process(command, cwd, env, prefix, timeout, stdin=None):
    start, timed_out = time.monotonic(), False
    write_json(prefix.with_suffix('.command.json'), command)
    with prefix.with_suffix('.stdout.log').open('wb') as stdout, prefix.with_suffix('.stderr.log').open('wb') as stderr:
        proc = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            proc.communicate(stdin, timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            stop(proc)
    return {'returncode': proc.returncode, 'timed_out': timed_out,
            'duration_seconds': round(time.monotonic() - start, 6)}


def overrides(discovered=(), enabled=()):
    result = []
    for key, value in CONFIG.items():
        result += ['-c', key + '=' + json.dumps(value)]
    if discovered:
        rows = ['{path=' + json.dumps(p) + ',enabled=' + str(p in enabled).lower() + '}'
                for p in sorted(set(discovered))]
        result += ['-c', 'skills.config=[' + ','.join(rows) + ']']
    return result


def discover(cwds, config, folder):
    """Use the native discovery API without starting a thread or model turn."""
    folder.mkdir(parents=True)
    command = ['codex', 'app-server', '--stdio', '--strict-config', *config]
    write_json(folder / 'command.json', command)
    inbox, raw = queue.Queue(), []
    with (folder / 'stderr.log').open('w') as err:
        proc = subprocess.Popen(command, cwd=cwds[0], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=err, text=True, start_new_session=True)
        def receive():
            for line in proc.stdout:
                raw.append(line)
                try:
                    inbox.put(json.loads(line))
                except ValueError:
                    pass
        threading.Thread(target=receive, daemon=True).start()
        def rpc(ident, method, params):
            proc.stdin.write(json.dumps({'id': ident, 'method': method, 'params': params}) + '\n')
            proc.stdin.flush()
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                item = inbox.get(timeout=max(.01, deadline - time.monotonic()))
                if item.get('id') == ident:
                    if 'error' in item:
                        raise RuntimeError(item['error'])
                    return item['result']
            raise TimeoutError(method)
        try:
            rpc(1, 'initialize', {'clientInfo': {'name': 'suffice_external_eval', 'version': '1'}})
            proc.stdin.write('{"method":"initialized"}\n')
            proc.stdin.flush()
            result = rpc(2, 'skills/list', {'cwds': [str(x) for x in cwds], 'forceReload': True})
            write_json(folder / 'result.json', result)
            return result['data']
        finally:
            stop(proc)
            (folder / 'events.jsonl').write_text(''.join(raw))


def environment(task, work):
    env = os.environ.copy()
    env.pop('PYTHONOPTIMIZE', None)
    env.update(PYTHONPATH=str(work / task['source_subdir']), PYTHONDONTWRITEBYTECODE='1',
               PATH=str(Path(task['python_executable']).parent) + os.pathsep + env.get('PATH', ''))
    return env


def prompt_for(task):
    test = shlex.join([x.replace('{python}', task['python_executable']) for x in task['test_command']])
    return task['prompt'] + '\n\n' + (
        'Inspect and edit project files only in this checkout. You may execute the designated Python '
        'interpreter and installed local tools; do not read source or reference files from other directories, '
        'use the network, install '
        'dependencies, spawn agents, commit, or inspect hidden evaluator files. Preserve all '
        'preexisting files except these allowed sources: ' + ', '.join(task['allowed_source_paths']) + '. '
        + ('Do not add files. ' if task.get('expected_noop') or not task.get('allow_new_tests', True)
           else 'You may add new Python regression tests under tests/. ') +
        'Preserve LOCAL_NOTES.md and repository instructions. Use Python ' + task['python_executable'] +
        '. Run the existing checks with: PYTHONPATH=' + task['source_subdir'] + ' ' + test +
        '. Report what you changed and actually verified.\n')


def seed_case(folder, task, assets):
    work = folder / 'workspace'
    work.mkdir(parents=True)
    with tarfile.open(assets / task['id'] / 'base.tar') as archive:
        archive.extractall(work, filter='data')
    native = work / '.agents/skills/suffice-patch'
    if native.exists() or (work / 'LOCAL_NOTES.md').exists():
        raise ValueError('Fixture conflicts with existing files')
    for name in BUNDLE:
        target = native / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(assets / 'skill' / name, target)
    for args in (['init', '-q'], ['add', '.'], ['-c', 'user.name=External Eval',
                 '-c', 'user.email=eval@invalid.local', '-c', 'core.hooksPath=/dev/null',
                 'commit', '-qm', 'Pinned source fixture']):
        checked(['git', *args], cwd=work)
    (work / 'LOCAL_NOTES.md').write_bytes(b'User draft: preserve this untracked file exactly.\n')
    write_json(folder / 'before.json', snapshot_hashes(snapshot(work)))
    (folder / 'prompt.txt').write_text(prompt_for(task))


def parse_events(raw):
    events = []
    for line in raw.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    usages = [e['usage'] for e in events if e.get('type') == 'turn.completed' and 'usage' in e]
    items = [e['item'] for e in events if e.get('type') == 'item.completed' and 'item' in e]
    keys = ('input_tokens', 'cached_input_tokens', 'cache_write_input_tokens',
            'output_tokens', 'reasoning_output_tokens')
    result = {k: sum(u[k] for u in usages) if usages and all(isinstance(u.get(k), int) for u in usages)
              else None for k in keys}
    commands = [i for i in items if i.get('type') == 'command_execution']
    result.update(raw_usage=usages, completed=any(e.get('type') == 'turn.completed' for e in events)
                  and not any(e.get('type') == 'turn.failed' for e in events),
                  tool_calls=sum(i.get('type') not in {'agent_message', 'reasoning', 'error'} for i in items),
                  commands=[i.get('command', '') for i in commands],
                  tool_output_bytes=sum(len(i.get('aggregated_output', '').encode()) for i in items))
    result['helper_invoked'] = any('collect_context.py' in i.get('command', '') for i in commands)
    result['helper_success'] = any('collect_context.py' in i.get('command', '') and i.get('exit_code') == 0
                                   and re.search(r'^ROOT: ', i.get('aggregated_output', ''), re.MULTILINE)
                                   and re.search(r'^FILE: ', i.get('aggregated_output', ''), re.MULTILINE)
                                   for i in commands)
    result['skill_read'] = any('SKILL.md' in i.get('command', '') or '# SufficePatch' in i.get('aggregated_output', '')
                               for i in commands)
    return result


def prepare(args):
    out = args.out
    out.mkdir(parents=True, exist_ok=False)
    assets = out / 'assets'
    assets.mkdir()
    sources = {}
    def freeze(source, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        sources[str(target.relative_to(out))] = sha(target.read_bytes())
    freeze(Path(__file__), assets / 'external_run.py')
    freeze(ROOT / 'evals/GENERALIZATION_PLAN_20261006.md', assets / 'GENERALIZATION_PLAN_20261006.md')
    for name in BUNDLE:
        freeze(ROOT / name, assets / 'skill' / name)
    tasks = []
    for path in args.tasks.split(','):
        source = Path(path).resolve()
        task = json.loads(source.read_text())
        if not re.fullmatch(r'[A-Za-z0-9_-]+', task['id']) or any(t['id'] == task['id'] for t in tasks):
            raise ValueError('Invalid or duplicate task id')
        python = task.get('python_executable')
        if not python:
            family = 'itsdangerous-py312' if task['id'].startswith('itsdangerous') else 'packaging-venv'
            python = '/tmp/suffice-' + family + '/bin/python'
        task['python_executable'] = python
        for field in ('base_commit', 'reference_commit'):
            if not re.fullmatch(r'[0-9a-f]{40}', task[field]):
                raise ValueError('Full pinned commit required')
        target = assets / task['id']
        freeze(source, target / 'task.source.json')
        freeze(source.parent / task['grader'], target / 'grader.py')
        for field, name in (('base_commit', 'base.tar'), ('reference_commit', 'reference.tar')):
            with (target / name).open('wb') as stream:
                subprocess.run(['git', 'archive', '--format=tar', task[field]], cwd=task['prep_repo'], stdout=stream, check=True)
            sources[str((target / name).relative_to(out))] = sha((target / name).read_bytes())
        versions = {'python': checked([python, '--version']), 'pip_freeze': checked([python, '-m', 'pip', 'freeze'])}
        write_json(target / 'environment.json', versions)
        sources[str((target / 'environment.json').relative_to(out))] = sha((target / 'environment.json').read_bytes())
        task['environment'] = versions
        tasks.append(task)
    pairs = [(task['id'], repeat + 1) for task in tasks for repeat in range(args.repeats)]
    random.Random(args.seed).shuffle(pairs)
    schedule = []
    by_id = {t['id']: t for t in tasks}
    for index, (task_id, repeat) in enumerate(pairs):
        task_index = next(i for i, task in enumerate(tasks) if task['id'] == task_id)
        arms = ('baseline', 'implicit') if (task_index + repeat) % 2 == 0 else ('implicit', 'baseline')
        for arm in arms:
            case = {'pair': index + 1, 'task': task_id, 'repeat': repeat, 'arm': arm,
                    'run': f'{index + 1:02d}-{task_id}-r{repeat}-{arm}'}
            seed_case(out / case['run'], by_id[task_id], assets)
            for name in ('before.json', 'prompt.txt'):
                path = out / case['run'] / name
                sources[str(path.relative_to(out))] = sha(path.read_bytes())
            schedule.append(case)
    cwds = [(out / c['run'] / 'workspace').resolve() for c in schedule]
    initial = discover(cwds, overrides(), out / 'discovery-initial')
    discovered = sorted({s['path'] for entry in initial for s in entry['skills']})
    for arm in ('baseline', 'implicit'):
        selected = [c for c in schedule if c['arm'] == arm]
        roots = [(out / c['run'] / 'workspace').resolve() for c in selected]
        enabled = [str(p / '.agents/skills/suffice-patch/SKILL.md') for p in roots] if arm == 'implicit' else []
        records = discover(roots, overrides(discovered, enabled), out / ('discovery-' + arm))
        if len(records) != len(roots):
            raise RuntimeError('Incomplete discovery response')
        for record in records:
            active = [s for s in record['skills'] if s.get('enabled')]
            expected = ['suffice-patch'] if arm == 'implicit' else []
            if sorted(s['name'] for s in active) != expected or any(s['path'] not in enabled for s in active):
                raise RuntimeError('Skill isolation failed: ' + str(active))
    manifest = {'version': 2, 'bundle_files': list(BUNDLE), 'model': args.model, 'effort': args.effort, 'timeout': args.timeout,
                'repeats': args.repeats, 'seed': args.seed, 'tasks': tasks, 'schedule': schedule,
                'sources': sources, 'discovered_skill_paths': discovered, 'config': CONFIG,
                'cli': checked(['codex', '--version']), 'platform': platform.platform(),
                'harness_python': sys.version, 'prepared_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'discovery_passed': True, 'actual_usd': None}
    write_json(out / 'manifest.json', manifest)
    (out / 'manifest.sha256').write_text(sha((out / 'manifest.json').read_bytes()) + '\n')
    write_json(out / 'results.json', [])
    return manifest


def run_case(out, manifest, case):
    folder = out / case['run']
    work = (folder / 'workspace').resolve()
    task = next(t for t in manifest['tasks'] if t['id'] == case['task'])
    before = snapshot(work)
    if snapshot_hashes(before) != json.loads((folder / 'before.json').read_text()):
        raise RuntimeError('Prepared checkout was changed: ' + case['run'])
    if (folder / 'started.json').exists():
        raise RuntimeError('Incomplete case exists; refusing to overwrite: ' + case['run'])
    write_json(folder / 'started.json', {'started_at': time.time()})
    native = str(work / '.agents/skills/suffice-patch/SKILL.md')
    enabled = [native] if case['arm'] == 'implicit' else []
    command = ['codex', 'exec', '--ignore-user-config', '--ephemeral', '--json', '--strict-config',
               '--skip-git-repo-check', '-s', 'workspace-write', '-m', manifest['model'], '-C', str(work),
               *overrides(manifest['discovered_skill_paths'], enabled), '-c',
               'model_reasoning_effort=' + json.dumps(manifest['effort']), '-']
    execution = process(command, work, environment(task, work), folder / 'agent', manifest['timeout'],
                        (folder / 'prompt.txt').read_bytes())
    shutil.copyfile(folder / 'agent.stdout.log', folder / 'events.jsonl')
    usage = parse_events((folder / 'events.jsonl').read_text())
    after = snapshot(work)
    metrics, patch = compare(before, after, task)
    (folder / 'changes.diff').write_text(patch)
    write_json(folder / 'after.json', snapshot_hashes(after))
    grading_env = environment(task, work)
    import_code = ('import importlib,json,pathlib; p=pathlib.Path(importlib.import_module('
                   + repr(task['import_package']) + ').__file__).resolve(); '
                   + 'assert p.is_relative_to(pathlib.Path(' + repr(str(work / task['source_subdir']))
                   + ').resolve()), str(p); print(json.dumps({"import_origin": str(p)}))')
    import_hidden = process([task['python_executable'], '-B', '-c', import_code], work, grading_env,
                            folder / 'import-hidden', 90)
    hidden = process([task['python_executable'], '-B', '-'], work, grading_env, folder / 'hidden', 90,
                     (out / 'assets' / task['id'] / 'grader.py').read_bytes())
    import_upstream = process([task['python_executable'], '-B', '-c', import_code], work, grading_env,
                              folder / 'import-upstream', 90)
    upstream = process([x.replace('{python}', task['python_executable']) for x in task['test_command']],
                       work, grading_env, folder / 'upstream', 90)
    bundle_ok = all(after.get('.agents/skills/suffice-patch/' + name) == before.get('.agents/skills/suffice-patch/' + name)
                    for name in BUNDLE)
    contaminated = case['arm'] == 'baseline' and (usage['helper_invoked'] or usage['skill_read'])
    complete = execution['returncode'] == 0 and not execution['timed_out'] and usage['completed']
    valid = not contaminated
    success = (complete and valid and hidden['returncode'] == upstream['returncode'] == 0
               and import_hidden['returncode'] == import_upstream['returncode'] == 0
               and not hidden['timed_out'] and not upstream['timed_out'] and not metrics['forbidden_changes'] and bundle_ok)
    result = {**case, **execution, **usage, **metrics, 'hidden': hidden, 'upstream': upstream,
              'import_hidden': import_hidden, 'import_upstream': import_upstream,
              'bundle_intact': bundle_ok, 'noop_preserved': not task.get('expected_noop') or before == after,
              'valid': valid, 'baseline_contamination': contaminated, 'success': success,
              'comparison_valid': valid, 'protected_preserved': not metrics['forbidden_changes'] and bundle_ok,
              'added_files': sorted(after.keys() - before.keys()), 'skill_used': usage['helper_success'],
              'infrastructure_failure': not complete and not execution['timed_out'], 'actual_usd': None,
              'prompt_sha256': sha((folder / 'prompt.txt').read_bytes()), 'command': command}
    write_json(folder / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--tasks', default='')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--seed', type=int, default=20261006)
    parser.add_argument('--model', default='gpt-6-astra')
    parser.add_argument('--effort', default='low')
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    args.out = args.out.resolve()
    if args.resume:
        body = (args.out / 'manifest.json').read_bytes()
        if sha(body) != (args.out / 'manifest.sha256').read_text().strip():
            parser.error('Frozen manifest was modified')
        manifest = json.loads(body)
        for path, expected in manifest['sources'].items():
            if sha((args.out / path).read_bytes()) != expected:
                parser.error('Frozen source was modified: ' + path)
        if manifest['config'] != CONFIG:
            parser.error('Runner configuration differs from frozen configuration')
        if sha(Path(__file__).read_bytes()) != manifest['sources']['assets/external_run.py']:
            parser.error('Runner differs from frozen runner; invoke assets/external_run.py')
        if checked(['codex', '--version']) != manifest['cli']:
            parser.error('Codex version changed since preparation')
        verified_python = set()
        for task in manifest['tasks']:
            python = task['python_executable']
            if python in verified_python:
                continue
            if checked([python, '--version']) != task['environment']['python']:
                parser.error('Python version changed since preparation: ' + task['id'])
            if checked([python, '-m', 'pip', 'freeze']) != task['environment']['pip_freeze']:
                parser.error('Python dependencies changed since preparation: ' + task['id'])
            verified_python.add(python)
    else:
        if not args.tasks or args.repeats < 1 or args.timeout < 1:
            parser.error('Provide task JSON paths and positive repeats/timeout')
        manifest = prepare(args)
    if args.prepare_only:
        print('PREPARED', args.out, 'cases=' + str(len(manifest['schedule'])), flush=True)
        return
    rows, consecutive = [], 0
    for case in manifest['schedule']:
        result_path = args.out / case['run'] / 'result.json'
        if result_path.exists():
            result = json.loads(result_path.read_text())
        else:
            print('START', case['run'], flush=True)
            result = run_case(args.out, manifest, case)
            print('DONE', case['run'], 'success=' + str(result['success']), flush=True)
        rows.append(result)
        write_json(args.out / 'results.json', rows)
        consecutive = consecutive + 1 if result['infrastructure_failure'] else 0
        if consecutive >= 2:
            write_json(args.out / 'STOPPED.json', {'reason': 'Two consecutive infrastructure failures', 'completed': len(rows)})
            break


if __name__ == '__main__':
    main()
