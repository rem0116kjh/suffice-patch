#!/usr/bin/env python3
"""Independently check frozen inputs, arm isolation, raw usage, and final files."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys


def audit(out):
    # Audit with the exact runner that generated these records, even after the
    # repository's current evaluator has received subsequent maintenance fixes.
    for name in ('external_run', 'version_compare'):
        spec = importlib.util.spec_from_file_location(name, out / 'assets' / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    runner = sys.modules['version_compare']
    manifest = runner.verify(out)
    results = json.loads((out / 'results.json').read_text())
    by_run = {r['run']: r for r in results}
    if len(by_run) != len(results):
        raise ValueError('Duplicate run')
    checks = []
    prompt_hashes, starts = {}, {}
    for case in manifest['schedule']:
        folder = out / case['run']
        prompt_hashes.setdefault(case['task'], set()).add(runner.core.sha((folder / 'prompt.txt').read_bytes()))
        before = json.loads((folder / 'before.json').read_text())
        project = {p: value for p, value in before.items() if not p.startswith('.agents/skills/suffice-patch/')}
        starts.setdefault(case['task'], []).append(project)
        if case['run'] not in by_run:
            continue
        result = by_run[case['run']]
        raw_result = json.loads((folder / 'result.json').read_text())
        if result != raw_result:
            raise ValueError('Aggregate differs from per-run result')
        usage = runner.parse_events((folder / 'agent.stdout.log').read_text())
        if any(result[k] != v for k, v in usage.items()):
            raise ValueError('Usage differs from raw events')
        after = json.loads((folder / 'after.json').read_text())
        actual = runner.core.snapshot_hashes(runner.core.snapshot(folder / 'workspace'))
        if actual != after:
            raise ValueError('Final files changed after grading')
        command = json.loads((folder / 'agent.command.json').read_text())
        native = str(folder / 'workspace/.agents/skills/suffice-patch/SKILL.md')
        config = next(v for v in command if v.startswith('skills.config='))
        # JSON is not TOML here, so inspect each encoded path's explicit flag.
        enabled = '{path=' + json.dumps(native) + ',enabled=true}'
        isolated = enabled in config and config.count('enabled=true') == 1
        correct_model = command[command.index('-m') + 1] == manifest['model']
        correct_effort = 'model_reasoning_effort=' + json.dumps(manifest['effort']) in command
        bundle = manifest['bundle_files'][case['arm']]
        intact = all(after['.agents/skills/suffice-patch/' + p] == before['.agents/skills/suffice-patch/' + p] for p in bundle)
        success = (result['returncode'] == 0 and not result['timed_out'] and usage['completed'] and
                   all(result[k]['returncode'] == 0 and not result[k]['timed_out'] for k in ('hidden', 'upstream', 'import_hidden', 'import_upstream'))
                   and not result['forbidden_changes'] and intact)
        if success != result['success']:
            raise ValueError('Success disagrees with grading evidence')
        checks.append({'run': case['run'], 'one_assigned_skill_enabled': isolated,
                       'model_and_effort_match': correct_model and correct_effort,
                       'bundle_preserved': intact, 'raw_usage_matches': True,
                       'final_files_match': True, 'grading_status_matches': True})
    prompts_equal = all(len(hashes) == 1 for hashes in prompt_hashes.values())
    initial_equal = all(all(p == projects[0] for p in projects) for projects in starts.values())
    result = {'completed': len(results), 'planned': len(manifest['schedule']),
              'manifest_and_frozen_sources_verified': True, 'same_prompt_per_project': prompts_equal,
              'same_initial_project_files': initial_equal, 'checks': checks,
              'passed': len(results) == len(manifest['schedule']) and prompts_equal and initial_equal
                        and all(all(v is True for k, v in c.items() if k != 'run') for c in checks)}
    runner.core.write_json(out / 'audit.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    args = parser.parse_args()
    result = audit(args.out.resolve())
    print(json.dumps({k: v for k, v in result.items() if k != 'checks'}, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
