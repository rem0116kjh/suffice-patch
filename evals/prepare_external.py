#!/usr/bin/env python3
"""Prepare public evaluation tasks without models or global installs.

Use Python 3.12 because these historical repositories were validated on it.
Separate repository venvs preserve each task's conflicting pinned dependencies.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ['dotenv/task.json', 'packaging/task.json', 'itsdangerous/task.json', 'itsdangerous/noop.json']


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path, help='New or empty output directory')
    parser.add_argument('--python', default='python3.12', help='Python 3.12 executable for isolated venvs')
    parser.add_argument('--tasks', help='Comma-separated task JSON paths; defaults to the four frozen tasks')
    parser.add_argument('--dry-run', action='store_true', help='Print the setup plan without running commands or writing files')
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        parser.error('--out must be new or empty; existing contents will never be overwritten')
    python = shutil.which(args.python)
    if not python:
        parser.error('Python 3.12 executable not found: ' + args.python)
    paths = [Path(p).resolve() for p in args.tasks.split(',')] if args.tasks else [ROOT / 'evals/external_tasks' / p for p in DEFAULTS]
    tasks, groups, ids, requirements = [], {}, set(), {}
    for source in paths:
        task = json.loads(source.read_text())
        ident, url = task['id'], task['repo_url']
        if not re.fullmatch(r'[A-Za-z0-9_-]+', ident) or ident in ids:
            parser.error('Task IDs must be unique safe directory names: ' + ident)
        ids.add(ident)
        if not url.startswith('https://') or any(not re.fullmatch(r'[0-9a-f]{40}', task[k]) for k in ['base_commit', 'reference_commit']):
            parser.error('Tasks require a public HTTPS repository and full pinned commit hashes')
        grader = Path(task['grader'])
        if grader.name != task['grader'] or not (source.parent / grader).is_file():
            parser.error('Task grader must name an existing adjacent file: ' + str(source))
        group = groups.setdefault(url, {'tasks': [], 'dependencies': {}, 'fully_locked': True})
        lock = source.parent / 'requirements.lock.txt'
        group['fully_locked'] = group['fully_locked'] and lock.is_file()
        pins = task['dependencies']
        if lock.is_file():
            body = lock.read_bytes()
            pins = [line.strip() for line in body.decode().splitlines() if line.strip() and not line.lstrip().startswith('#')]
            if not set(task['dependencies']).issubset(pins):
                parser.error('Runtime lock must preserve every exact direct dependency pin: ' + str(lock))
            requirements[str(lock)] = {'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body), 'packages': len(pins)}
        for dependency in pins:
            if not re.fullmatch(r'[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+', dependency):
                parser.error('Only exact pinned package dependencies are supported: ' + dependency)
            name = re.sub(r'[-_.]+', '-', dependency.split('==')[0]).lower()
            if name in group['dependencies'] and group['dependencies'][name] != dependency:
                parser.error('Conflicting dependency pins in the same repository: ' + name)
            group['dependencies'][name] = dependency
        entry = {'source': source, 'task': task}
        group['tasks'].append(entry)
        tasks.append(entry)
    actions = [{'name': 'python-version', 'command': [python, '-c', 'import platform, sys; print(platform.python_version()); assert sys.version_info[:2] == (3, 12), "Python 3.12 is required"']}]
    for url, group in groups.items():
        key = url.rstrip('/').split('/')[-1].removesuffix('.git') + '-' + hashlib.sha256(url.encode()).hexdigest()[:8]
        repo, venv = out / 'repos' / key, out / 'venvs' / key
        interpreter = venv / 'bin/python'
        group.update(repo=repo, python=interpreter, key=key)
        commands = [['git', '-c', 'core.hooksPath=/dev/null', 'clone', '--filter=blob:none', '--no-checkout', '--', url, str(repo)]]
        commits = sorted({entry['task'][field] for entry in group['tasks'] for field in ['base_commit', 'reference_commit']})
        commands += [['git', '-C', str(repo), 'fetch', '--no-tags', 'origin', commit] for commit in commits]
        installs = [entry['task'] for entry in group['tasks'] if entry['task'].get('install_package')]
        install = next((task for task in installs if not task.get('expected_noop')), installs[0] if installs else None)
        if len({task['base_commit'] for task in installs if not task.get('expected_noop')}) > 1:
            parser.error('Multiple package-install bases in one repository need separate preparations')
        if install:
            commands.append(['git', '-C', str(repo), '-c', 'core.hooksPath=/dev/null', 'checkout', '--detach', install['base_commit']])
        dependency_flags = ['--no-deps'] if group['fully_locked'] else []
        commands += [[python, '-m', 'venv', str(venv)], [str(interpreter), '-m', 'pip', 'install', '--disable-pip-version-check', *dependency_flags, *group['dependencies'].values()]]
        if install:
            commands.append([str(interpreter), '-m', 'pip', 'install', '--disable-pip-version-check', '--no-deps', str(repo)])
        commands += [[str(interpreter), '--version'], [str(interpreter), '-m', 'pip', 'freeze']]
        actions += [{'name': key + '-' + str(index), 'repository': url, 'command': command} for index, command in enumerate(commands)]
    emitted = [str(out / 'tasks' / entry['task']['id'] / 'task.json') for entry in tasks]
    plan = {'output': str(out), 'task_sources': [str(p) for p in paths], 'requirements': requirements, 'emitted_tasks': emitted, 'actions': actions,
            'next_command': ['python3', '-B', str(ROOT / 'evals/external_run.py'), '--out', str(out / 'evaluation'), '--tasks', ','.join(emitted), '--prepare-only'],
            'note': 'Preparation performs no model calls. Preserve task order and freeze before trials. macOS-specific exclusions remain exactly as declared in each task.'}
    if args.dry_run:
        print(json.dumps(plan, indent=2))
        return
    out.mkdir(parents=True, exist_ok=True)
    for directory in ['repos', 'venvs', 'tasks', 'logs']:
        (out / directory).mkdir()
    write_json(out / 'plan.json', plan)
    evidence = {'completed': False, 'commands': [], 'inputs': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, 'requirements': requirements}
    env = os.environ.copy()
    for name in ['PYTHONPATH', 'PYTHONHOME', 'PYTHONOPTIMIZE']:
        env.pop(name, None)
    env.update(PYTHONNOUSERSITE='1', PIP_DISABLE_PIP_VERSION_CHECK='1', PYTHONDONTWRITEBYTECODE='1')
    try:
        for action in actions:
            result = subprocess.run(action['command'], cwd=out, env=env, capture_output=True, text=True, timeout=600)
            record = {**action, 'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
            evidence['commands'].append(record)
            write_json(out / 'logs' / (action['name'] + '.json'), record)
            write_json(out / 'setup.json', evidence)
            if result.returncode:
                raise RuntimeError('Preparation failed; see ' + str(out / 'logs' / (action['name'] + '.json')))
        for entry, destination in zip(tasks, emitted):
            source, task = entry['source'], dict(entry['task'])
            group = groups[task['repo_url']]
            task.update(prep_repo=str(group['repo']), python_executable=str(group['python']))
            target = Path(destination)
            target.parent.mkdir()
            for name in [task['grader'], 'provenance.md', 'requirements.lock.txt']:
                asset = source.parent / name
                if asset.is_file():
                    shutil.copyfile(asset, target.parent / name)
            write_json(target, task)
        evidence['completed'] = True
        evidence['emitted_tasks'] = emitted
        evidence['next_command'] = plan['next_command']
    finally:
        write_json(out / 'setup.json', evidence)
    print(json.dumps({'task_paths': emitted, 'next_command': plan['next_command'], 'setup_evidence': str(out / 'setup.json')}, indent=2))


if __name__ == '__main__':
    main()
