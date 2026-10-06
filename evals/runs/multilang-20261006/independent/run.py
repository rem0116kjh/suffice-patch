#!/usr/bin/env python3
"""Independent API checks; never modify the candidate fixture or run an LLM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import time

HERE = Path(__file__).resolve().parent
ALLOWED = {
    'apps/storefront/src/quote.js',
    'services/order-go/quote/quote.go',
    'native/order-c/src/quote.c',
    'services/order-java/src/example/order/QuoteService.java',
}
IGNORED = {'.git', '__pycache__', '.pytest_cache', '.cache', 'node_modules', 'target'}


def sha(body):
    return hashlib.sha256(body).hexdigest()


def snapshot(root):
    result = {}
    for folder, directories, files in os.walk(root, followlinks=False):
        directories[:] = sorted(name for name in directories if name not in IGNORED)
        for name in files + [name for name in directories if (Path(folder) / name).is_symlink()]:
            path = Path(folder) / name
            result[path.relative_to(root).as_posix()] = ('SYMLINK:' + os.readlink(path)) if path.is_symlink() else sha(path.read_bytes())
    return result


def allowed_new_test(name):
    return ((name.startswith('apps/storefront/test/') and name.endswith(('.js', '.ts', '.mjs')))
            or (name.startswith('services/order-go/quote/') and name.endswith('_test.go'))
            or (name.startswith('native/order-c/tests/') and name.endswith('.c'))
            or (name.startswith('services/order-java/tests/') and name.endswith('.java')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path)
    parser.add_argument('--out', type=Path, required=True, help='New evidence/build directory outside fixture')
    args = parser.parse_args()
    verification_path = HERE.parent / 'verification.json'
    archive_path = HERE.parent / 'fixture-before.tar'
    verification = json.loads(verification_path.read_text())
    fixture = (args.fixture or Path(verification['fixture'])).resolve()
    out = args.out.resolve()
    if out.exists() or out.is_relative_to(fixture):
        parser.error('--out must be a new directory outside the fixture')
    out.mkdir(parents=True)
    before = verification['fixture_before']
    current_before = snapshot(fixture)
    changed = sorted(name for name in before.keys() | current_before.keys() if before.get(name) != current_before.get(name))
    forbidden = [name for name in changed if name not in ALLOWED and not (name not in before and allowed_new_test(name) and not current_before[name].startswith('SYMLINK:'))]
    archive_hashes = {}
    with tarfile.open(archive_path) as archive:
        for member in archive:
            if member.isfile():
                archive_hashes[member.name] = sha(archive.extractfile(member).read())
    tools = {name: shutil.which(name) for name in ['node', 'go', 'clang', 'java', 'javac']}
    missing = [name for name, path in tools.items() if not path]
    if missing:
        raise RuntimeError('Required already-installed native tool missing: ' + ', '.join(missing))
    report = {
        'scope': 'Synthetic functional forward test; no efficiency or public-project benchmark claim',
        'fixture': str(fixture), 'platform': platform.platform(), 'started_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'additional_model_calls': 0, 'network_installations': 0,
        'verification_sha256': sha(verification_path.read_bytes()), 'archive_sha256': sha(archive_path.read_bytes()),
        'grader_source_sha256': {path.name: sha(path.read_bytes()) for path in sorted(HERE.iterdir()) if path.is_file() and path.suffix in {'.py', '.go', '.mjs', '.java', '.c'}},
        'archive_matches_frozen_hashes': archive_hashes == before,
        'allowed_existing_source_paths': sorted(ALLOWED), 'modified_paths': changed, 'forbidden_changes': forbidden,
        'added_tests': sorted(name for name in current_before.keys() - before.keys() if allowed_new_test(name)),
        'protected_files_unchanged': not forbidden, 'rust_unchanged': all(current_before.get(name) == digest for name, digest in before.items() if name.startswith('crates/order-rs/')),
        'typescript_static_typecheck': 'not run: tsc unavailable; Node native type-stripping runtime checks only',
        'rust_runtime': 'not run: rustc/cargo unavailable', 'tools': tools, 'commands': [], 'success': False,
    }
    env = dict(os.environ, GOPROXY='off', GOSUMDB='off', GOTOOLCHAIN='local', CGO_ENABLED='0',
               GOCACHE=str(out / 'go-cache'), GOMODCACHE=str(out / 'go-module-cache'), PYTHONDONTWRITEBYTECODE='1')

    def run(name, command, cwd, expect_json=False):
        start = time.monotonic()
        result = subprocess.run([str(value) for value in command], cwd=cwd, env=env, capture_output=True, text=True, timeout=180)
        row = {'name': name, 'command': [str(value) for value in command], 'cwd': str(cwd), 'returncode': result.returncode,
               'seconds': round(time.monotonic() - start, 3), 'stdout': result.stdout, 'stderr': result.stderr}
        if expect_json:
            try:
                row['checks'] = json.loads(result.stdout)
            except ValueError:
                row['checks'] = None
        path = out / (name + '.json')
        path.write_text(json.dumps(row, indent=2) + '\n')
        report['commands'].append({'name': name, 'returncode': result.returncode, 'seconds': row['seconds'], 'log_path': str(path), 'log_sha256': sha(path.read_bytes())})
        return row

    def suite(source, label, existing):
        build = out / (label + '-build')
        build.mkdir()
        rows = []
        if existing:
            rows.append(run(label + '-existing-js-ts', [tools['node'], '--test', 'apps/storefront/test/quote.test.js', 'packages/money/test/amount.test.ts'], source))
            rows.append(run(label + '-existing-go', [tools['go'], 'test', '-v', './...'], source / 'services/order-go'))
        rows.append(run(label + '-hidden-js-ts', [tools['node'], HERE / 'check_js.mjs', source], source, True))
        rows.append(run(label + '-hidden-go', [tools['go'], 'run', HERE / 'check_go.go'], source / 'services/order-go', True))
        c_sources = [source / 'native/order-c/src/money.c', source / 'native/order-c/src/quote.c']
        c_compile = run(label + '-compile-c', [tools['clang'], '-std=c17', '-Wall', '-Wextra', '-Werror', '-I', source / 'native/order-c/include', *c_sources, HERE / 'check_c.c', '-o', build / 'check_c'], source)
        rows.append(c_compile)
        if c_compile['returncode'] == 0:
            rows.append(run(label + '-hidden-c', [build / 'check_c'], source, True))
        if existing:
            compiled = run(label + '-compile-existing-c', [tools['clang'], '-std=c17', '-Wall', '-Wextra', '-Werror', *c_sources, source / 'native/order-c/tests/test_quote.c', '-o', build / 'existing_c'], source)
            rows.append(compiled)
            if compiled['returncode'] == 0:
                rows.append(run(label + '-existing-c', [build / 'existing_c'], source))
        java_build = build / 'java'
        java_build.mkdir()
        java_sources = sorted((source / 'services/order-java/src').rglob('*.java'))
        if existing:
            java_sources += sorted((source / 'services/order-java/tests').rglob('*.java'))
        java_compile = run(label + '-compile-java', [tools['javac'], '-d', java_build, *java_sources, HERE / 'IndependentQuoteCheck.java'], source)
        rows.append(java_compile)
        if java_compile['returncode'] == 0:
            rows.append(run(label + '-hidden-java', [tools['java'], '-ea', '-cp', java_build, 'IndependentQuoteCheck'], source, True))
            if existing:
                rows.append(run(label + '-existing-java', [tools['java'], '-ea', '-cp', java_build, 'example.order.QuoteTests'], source))
        return rows

    try:
        if archive_hashes != before:
            raise RuntimeError('Frozen baseline archive and hashes disagree')
        control = out / 'unchanged-baseline'
        control.mkdir()
        with tarfile.open(archive_path) as archive:
            archive.extractall(control, filter='data')
        control_rows = suite(control, 'negative-control', False)
        candidate_rows = suite(fixture, 'candidate', True)
        hidden = [row for row in candidate_rows if '-hidden-' in row['name']]
        negative = [row for row in control_rows if '-hidden-' in row['name']]
        report['candidate_hidden'] = {row['name']: row.get('checks') for row in hidden}
        report['negative_control_hidden'] = {row['name']: row.get('checks') for row in negative}
        report['negative_control_detected_missing_feature'] = len(negative) == 4 and all(row['returncode'] != 0 and row.get('checks') and row['checks'].get('failed', 0) > 0 for row in negative)
        report['candidate_runtime_passed'] = len(hidden) == 4 and all(row['returncode'] == 0 for row in candidate_rows) and all(row.get('checks') and row['checks']['passed'] == row['checks']['total'] > 0 for row in hidden)
        report['fixture_unchanged_by_grader'] = snapshot(fixture) == current_before
        report['success'] = bool(report['candidate_runtime_passed'] and report['negative_control_detected_missing_feature'] and report['fixture_unchanged_by_grader'] and report['protected_files_unchanged'] and report['rust_unchanged'])
    finally:
        report['finished_at_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        (out / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ['success', 'modified_paths', 'forbidden_changes', 'candidate_runtime_passed', 'negative_control_detected_missing_feature', 'fixture_unchanged_by_grader', 'rust_unchanged']}, indent=2))
    raise SystemExit(not report['success'])


if __name__ == '__main__':
    main()
