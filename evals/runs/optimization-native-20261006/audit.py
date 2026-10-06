"""Audit saved native traces without model calls; preserve raw usage availability."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FIELDS = ['input_tokens', 'cached_input_tokens', 'cache_write_input_tokens',
          'output_tokens', 'reasoning_output_tokens']


def main():
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    rows = []
    for arm in ['baseline', 'implicit']:
        folder = ROOT / f'1-inventory-{arm}'
        result = json.loads((folder / 'result.json').read_text())
        events = [json.loads(line) for line in (folder / 'events.jsonl').read_text().splitlines()]
        usages = [event['usage'] for event in events if event.get('type') == 'turn.completed']
        items = [event['item'] for event in events if event.get('type') == 'item.completed']
        commands = [item for item in items if item.get('type') == 'command_execution']
        usage = {key: sum(record[key] for record in usages)
                 if usages and all(key in record for record in usages) else None for key in FIELDS}
        skill_reads = [item for item in commands if 'cat .agents/skills/suffice-patch/SKILL.md' in item['command']]
        helper_calls = [item for item in commands if 'scripts/collect_context.py inventory.py' in item['command']]
        helper_ok = [item for item in helper_calls if item.get('exit_code') == 0
                     and 'FILE: inventory.py | requested target' in item.get('aggregated_output', '')]
        assert result['success'] and all(check['passed'] for check in result['checks'])
        assert result['unrelated_preserved'] and result['skill_preserved']
        assert result['modified_paths'] == ['inventory.py']
        if arm == 'baseline':
            assert not any('SKILL.md' in item['command'] or 'collect_context.py' in item['command'] for item in commands)
        else:
            assert len(skill_reads) == len(helper_ok) == 1
        row = {'arm': arm, 'raw_turn_usage': usages, 'reported_usage_fields': sorted(set.intersection(*(set(u) for u in usages))),
               **usage, 'total_input_plus_output_tokens': usage['input_tokens'] + usage['output_tokens'],
               'uncached_input_tokens': usage['input_tokens'] - usage['cached_input_tokens'],
               'duration_seconds': result['duration_seconds'], 'tool_events': result['tool_calls'],
               'command_events': len(commands), 'tool_output_bytes': result['tool_output_bytes'],
               'successful_skill_reads': sum(item.get('exit_code') == 0 for item in skill_reads),
               'successful_inspector_invocations': len(helper_ok),
               'checks_passed': len(result['checks']), 'checks_total': len(result['checks']),
               'unrelated_preserved': result['unrelated_preserved'], 'skill_preserved': result['skill_preserved'],
               'files_modified': result['files_modified'], 'loc_added': result['loc_added'],
               'prompt_sha256': result['prompt_sha256'],
               'trace_sha256': hashlib.sha256((folder / 'events.jsonl').read_bytes()).hexdigest()}
        rows.append(row)
    baseline, implicit = rows
    assert baseline['prompt_sha256'] == implicit['prompt_sha256']
    metrics = ['total_input_plus_output_tokens', 'uncached_input_tokens', 'duration_seconds', 'tool_events']
    changes = {key: round((implicit[key] / baseline[key] - 1) * 100, 4) for key in metrics}
    audit = {'cli': 'codex-cli 0.160.0', 'model': manifest['model'], 'effort': manifest['effort'],
             'tasks': manifest['tasks'], 'repeats': manifest['repeats'],
             'order': ['baseline', 'implicit'], 'reruns': 0,
             'evaluated_bundle_hashes': manifest['bundle_hashes'], 'rows': rows,
             'implicit_change_percent': changes,
             'measurement_notes': [
                 'One preselected existing inventory task, one run per arm; descriptive evidence only, not statistical or broad generalization.',
                 'Native skill discovery was independently probed before model calls; host candidate disabled in both arms, repo candidate only enabled in implicit.',
                 'Discovery probe was refreshed after final safety flags were staged and before either model run; preliminary probe output was replaced.',
                 'Other installed local skill metadata remained discoverable equally; plugins, hooks, apps, memory, web, and multi-agent were disabled by runner config.',
                 'Total is input_tokens + output_tokens. Cached input is a subset of input; reasoning output is a subset of output, neither is added again.',
                 'All five usage fields were present in both raw turn.completed records; the recorded zero cache-write count is directly reported, not fabricated for a missing field.',
                 'Uncached input increased despite total token reduction; dollar cost was not measured.',
                 'Tool events count completed command/file-change items, not shell subprocesses. Baseline: 3 commands + 1 file change; implicit: 4 commands.',
                 'Evaluated helper SHA-256 is 76c6314d8574b1514b827c1d45c425dfd0182e3cab8aa7ee8097c9e182ffc54c. A subsequent .pyi compatibility fix is outside this live-run hash and must not be described as natively rerun.',
                 'Both solutions validated before mutation, passed 3 independent assertion groups, and only changed inventory.py; both local agent checks also reported 3 passing unittest methods.',
             ]}
    (ROOT / 'audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps({'rows': rows, 'changes': changes}, indent=2))


if __name__ == '__main__':
    main()
