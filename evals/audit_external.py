#!/usr/bin/env python3
"""Audit frozen external-evaluation evidence without running agents or tests."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tarfile
import time

CACHES = {'.git', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache'}
USAGE = ['input_tokens', 'cached_input_tokens', 'cache_write_input_tokens', 'output_tokens', 'reasoning_output_tokens']
BUNDLE = ['SKILL.md', 'scripts/collect_context.py']


def sha(body):
    return hashlib.sha256(body).hexdigest()


def entry(body, mode=0o644, kind='file'):
    return {'kind': kind, 'mode': mode, 'sha256': sha(body)}


def snapshot(root):
    result, bodies = {}, {}
    for folder, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in CACHES)
        for name in files + [d for d in dirs if (Path(folder) / d).is_symlink()]:
            path = Path(folder) / name
            link = path.is_symlink()
            body = os.fsencode(os.readlink(path)) if link else path.read_bytes()
            key = path.relative_to(root).as_posix()
            result[key], bodies[key] = entry(body, stat.S_IMODE(path.lstat().st_mode), 'link' if link else 'file'), body
    return result, bodies


def prepared(run, task, platform):
    result, bodies = {}, {}
    with tarfile.open(run / 'assets' / task['id'] / 'base.tar') as archive:
        for member in archive:
            if member.isdir():
                continue
            body = os.fsencode(member.linkname) if member.issym() else archive.extractfile(member).read()
            # macOS applies the preparation's standard 022 umask to new symlinks.
            mode = (0o755 if platform.startswith('macOS') else 0o777) if member.issym() else member.mode & 0o755
            result[member.name] = entry(body, mode, 'link' if member.issym() else 'file')
            bodies[member.name] = body
    for name in BUNDLE:
        path = '.agents/skills/suffice-patch/' + name
        bodies[path] = (run / 'assets/skill' / name).read_bytes()
        result[path] = entry(bodies[path])
    bodies['LOCAL_NOTES.md'] = b'User draft: preserve this untracked file exactly.\n'
    result['LOCAL_NOTES.md'] = entry(bodies['LOCAL_NOTES.md'])
    return result, bodies


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    run = args.run.resolve()
    audit = {'audited_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'mismatches': [], 'pending': [], 'files': {}, 'cases': [],
             'limitations': ['No agents, tests, network calls, or runner helper imports were executed.', 'Process exit codes and timeouts have no separate independent process record; consistency and stdout evidence are audited, not re-executed.', 'Snapshot cache exclusions match the frozen runner; in-progress workspace changes are not judged.']}
    def issue(scope, detail, actual=None, expected=None):
        audit['mismatches'].append({'scope': scope, 'detail': detail, 'actual': actual, 'expected': expected})
    def equal(scope, actual, expected):
        if actual != expected:
            if isinstance(actual, bytes):
                actual = {'bytes': len(actual), 'sha256': sha(actual)}
            if isinstance(expected, bytes):
                expected = {'bytes': len(expected), 'sha256': sha(expected)}
            issue(scope, 'values differ', actual, expected)
    def read(path):
        body = path.read_bytes()
        audit['files'][str(path.relative_to(run))] = {'sha256': sha(body), 'bytes': len(body)}
        return body
    def load(path):
        return json.loads(read(path))
    def maps(scope, actual, expected):
        differences = sorted(k for k in actual.keys() | expected.keys() if actual.get(k) != expected.get(k))
        if differences:
            issue(scope, 'snapshot entries differ', differences)
    manifest_body = read(run / 'manifest.json')
    manifest = json.loads(manifest_body)
    equal('manifest.sha256', sha(manifest_body), read(run / 'manifest.sha256').decode().strip())
    for relative, expected in manifest['sources'].items():
        path = run / relative
        if not path.is_file():
            issue(relative, 'frozen source missing')
        else:
            equal(relative, sha(read(path)), expected)
    schedule = manifest['schedule']
    tasks = {task['id']: task for task in manifest['tasks']}
    cases = {case['run']: case for case in schedule}
    equal('schedule duplicate run IDs', len(cases), len(schedule))
    equal('schedule size', len(schedule), len(tasks) * manifest['repeats'] * 2)
    equal('schedule duplicate task/repeat/arm', len({(c['task'], c['repeat'], c['arm']) for c in schedule}), len(schedule))
    for task in tasks.values():
        source = load(run / 'assets' / task['id'] / 'task.source.json')
        for key, value in source.items():
            equal(task['id'] + '.source.' + key, task.get(key), value)
    try:
        listed = load(run / 'results.json')
    except json.JSONDecodeError:
        listed = []
        audit['pending'].append('results.json was being written; rerun after completion')
    indexed = {row.get('run'): row for row in listed}
    equal('aggregate duplicate run IDs', len(indexed), len(listed))
    for name in indexed:
        if name not in cases:
            issue('results.json', 'unscheduled result', name)
    for path in run.glob('*/result.json'):
        if re.match(r'^\d+-', path.parent.name) and path.parent.name not in cases:
            issue(str(path.relative_to(run)), 'unscheduled finalized case')
    for arm in ['baseline', 'implicit']:
        discovery = load(run / ('discovery-' + arm) / 'result.json')['data']
        expected_roots = {str((run / c['run'] / 'workspace').resolve()) for c in schedule if c['arm'] == arm}
        equal('discovery-' + arm + '.roots', sorted(d['cwd'] for d in discovery), sorted(expected_roots))
        for record in discovery:
            active = [s for s in record['skills'] if s.get('enabled')]
            wanted = [(str(Path(record['cwd']) / '.agents/skills/suffice-patch/SKILL.md'), 'suffice-patch')] if arm == 'implicit' else []
            equal('discovery-' + arm + '.' + record['cwd'], sorted((s['path'], s['name']) for s in active), wanted)
    bases = {ident: prepared(run, task, manifest['platform']) for ident, task in tasks.items()}
    prompts = {}
    for case in schedule:
        name, task = case['run'], tasks[case['task']]
        folder, work = run / name, run / name / 'workspace'
        prompt_hash = sha(read(folder / 'prompt.txt'))
        pair = case['pair']
        equal(name + '.paired_prompt', prompt_hash, prompts.setdefault(pair, prompt_hash))
        before = load(folder / 'before.json')
        maps(name + '.prepared', before, bases[task['id']][0])
        if not (folder / 'result.json').exists():
            if name in indexed:
                issue(name, 'aggregate row exists without a finalized result')
            if not (folder / 'started.json').exists():
                maps(name + '.unstarted_workspace', snapshot(work)[0], before)
            audit['pending'].append(name)
            continue
        try:
            row = load(folder / 'result.json')
        except json.JSONDecodeError:
            audit['pending'].append(name + ': result is being written')
            continue
        for key, expected in case.items():
            equal(name + '.' + key, row.get(key), expected)
        if name in indexed:
            equal(name + '.aggregate_row', row, indexed[name])
        else:
            audit['pending'].append(name + ': aggregate row not yet published')
        equal(name + '.prompt_sha256', row.get('prompt_sha256'), prompt_hash)
        raw = read(folder / 'events.jsonl')
        equal(name + '.agent_events_copy', raw, read(folder / 'agent.stdout.log'))
        events = []
        for number, line in enumerate(raw.decode().splitlines(), 1):
            try:
                events.append((number, json.loads(line)))
            except json.JSONDecodeError:
                issue(name, 'unparseable event line', number)
        usage = [(line, e['usage']) for line, e in events if e.get('type') == 'turn.completed' and 'usage' in e]
        items = [(line, e['item']) for line, e in events if e.get('type') == 'item.completed' and 'item' in e]
        commands = [(line, i) for line, i in items if i.get('type') == 'command_execution']
        totals = {key: sum(u[key] for _, u in usage) if usage and all(type(u.get(key)) is int for _, u in usage) else None for key in USAGE}
        invoked = any('collect_context.py' in i.get('command', '') for _, i in commands)
        helper = [(line, i) for line, i in commands if 'collect_context.py' in i.get('command', '') and i.get('exit_code') == 0 and re.search(r'^ROOT: ', i.get('aggregated_output', ''), re.M) and re.search(r'^FILE: ', i.get('aggregated_output', ''), re.M)]
        skill_read = any('SKILL.md' in i.get('command', '') or '# SufficePatch' in i.get('aggregated_output', '') for _, i in commands)
        completed = any(e.get('type') == 'turn.completed' for _, e in events) and not any(e.get('type') == 'turn.failed' for _, e in events)
        derived = dict(totals, raw_usage=[u for _, u in usage], commands=[i.get('command', '') for _, i in commands], completed=completed, helper_invoked=invoked, helper_success=bool(helper), skill_used=bool(helper), skill_read=skill_read,
                       tool_calls=sum(i.get('type') not in {'agent_message', 'reasoning', 'error'} for _, i in items), tool_output_bytes=sum(len(i.get('aggregated_output', '').encode()) for _, i in items))
        for key, value in derived.items():
            equal(name + '.' + key, row.get(key), value)
        for line, item in helper:
            roots = re.findall(r'^ROOT: (.+)$', item['aggregated_output'], re.M)
            if str(work.resolve()) not in roots:
                issue(name + '.helper_origin', 'helper ROOT does not match workspace', {'line': line, 'roots': roots})
        after = load(folder / 'after.json')
        current, bodies = snapshot(work)
        maps(name + '.current_vs_after', current, after)
        changed = sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))
        forbidden = [p for p in changed if task.get('expected_noop') or not (p in task['allowed_source_paths'] or (p not in before and p.startswith('tests/') and p.endswith('.py') and after[p]['kind'] == 'file' and task.get('allow_new_tests', True)))]
        bundle_ok = all(before.get('.agents/skills/suffice-patch/' + p) == after.get('.agents/skills/suffice-patch/' + p) for p in BUNDLE)
        patch = []
        for path in changed:
            left, right = bases[task['id']][1].get(path, b''), bodies.get(path, b'')
            patch += list(difflib.unified_diff(left.decode(errors='replace').splitlines(True), right.decode(errors='replace').splitlines(True), fromfile='a/' + path, tofile='b/' + path)) or [f'File type/mode changed: {path}\n']
        contaminated = case['arm'] == 'baseline' and (invoked or skill_read)
        complete = row.get('returncode') == 0 and row.get('timed_out') is False and completed
        gates_ok = all(row.get(k, {}).get('returncode') == 0 and row.get(k, {}).get('timed_out') is False for k in ['hidden', 'upstream', 'import_hidden', 'import_upstream'])
        success = complete and not contaminated and gates_ok and not forbidden and bundle_ok
        derived = {'modified_paths': changed, 'files_modified': len(changed), 'forbidden_changes': forbidden, 'added_files': sorted(after.keys() - before.keys()), 'bundle_intact': bundle_ok, 'protected_preserved': not forbidden and bundle_ok, 'noop_preserved': not task.get('expected_noop') or before == after, 'valid': not contaminated, 'comparison_valid': not contaminated, 'baseline_contamination': contaminated, 'success': success, 'infrastructure_failure': not complete and not row.get('timed_out'), 'loc_added': sum(p.startswith('+') and not p.startswith('+++') for p in patch), 'loc_deleted': sum(p.startswith('-') and not p.startswith('---') for p in patch)}
        for key, value in derived.items():
            equal(name + '.' + key, row.get(key), value)
        equal(name + '.changes.diff', read(folder / 'changes.diff').decode(), ''.join(patch))
        if contaminated:
            issue(name, 'baseline used the candidate skill')
        for path in folder.glob('*.log'):
            read(path)
        for path in folder.glob('*.command.json'):
            read(path)
        equal(name + '.agent_command', load(folder / 'agent.command.json'), row.get('command'))
        for gate in ['import-hidden', 'import-upstream']:
            if row[gate.replace('-', '_')]['returncode'] == 0:
                origin = load(folder / (gate + '.stdout.log'))['import_origin']
                if not Path(origin).resolve().is_relative_to((work / task['source_subdir']).resolve()):
                    issue(name + '.' + gate, 'import escaped candidate source', origin)
        try:
            hidden_counts = load(folder / 'hidden.stdout.log')
        except json.JSONDecodeError:
            hidden_counts = {}
        upstream_text = read(folder / 'upstream.stdout.log').decode()
        if success:
            if not (isinstance(hidden_counts.get('total'), int) and hidden_counts['total'] > 0 and hidden_counts.get('passed') == hidden_counts['total']):
                issue(name + '.hidden_output', 'successful case has no all-pass hidden count evidence')
            if not re.search(r'\b\d+ passed\b', upstream_text) or re.search(r'\b\d+ (failed|errors?)\b', upstream_text):
                issue(name + '.upstream_output', 'successful case has no clean pytest summary evidence')
        audit['cases'].append({'run': name, 'success': success, 'event_lines': len(events), 'raw_usage': [{'line': line, 'usage': value} for line, value in usage], 'computed_usage': totals, 'helper_traces': [{'line': line, 'item_id': item.get('id'), 'command': item.get('command'), 'exit_code': item.get('exit_code'), 'output_bytes': len(item.get('aggregated_output', '').encode()), 'output_sha256': sha(item.get('aggregated_output', '').encode())} for line, item in helper], 'hidden_counts': {key: hidden_counts.get(key) for key in ['passed', 'total', 'failed']}, 'upstream_summary': upstream_text.strip().splitlines()[-1:] or None, 'changed_paths': changed, 'forbidden_paths': forbidden, 'before_files': len(before), 'after_files': len(after), 'model_completed': completed})
    audit.update(scheduled=len(schedule), finalized=len(audit['cases']), aggregate_rows=len(listed), complete=len(audit['cases']) == len(schedule) and not audit['pending'], integrity_passed=not audit['mismatches'])
    audit['require_complete_satisfied'] = not args.require_complete or (audit['complete'] and audit['finalized'] == 24)
    (run / 'audit.json').write_text(json.dumps(audit, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({key: audit[key] for key in ['scheduled', 'finalized', 'aggregate_rows', 'complete', 'integrity_passed', 'require_complete_satisfied']}))
    raise SystemExit(not audit['integrity_passed'] or not audit['require_complete_satisfied'])


if __name__ == '__main__':
    main()
