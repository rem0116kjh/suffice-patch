#!/usr/bin/env python3
"""Frozen two-release comparison using the existing external evaluator primitives."""
import argparse
import json
from pathlib import Path
import platform
import random
import re
import shutil
import subprocess
import sys
import tarfile
import time
import zipfile

import external_run as core

ROOT = Path(__file__).resolve().parents[1]
ARMS = ('v4', 'v5')
ARCHIVES = {'v4': 'suffice-patch-v4.zip', 'v5': 'suffice-patch-v5.0.0.zip'}


def parse_events(raw):
    result = core.parse_events(raw)
    commands = []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get('type') == 'item.completed' and event.get('item', {}).get('type') == 'command_execution':
            commands.append(event['item'])
    # A filename in cat/rg output is not helper execution. Accept Python and direct
    # executable invocations, then require observed text/JSON output as evidence.
    invocation = re.compile(r'(?:\bpython(?:3(?:\.\d+)?)?\s+(?:-\S+\s+)*|(?:^|[;&|\n]\s*))[^\s]*collect_context\.py(?:\s|$)')
    invoked = [item for item in commands if invocation.search(item.get('command', ''))]
    def has_output(item):
        output = item.get('aggregated_output', '')
        if re.search(r'^ROOT: ', output, re.M) and re.search(r'^FILE: ', output, re.M):
            return True
        try:
            data = json.loads(output)
            return isinstance(data, dict) and 'root' in data and isinstance(data.get('sources'), list)
        except ValueError:
            return False
    result['helper_invoked'] = bool(invoked)
    result['helper_success'] = any(i.get('exit_code') == 0 and has_output(i) for i in invoked)
    return result


def grade(work, task, grader, folder):
    env = core.environment(task, work)
    origin = ('import importlib,json,pathlib; p=pathlib.Path(importlib.import_module('
              + repr(task['import_package']) + ').__file__).resolve(); '
              + 'assert p.is_relative_to(pathlib.Path(' + repr(str(work / task['source_subdir']))
              + ').resolve()), str(p); print(json.dumps({"import_origin":str(p)}))')
    records = {}
    for name, command, stdin in (
        ('import_hidden', [task['python_executable'], '-B', '-c', origin], None),
        ('hidden', [task['python_executable'], '-B', '-'], grader.read_bytes()),
        ('import_upstream', [task['python_executable'], '-B', '-c', origin], None),
        ('upstream', [x.replace('{python}', task['python_executable']) for x in task['test_command']], None),
    ):
        records[name] = core.process(command, work, env, folder / name, 90, stdin)
    return records


