#!/usr/bin/env python3
"""Compare a bundled inspector skill with the same agent and fixture without workflow injection."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import run as harness
from tasks import TASKS as OLD_TASKS
from v3_tasks import TASKS as NEW_TASKS
from v3_run import selftest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--skill-dir', type=Path, default=Path('candidates/v3-tools/suffice-patch'))
    parser.add_argument('--tasks', default=','.join(NEW_TASKS))
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--model', default='gpt-6-astra')
    parser.add_argument('--effort', default='low')
    parser.add_argument('--timeout', type=int, default=240)
    args = parser.parse_args()
    selftest()
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    args.skill_dir = args.skill_dir.resolve()
    tasks = {**OLD_TASKS, **NEW_TASKS}
    names = args.tasks.split(',')
    assert all(name in tasks for name in names)
    bundle = {str(p.relative_to(args.skill_dir)): p.read_bytes()
              for p in args.skill_dir.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    skill = bundle['SKILL.md'].decode()
    sources = [Path(__file__), Path(harness.__file__), Path(__file__).with_name('v3_tasks.py')]
    manifest = {'model': args.model, 'effort': args.effort, 'tasks': names, 'repeats': args.repeats,
                'skill': skill, 'common': harness.COMMON,
                'bundle_hashes': {name: hashlib.sha256(body).hexdigest() for name, body in bundle.items()},
                'note': 'Both arms receive identical hidden helper files; native discovery is off. Only suffice receives workflow and resolved skill-dir path.',
                'sources': [{'path': str(p.resolve()), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources]}
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    for path in sources:
        (args.out / path.name).write_bytes(path.read_bytes())
    shutil.copytree(args.skill_dir, args.out / 'skill')
    original_seed = harness.seed
    def seed_with_bundle(work, task):
        original_seed(work, task)
        for name, body in bundle.items():
            target = work / '.agents/skills/suffice-patch' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
    harness.seed = seed_with_bundle
    rows = []
    for repeat in range(args.repeats):
        for index, name in enumerate(names):
            task = tasks[name]
            if task.get('unchanged'):
                harness.TASKS['noop'] = task
            arms = ['baseline', 'suffice'] if (index + repeat) % 2 == 0 else ['suffice', 'baseline']
            for arm in arms:
                label = f'{repeat + 1}-{name}-{arm}'
                folder = args.out / label
                instruction = skill.replace('<skill-dir>', str(folder / 'workspace/.agents/skills/suffice-patch')) if arm == 'suffice' else ''
                print('START', label, flush=True)
                result = harness.run_one(folder, task, instruction, args)
                intact = all((folder / 'workspace/.agents/skills/suffice-patch' / file).read_bytes() == body for file, body in bundle.items())
                result['bundle_preserved'] = intact
                result['success'] = result['success'] and intact
                (folder / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
                rows.append({'run': label, 'task': name, 'arm': arm, **result})
                (args.out / 'results.json').write_text(json.dumps(rows, indent=2) + '\n')
                print('DONE', label, 'success=' + str(result['success']),
                      'tokens=' + str((result['input_tokens'] or 0) + (result['output_tokens'] or 0)),
                      'calls=' + str(result['tool_calls']), flush=True)


if __name__ == '__main__':
    main()
