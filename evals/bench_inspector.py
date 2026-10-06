#!/usr/bin/env python3
"""Compare two inspector versions on temporary fixtures; this is a local microbenchmark."""
import argparse
import hashlib
import json
import platform
import random
import re
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


SOURCE_HEADER = re.compile(r'^FILE: (.*?) \| .*? \| SHA256: ([0-9a-f]{64})$', re.MULTILINE)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def version(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        return result.stdout.splitlines()[0] if result.stdout else result.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as error:
        return type(error).__name__


def write(root, name, source):
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding='utf-8')


def fixture(root, kind, callers, seed):
    root.mkdir()
    rng = random.Random(seed)
    write(root, 'AGENTS.md', 'Preserve unrelated user changes. Use the existing public interface.\n')
    write(root, 'labels.py', 'def display_name(value):\n    return value.strip() or "Anonymous"\n')
    if kind == 'repeated_imports':
        write(root, 'api.py', 'import labels\n' * 2000 +
              '\ndef customer_label(value):\n    return labels.display_name(value)\n')
    else:
        write(root, 'api.py', 'from labels import display_name\n\n'
              'def customer_label(value):\n    return display_name(value)\n')
    write(root, 'test_api.py', 'from api import customer_label\n\n'
          'def test_customer_label():\n    assert customer_label(" Ada ") == "Ada"\n')
    write(root, 'web.py', 'from api import customer_label\n\n'
          'def render(value):\n    return "Hello, " + customer_label(value)\n')
    write(root, 'unrelated.py', 'UNRELATED_USER_VALUE = 10\n')
    if kind == 'many_callers':
        for index in range(callers):
            write(root, f'callers/caller_{index:05d}.py',
                  f'# fixture value {rng.randrange(1_000_000)}\n'
                  'from api import customer_label\n\n'
                  f'def render_{index}(value):\n    return customer_label(value)\n')
    commands = [('init', '-q'), ('add', '.'),
                ('-c', 'user.name=Benchmark', '-c', 'user.email=benchmark@invalid.local',
                 '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'fixture')]
    for command in commands:
        subprocess.run(['git', *command], cwd=root, check=True, capture_output=True)
    write(root, 'unrelated.py', 'UNRELATED_USER_VALUE = 11\n')
    write(root, 'labels.py', 'def display_name(value):\n    return value.strip() or "Guest"\n')
    return {
        'python_files': sum(1 for _ in root.rglob('*.py')),
        'tracked_fixture': True,
        'target': 'api.customer_label',
        'repeated_import_statements': 2000 if kind == 'repeated_imports' else 0,
        'textual_callers_created': callers if kind == 'many_callers' else 2,
    }


def run(script, root, arguments, timeout):
    start = time.perf_counter_ns()
    result = subprocess.run([sys.executable, '-B', str(script), '--root', str(root), *arguments],
                            cwd=root, capture_output=True, timeout=timeout)
    elapsed = time.perf_counter_ns() - start
    stdout = result.stdout.decode('utf-8', errors='replace')
    record = {
        'elapsed_ns': elapsed,
        'returncode': result.returncode,
        'stdout_bytes': len(result.stdout),
        'stdout_sha256': digest(result.stdout),
        'stderr': result.stderr.decode('utf-8', errors='replace'),
        'source_fingerprints': dict(SOURCE_HEADER.findall(stdout)),
    }
    return record, stdout


def summarize(records, label):
    measured = [record for record in records if record['phase'] == 'measured' and record['variant'] == label]
    elapsed = [record['elapsed_ns'] / 1e9 for record in measured]
    return {
        'median_seconds': statistics.median(elapsed),
        'min_seconds': min(elapsed),
        'max_seconds': max(elapsed),
        'stdout_bytes': sorted({record['stdout_bytes'] for record in measured}),
        'stdout_stable': len({record['stdout_sha256'] for record in measured}) == 1,
        'source_context_stable': all(record['source_fingerprints'] == measured[0]['source_fingerprints']
                                     for record in measured),
    }


def compare_output(before, after):
    reporting = lambda output: [line for line in output.splitlines() if 'caller/test search' in line.lower()]
    without_reporting = lambda output: '\n'.join(
        line for line in output.splitlines() if 'caller/test search' not in line.lower()).strip()
    if before == after:
        difference = 'identical stdout'
    elif without_reporting(before) == without_reporting(after):
        difference = 'caller-search reporting only; source and remaining output are identical'
    else:
        difference = 'other output differs; inspect source equivalence and output samples'
    return {
        'stdout_equivalent': before == after,
        'source_context_equivalent': SOURCE_HEADER.findall(before) == SOURCE_HEADER.findall(after),
        'difference': difference,
        'before_search_reporting': reporting(before),
        'after_search_reporting': reporting(after),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repetitions', type=int, default=7)
    parser.add_argument('--warmup', type=int, default=1)
    parser.add_argument('--callers', type=int, default=2000)
    parser.add_argument('--seed', type=int, default=20261006)
    parser.add_argument('--timeout', type=float, default=30)
    args = parser.parse_args()
    if args.repetitions < 1 or args.warmup < 0 or args.callers < 1 or args.timeout <= 0:
        parser.error('repetitions, callers and timeout must be positive; warmup must be nonnegative')
    report = {
        'benchmark': 'isolated inspector subprocess microbenchmark; not an agent or skill quality evaluation',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'environment': {'python': sys.version, 'executable': sys.executable,
                        'platform': platform.platform(), 'machine': platform.machine(),
                        'git': version(['git', '--version']), 'rg': version(['rg', '--version'])},
        'parameters': {'repetitions': args.repetitions, 'warmup': args.warmup,
                       'callers': args.callers, 'seed': args.seed, 'timeout_seconds': args.timeout},
        'method': 'Freeze script bytes, warm each variant, then alternate paired execution order; '
                  'include interpreter startup, search, and Git subprocesses. Fixtures share one root per case. '
                  'Use medians; preserve every sample. Filesystem cache is warm and not reset.',
        'scripts': {}, 'cases': [],
    }
    with tempfile.TemporaryDirectory(prefix='suffice-inspector-bench-') as temp:
        base = Path(temp)
        scripts = {}
        for label, original in [('before', args.before), ('after', args.after)]:
            raw = original.read_bytes()
            scripts[label] = base / f'{label}.py'
            scripts[label].write_bytes(raw)
            report['scripts'][label] = {'path': str(original.resolve()), 'sha256': digest(raw)}
        fixtures = {}
        for index, kind in enumerate(('small', 'repeated_imports', 'many_callers')):
            root = base / kind
            fixtures[kind] = (root, fixture(root, kind, args.callers, args.seed + index))
        for case_index, (name, kind, arguments) in enumerate([
            ('small', 'small', ['api.customer_label']),
            ('repeated_imports', 'repeated_imports', ['api.customer_label']),
            ('many_callers', 'many_callers', ['api.customer_label']),
            ('file_limit', 'many_callers', ['--max-files', '1', 'api.customer_label']),
        ]):
            root, description = fixtures[kind]
            records, samples = [], {}
            for phase, count in [('warmup', args.warmup), ('measured', args.repetitions)]:
                for pair in range(count):
                    order = ['before', 'after'] if (pair + case_index) % 2 == 0 else ['after', 'before']
                    for position, label in enumerate(order):
                        record, stdout = run(scripts[label], root, arguments, args.timeout)
                        record.update({'phase': phase, 'pair': pair, 'position': position, 'variant': label})
                        records.append(record)
                        samples[label] = stdout
            before, after = (summarize(records, label) for label in ('before', 'after'))
            case = {'name': name, 'fixture': description, 'arguments': arguments,
                    'before': before, 'after': after,
                    'median_time_reduction_percent': 100 * (1 - after['median_seconds'] / before['median_seconds']),
                    'comparison': compare_output(samples['before'], samples['after']),
                    'all_runs_succeeded': all(record['returncode'] == 0 for record in records),
                    'raw_runs': records}
            if not case['comparison']['stdout_equivalent']:
                case['output_samples'] = samples
            report['cases'].append(case)
            print(f"{name}: {before['median_seconds']:.4f}s -> {after['median_seconds']:.4f}s "
                  f"({case['median_time_reduction_percent']:+.1f}% time reduction); "
                  f"{case['comparison']['difference']}", flush=True)
    report['valid'] = all(case['all_runs_succeeded'] and case['comparison']['source_context_equivalent']
                          and case['before']['source_context_stable'] and case['after']['source_context_stable']
                          for case in report['cases'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Results: {args.output.resolve()}')
    return 0 if report['valid'] else 1


if __name__ == '__main__':
    sys.exit(main())