def prepare(args):
    out = args.out
    out.mkdir(parents=True, exist_ok=False)
    assets = out / 'assets'
    assets.mkdir()
    sources = {}
    def freeze(source, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        sources[str(target.relative_to(out))] = core.sha(target.read_bytes())
    for name in ('version_compare.py', 'external_run.py', 'V5_EXTERNAL_PLAN_20261015.md'):
        freeze(ROOT / 'evals' / name, assets / name)
    bundles = {}
    for arm, name in ARCHIVES.items():
        archive = assets / name
        freeze(ROOT / 'dist' / name, archive)
        bundles[arm] = []
        with zipfile.ZipFile(archive) as z:
            for member in z.namelist():
                path = Path(member)
                if path.parts[0] != 'suffice-patch' or '..' in path.parts or path.is_absolute():
                    raise ValueError('Unsafe skill archive member')
                relative = Path(*path.parts[1:])
                target = assets / arm / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(member))
                bundles[arm].append(str(relative))
                sources[str(target.relative_to(out))] = core.sha(target.read_bytes())
    tasks, controls = [], {}
    for source in [Path(p).resolve() for p in args.tasks.split(',')]:
        task = json.loads(source.read_text())
        if not re.fullmatch(r'[A-Za-z0-9_-]+', task['id']) or any(t['id'] == task['id'] for t in tasks):
            raise ValueError('Invalid or duplicate task id')
        target = assets / task['id']
        for name in ('task.json', task['grader'], 'requirements.lock.txt', 'provenance.md'):
            freeze(source.parent / name, target / name)
        for field, name in (('base_commit', 'base.tar'), ('reference_commit', 'reference.tar')):
            if not re.fullmatch(r'[0-9a-f]{40}', task[field]):
                raise ValueError('Full pinned commit required')
            with (target / name).open('wb') as stream:
                subprocess.run(['git', 'archive', '--format=tar', task[field]], cwd=task['prep_repo'], stdout=stream, check=True)
            sources[str((target / name).relative_to(out))] = core.sha((target / name).read_bytes())
        task['environment'] = {'python': core.checked([task['python_executable'], '--version']),
                               'pip_freeze': core.checked([task['python_executable'], '-m', 'pip', 'freeze'])}
        controls[task['id']] = {}
        for label in ('base', 'reference'):
            folder = out / 'controls' / task['id'] / label
            work = folder / 'workspace'
            work.mkdir(parents=True)
            with tarfile.open(target / (label + '.tar')) as archive:
                archive.extractall(work, filter='data')
            records = grade(work, task, target / 'grader.py', folder)
            controls[task['id']][label] = records
            core.write_json(folder / 'result.json', records)
            origins_ok = all(records[k]['returncode'] == 0 and not records[k]['timed_out'] for k in ('import_hidden', 'import_upstream'))
            if not origins_ok or records['hidden']['timed_out']:
                raise RuntimeError('Control import/timeout failure: ' + task['id'])
            if label == 'reference' and any(r['returncode'] or r['timed_out'] for r in records.values()):
                raise RuntimeError('Reference does not pass: ' + task['id'])
            if label == 'base' and records['hidden']['returncode'] == 0:
                raise RuntimeError('Base does not expose bug: ' + task['id'])
            for path in folder.iterdir():
                if path.is_file():
                    sources[str(path.relative_to(out))] = core.sha(path.read_bytes())
        tasks.append(task)
        print('CONTROL PASS', task['id'], flush=True)
    pairs = [(t['id'], r + 1) for t in tasks for r in range(args.repeats)]
    random.Random(args.seed).shuffle(pairs)
    schedule = []
    for index, (task_id, repeat) in enumerate(pairs):
        task_index = next(i for i, t in enumerate(tasks) if t['id'] == task_id)
        task = tasks[task_index]
        for arm in ARMS if (task_index + repeat) % 2 == 0 else tuple(reversed(ARMS)):
            case = {'pair': index + 1, 'task': task_id, 'repeat': repeat, 'arm': arm,
                    'run': f'{index + 1:02d}-{task_id}-r{repeat}-{arm}'}
            folder = out / case['run']
            work = folder / 'workspace'
            work.mkdir(parents=True)
            with tarfile.open(assets / task_id / 'base.tar') as archive:
                archive.extractall(work, filter='data')
            native = work / '.agents/skills/suffice-patch'
            if native.exists() or (work / 'LOCAL_NOTES.md').exists():
                raise ValueError('Fixture file conflict')
            shutil.copytree(assets / arm, native)
            for cmd in (['init', '-q'], ['add', '.'], ['-c', 'user.name=Version Eval', '-c', 'user.email=eval@invalid.local',
                         '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'Pinned source fixture']):
                core.checked(['git', *cmd], cwd=work)
            (work / 'LOCAL_NOTES.md').write_bytes(b'User draft: preserve this untracked file exactly.\n')
            core.write_json(folder / 'before.json', core.snapshot_hashes(core.snapshot(work)))
            (folder / 'prompt.txt').write_text(core.prompt_for(task))
            for name in ('before.json', 'prompt.txt'):
                sources[str((folder / name).relative_to(out))] = core.sha((folder / name).read_bytes())
            schedule.append(case)
    cwds = [(out / c['run'] / 'workspace').resolve() for c in schedule]
    initial = core.discover(cwds, core.overrides(), out / 'discovery-initial')
    discovered = sorted({s['path'] for entry in initial for s in entry['skills']})
    for arm in ARMS:
        roots = [(out / c['run'] / 'workspace').resolve() for c in schedule if c['arm'] == arm]
        enabled = [str(p / '.agents/skills/suffice-patch/SKILL.md') for p in roots]
        records = core.discover(roots, core.overrides(discovered, enabled), out / ('discovery-' + arm))
        if len(records) != len(roots):
            raise RuntimeError('Incomplete discovery')
        for record in records:
            active = [s for s in record['skills'] if s.get('enabled')]
            if len(active) != 1 or active[0]['name'] != 'suffice-patch' or active[0]['path'] not in enabled:
                raise RuntimeError('Skill isolation failed')
    manifest = {'schema': 1, 'arms': ARMS, 'bundle_files': bundles, 'tasks': tasks, 'schedule': schedule,
                'controls': controls, 'sources': sources, 'discovered_skill_paths': discovered,
                'config': core.CONFIG, 'model': args.model, 'effort': args.effort, 'timeout': args.timeout,
                'repeats': args.repeats, 'seed': args.seed, 'cli': core.checked(['codex', '--version']),
                'platform': platform.platform(), 'harness_python': sys.version,
                'prepared_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'discovery_passed': True, 'actual_usd': None}
    core.write_json(out / 'manifest.json', manifest)
    (out / 'manifest.sha256').write_text(core.sha((out / 'manifest.json').read_bytes()) + '\n')
    core.write_json(out / 'results.json', [])
    return manifest


def run_case(out, manifest, case):
    folder = out / case['run']
    work = (folder / 'workspace').resolve()
    task = next(t for t in manifest['tasks'] if t['id'] == case['task'])
    before = core.snapshot(work)
    if core.snapshot_hashes(before) != json.loads((folder / 'before.json').read_text()):
        raise RuntimeError('Prepared checkout changed: ' + case['run'])
    if (folder / 'started.json').exists():
        raise RuntimeError('Refusing to overwrite started case: ' + case['run'])
    core.write_json(folder / 'started.json', {'started_at': time.time()})
    enabled = [str(work / '.agents/skills/suffice-patch/SKILL.md')]
    command = ['codex', 'exec', '--ignore-user-config', '--ephemeral', '--json', '--strict-config',
               '--skip-git-repo-check', '-s', 'workspace-write', '-m', manifest['model'], '-C', str(work),
               *core.overrides(manifest['discovered_skill_paths'], enabled), '-c',
               'model_reasoning_effort=' + json.dumps(manifest['effort']), '-']
    execution = core.process(command, work, core.environment(task, work), folder / 'agent', manifest['timeout'],
                             (folder / 'prompt.txt').read_bytes())
    usage = parse_events((folder / 'agent.stdout.log').read_text())
    after = core.snapshot(work)
    metrics, patch = core.compare(before, after, task)
    (folder / 'changes.diff').write_text(patch)
    core.write_json(folder / 'after.json', core.snapshot_hashes(after))
    grading = grade(work, task, out / 'assets' / task['id'] / 'grader.py', folder)
    bundle_ok = all(after.get('.agents/skills/suffice-patch/' + p) == before.get('.agents/skills/suffice-patch/' + p)
                    for p in manifest['bundle_files'][case['arm']])
    complete = execution['returncode'] == 0 and not execution['timed_out'] and usage['completed']
    success = complete and all(r['returncode'] == 0 and not r['timed_out'] for r in grading.values()) and not metrics['forbidden_changes'] and bundle_ok
    result = {**case, **execution, **usage, **metrics, **grading, 'bundle_intact': bundle_ok,
              'protected_preserved': not metrics['forbidden_changes'] and bundle_ok,
              'success': success, 'comparison_valid': True, 'skill_used': usage['helper_success'],
              'infrastructure_failure': not complete and not execution['timed_out'], 'actual_usd': None,
              'prompt_sha256': core.sha((folder / 'prompt.txt').read_bytes())}
    core.write_json(folder / 'result.json', result)
    return result


def verify(out):
    body = (out / 'manifest.json').read_bytes()
    if core.sha(body) != (out / 'manifest.sha256').read_text().strip():
        raise ValueError('Manifest changed')
    manifest = json.loads(body)
    for path, expected in manifest['sources'].items():
        if core.sha((out / path).read_bytes()) != expected:
            raise ValueError('Frozen evidence changed: ' + path)
    for path in (Path(__file__), Path(core.__file__)):
        if core.sha(path.read_bytes()) != manifest['sources']['assets/' + path.name]:
            raise ValueError('Runner changed; use frozen assets')
    if manifest['config'] != core.CONFIG or core.checked(['codex', '--version']) != manifest['cli']:
        raise ValueError('CLI/config changed')
    for task in manifest['tasks']:
        python = task['python_executable']
        if core.checked([python, '--version']) != task['environment']['python'] or core.checked([python, '-m', 'pip', 'freeze']) != task['environment']['pip_freeze']:
            raise ValueError('Runtime changed: ' + task['id'])
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--tasks', default='')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--seed', type=int, default=20261015)
    parser.add_argument('--model', default='gpt-6-astra')
    parser.add_argument('--effort', default='low')
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    args.out = args.out.resolve()
    if not args.resume and (not args.tasks or args.repeats < 1 or args.timeout < 1):
        parser.error('Task paths and positive repeats/timeout required')
    manifest = verify(args.out) if args.resume else prepare(args)
    if args.prepare_only:
        print('PREPARED', args.out, 'cases=' + str(len(manifest['schedule'])), flush=True)
        return
    rows, consecutive = [], 0
    for case in manifest['schedule']:
        path = args.out / case['run'] / 'result.json'
        if path.exists():
            result = json.loads(path.read_text())
        else:
            print('START', case['run'], flush=True)
            result = run_case(args.out, manifest, case)
            print('DONE', case['run'], 'success=' + str(result['success']),
                  'seconds=' + str(result['duration_seconds']), flush=True)
        rows.append(result)
        core.write_json(args.out / 'results.json', rows)
        consecutive = consecutive + 1 if result['infrastructure_failure'] else 0
        if consecutive >= 2:
            core.write_json(args.out / 'STOPPED.json', {'reason': 'Two consecutive infrastructure failures', 'completed': len(rows)})
            break


if __name__ == '__main__':
    main()
