#!/usr/bin/env python3
"""Paired v3 evaluation using the original execution and independent grading code."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

import run as harness
from v3_tasks import TASKS


def selftest():
    for name, task in TASKS.items():
        with tempfile.TemporaryDirectory(prefix='suffice-v3-grader-') as directory:
            work = Path(directory)
            harness.seed(work, task)
            before = harness.grade(work, task)
            assert all(c['passed'] for c in before) == bool(task.get('unchanged')), (name, before)
            for file, body in task['good'].items():
                (work / file).write_text(body)
            good = harness.grade(work, task)
            assert all(c['passed'] for c in good), (name, good)
            target = next(iter(task['files']))
            (work / target).write_text('')
            assert not all(c['passed'] for c in harness.grade(work, task)), name
    print('PASS: 4 new graders accept known-good, reject defective/empty code.', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--skill', type=Path, default=Path('candidates/v3/suffice-patch/SKILL.md'))
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--model', default='gpt-6-astra')
    parser.add_argument('--effort', default='low')
    parser.add_argument('--timeout', type=int, default=240)
    args = parser.parse_args()
    selftest()
    if args.selftest:
        return
    if not args.out:
        parser.error('--out is required')
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    workflow = args.skill.read_text()
    sources = [Path(__file__), Path(__file__).with_name('v3_tasks.py'), Path(harness.__file__), args.skill]
    manifest = {'cli': subprocess.check_output(['codex', '--version'], text=True).strip(),
                'model': args.model, 'effort': args.effort, 'timeout': args.timeout,
                'repeats': args.repeats, 'tasks': list(TASKS), 'workflows': {'baseline': '', 'suffice': workflow},
                'sources': [{'path': str(p.resolve()), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                            for p in sources],
                'common': harness.COMMON,
                'note': 'Native discovery off for both arms. Token costs are not billed dollars.'}
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    for p in sources:
        (args.out / p.name).write_bytes(p.read_bytes())
    rows = []
    for repeat in range(args.repeats):
        for index, (name, task) in enumerate(TASKS.items()):
            arms = ['baseline', 'suffice'] if (index + repeat) % 2 == 0 else ['suffice', 'baseline']
            for arm in arms:
                label = f'{repeat + 1}-{name}-{arm}'
                print('START', label, flush=True)
                # Preserve the original harness's no-op detection by identity.
                if task.get('unchanged'):
                    harness.TASKS['noop'] = task
                row = {'run': label, 'task': name, 'arm': arm,
                       **harness.run_one(args.out / label, task, workflow if arm == 'suffice' else '', args)}
                rows.append(row)
                (args.out / 'results.json').write_text(json.dumps(rows, indent=2) + '\n')
                print('DONE', label, 'success=' + str(row['success']),
                      'tokens=' + str((row['input_tokens'] or 0) + (row['output_tokens'] or 0)),
                      'calls=' + str(row['tool_calls']), flush=True)


if __name__ == '__main__':
    main()
