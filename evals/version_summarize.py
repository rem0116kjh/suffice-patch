#!/usr/bin/env python3
"""Summarize all v4/v5 attempts, including failures and missing usage."""
import argparse
import json
from pathlib import Path
import random
import statistics

from external_summarize import measurements, geometric_mean, interval, METRICS

ARMS = ('v4', 'v5')


def summarize(manifest, rows):
    expected = {(t['id'], r + 1, a) for t in manifest['tasks'] for r in range(manifest['repeats']) for a in ARMS}
    keys = [(r['task'], r['repeat'], r['arm']) for r in rows]
    if len(set(keys)) != len(keys) or any(k not in expected for k in keys):
        raise ValueError('Duplicate or unplanned attempt')
    planned = {(r['task'], r['repeat'], r['arm']) for r in manifest['schedule']}
    if planned != expected or len(manifest['schedule']) != len(expected):
        raise ValueError('Invalid schedule')
    lookup = dict(zip(keys, rows))
    complete = set(keys) == expected
    def arms(selected):
        result = {}
        for arm in ARMS:
            runs = [r for r in selected if r['arm'] == arm]
            result[arm] = {'attempts': len(runs), 'successes': sum(r['success'] is True for r in runs),
                           'helper_successes': sum(r['helper_success'] is True for r in runs), 'metrics': {}}
            for metric in METRICS:
                values = [measurements(r)[metric] for r in runs]
                known = [v for v in values if v is not None]
                result[arm]['metrics'][metric] = {'observed': len(known), 'missing': len(values) - len(known),
                                                 'sum': sum(known) if known else None,
                                                 'median': statistics.median(known) if known else None,
                                                 'min': min(known) if known else None, 'max': max(known) if known else None}
        return result
    tasks = []
    for task in manifest['tasks']:
        entry = {'id': task['id'], 'arms': arms([r for r in rows if r['task'] == task['id']]), 'paired_ratios': {}}
        for metric in METRICS:
            ratios = []
            for repeat in range(1, manifest['repeats'] + 1):
                pair = [lookup.get((task['id'], repeat, a)) for a in ARMS]
                values = [measurements(r)[metric] if r else None for r in pair]
                ratios.append(values[1] / values[0] if all(v is not None for v in values) and values[0] > 0 else None)
            entry['paired_ratios'][metric] = {'values': ratios, 'median': statistics.median(ratios) if all(r is not None for r in ratios) else None}
        tasks.append(entry)
    totals = arms(rows)
    accuracy_ok = complete and all(t['arms']['v5']['successes'] >= t['arms']['v4']['successes'] for t in tasks)
    valid = complete and manifest.get('discovery_passed') is True and all(r.get('comparison_valid') is True for r in rows)
    effects = {}
    for metric in METRICS:
        values = [t['paired_ratios'][metric]['median'] for t in tasks]
        if not all(v is not None for v in values):
            effects[metric] = {'ratio': None, 'task_bootstrap_ci95': None}
            continue
        rng = random.Random(manifest['seed'])
        samples = [geometric_mean(rng.choices(values, k=len(values))) for _ in range(10000)]
        effects[metric] = {'ratio': geometric_mean(values), 'task_bootstrap_ci95': interval(samples)}
    gates = {}
    design = len(tasks) == 3 and manifest['repeats'] == 3
    for metric, threshold in (('total_tokens', .90), ('duration_seconds', .95)):
        effect = effects[metric]
        gates[metric] = bool(valid and accuracy_ok and design and effect['ratio'] is not None and
                             effect['ratio'] <= threshold and effect['task_bootstrap_ci95'][1] < 1)
    return {'complete': complete, 'comparison_valid': valid, 'accuracy_non_decreased': accuracy_ok,
            'planned': len(expected), 'recorded': len(rows), 'arms': totals, 'tasks': tasks,
            'effects_v5_over_v4': effects, 'efficiency_win_gates': gates, 'actual_usd': None,
            'limitations': ['Three known public Python bugs; no no-skill baseline.',
                            'Task bootstrap with only three projects is descriptive, not broad statistical evidence.',
                            'Caching and hosted model latency may differ across attempts; all usage is retained.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    summary = summarize(json.loads((args.run / 'manifest.json').read_text()), json.loads((args.run / 'results.json').read_text()))
    (args.run / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: summary[k] for k in ('complete', 'recorded', 'arms', 'effects_v5_over_v4', 'efficiency_win_gates')}, indent=2))


if __name__ == '__main__':
    main()
