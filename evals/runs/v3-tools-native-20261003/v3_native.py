#!/usr/bin/env python3
"""Compare actual native discovery/invocation with a disabled-skill baseline."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

import run as harness
from v3_tasks import TASKS


def run_case(folder, arm, task, skill, bundle, args):
    work = folder / 'workspace'
    work.mkdir(parents=True)
    harness.seed(work, task)
    native = work / '.agents/skills/suffice-patch/SKILL.md'
    for name, body in bundle.items():
        target = native.parent / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    for git_args in [['init', '-q'], ['add', '.'],
                     ['-c', 'user.name=Eval Fixture', '-c', 'user.email=eval@invalid.local',
                      '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'fixture']]:
        subprocess.run(['git', *git_args], cwd=work, check=True, capture_output=True)
    before = harness.snapshot(work)
    prefix = '$suffice-patch ' if arm == 'explicit' else ''
    prompt = prefix + task['prompt'] + '\n\n' + harness.COMMON
    (folder / 'prompt.txt').write_text(prompt)
    command = ['codex', 'exec', '--ignore-user-config', '--ephemeral', '--json',
               '--strict-config', '--skip-git-repo-check', '-s', 'workspace-write',
               '-m', args.model, '-C', str(work)]
    config = {'model_reasoning_effort': args.effort, 'approval_policy': 'never',
              'web_search': 'disabled', 'project_doc_max_bytes': 0,
              'suppress_unstable_features_warning': True,
              'features.skip_host_skill_discovery': False, 'features.plugins': False,
              'features.hooks': False, 'features.apps': False,
              'features.memories': False, 'features.multi_agent': False}
    for key, value in config.items():
        command += ['-c', key + '=' + json.dumps(value)]
    host = str(Path.home() / '.agents/skills/suffice-patch/SKILL.md')
    enabled = 'false' if arm == 'baseline' else 'true'
    overrides = ('skills.config=[{path=' + json.dumps(host) + ',enabled=false},'
                 '{path=' + json.dumps(str(native)) + ',enabled=' + enabled + '}]')
    command += ['-c', overrides, '-']
    started = time.monotonic()
    with (folder / 'events.jsonl').open('w') as out, (folder / 'stderr.log').open('w') as err:
        proc = subprocess.Popen(command, cwd=work, stdin=subprocess.PIPE,
                                stdout=out, stderr=err, text=True, start_new_session=True)
        timed_out = False
        try:
            proc.communicate(prompt, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
    duration = time.monotonic() - started
    after = harness.snapshot(work)
    metrics, diff = harness.diff_metrics(before, after)
    (folder / 'changes.diff').write_text(diff)
    usage = harness.parse_events((folder / 'events.jsonl').read_text())
    checks = harness.grade(work, task)
    preserved = all(after.get(f) == body for f, body in harness.DISTRACTORS.items())
    skill_preserved = all((native.parent / name).read_bytes() == body for name, body in bundle.items())
    success = (proc.returncode == 0 and not timed_out and usage['completed']
               and all(c['passed'] for c in checks) and preserved and skill_preserved)
    result = {'arm': arm, **usage, **metrics, 'checks': checks,
              'duration_seconds': round(duration, 3), 'returncode': proc.returncode,
              'timed_out': timed_out, 'success': success,
              'unrelated_preserved': preserved, 'skill_preserved': skill_preserved,
              'skill_path': str(native), 'skill_body_injected_by_harness': False,
              'prompt_sha256': harness.digest(prompt), 'command': command}
    (folder / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--skill', required=True, type=Path)
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--model', default='gpt-6-astra')
    parser.add_argument('--effort', default='low')
    parser.add_argument('--timeout', type=int, default=240)
    args = parser.parse_args()
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    skill = args.skill.read_text()
    bundle = {str(p.relative_to(args.skill.parent)): p.read_bytes()
              for p in args.skill.parent.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    sources = [Path(__file__), Path(harness.__file__), Path(__file__).with_name('v3_tasks.py'), args.skill]
    manifest = {'model': args.model, 'effort': args.effort, 'repeats': args.repeats,
                'task': 'invoice', 'arms': ['baseline', 'explicit', 'implicit'],
                'bundle_hashes': {name: hashlib.sha256(body).hexdigest() for name, body in bundle.items()},
                'sources': [{'path': str(p.resolve()), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                            for p in sources],
                'note': 'Native repo skill, host copy disabled per invocation. User installation unchanged.'}
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    for path in sources:
        (args.out / path.name).write_bytes(path.read_bytes())
    rows = []
    for repeat in range(args.repeats):
        arms = ['baseline', 'explicit', 'implicit']
        arms = arms[repeat % 3:] + arms[:repeat % 3]
        for arm in arms:
            label = f'{repeat + 1}-invoice-{arm}'
            print('START', label, flush=True)
            result = run_case(args.out / label, arm, TASKS['invoice'], skill, bundle, args)
            rows.append({'run': label, 'task': 'invoice', **result})
            (args.out / 'results.json').write_text(json.dumps(rows, indent=2) + '\n')
            print('DONE', label, 'success=' + str(result['success']),
                  'tokens=' + str((result['input_tokens'] or 0) + (result['output_tokens'] or 0)),
                  'calls=' + str(result['tool_calls']), flush=True)


if __name__ == '__main__':
    main()
