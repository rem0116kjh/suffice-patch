import json
from pathlib import Path
import tempfile
import unittest

import version_compare as runner


def event(command, output='', code=0):
    return json.dumps({'type': 'item.completed', 'item': {'type': 'command_execution',
                       'command': command, 'aggregated_output': output, 'exit_code': code}})


class ParsingTests(unittest.TestCase):
    def test_no_usage_is_missing_not_zero(self):
        row = runner.parse_events(event('cat SKILL.md'))
        self.assertIsNone(row['input_tokens'])
        self.assertFalse(row['completed'])

    def test_usage_does_not_double_count_reasoning(self):
        raw = json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 100,
                         'cached_input_tokens': 60, 'output_tokens': 40, 'reasoning_output_tokens': 20}})
        row = runner.parse_events(raw)
        self.assertEqual(row['input_tokens'] + row['output_tokens'], 140)
        self.assertEqual(row['cached_input_tokens'], 60)

    def test_failed_after_completed_is_failure(self):
        row = runner.parse_events('{"type":"turn.completed","usage":{}}\n{"type":"turn.failed"}')
        self.assertFalse(row['completed'])

    def test_reading_or_searching_helper_is_not_execution(self):
        for command in ('cat scripts/collect_context.py', 'rg collect_context.py .', 'sed -n 1,40p scripts/collect_context.py'):
            with self.subTest(command=command):
                self.assertFalse(runner.parse_events(event(command))['helper_invoked'])

    def test_text_helper_evidence(self):
        row = runner.parse_events(event("/bin/zsh -lc 'python3 .agents/skills/suffice-patch/scripts/collect_context.py src'", 'ROOT: /tmp/project\nFILE: src/a.py\n'))
        self.assertTrue(row['helper_invoked'])
        self.assertTrue(row['helper_success'])

    def test_json_helper_evidence(self):
        row = runner.parse_events(event('python3.12 -B scripts/collect_context.py src --format json', '{"schema_version":1,"root":"/tmp/project","sources":[],"file_map":[]}'))
        self.assertTrue(row['helper_success'])

    def test_unrelated_json_is_not_helper_output(self):
        row = runner.parse_events(event('python3 scripts/collect_context.py src --format json', '{"root":"/tmp/project","files":[]}'))
        self.assertFalse(row['helper_success'])

    def test_failed_helper_not_success(self):
        row = runner.parse_events(event('python scripts/collect_context.py src', 'ROOT: /tmp\nFILE: a.py', 2))
        self.assertTrue(row['helper_invoked'])
        self.assertFalse(row['helper_success'])

    def test_forbidden_file_or_mode_changes_fail(self):
        task = {'allowed_source_paths': ['src/a.py'], 'allow_new_tests': False}
        old = {'LOCAL_NOTES.md': ('file', 420, b'notes'), 'src/a.py': ('file', 420, b'a')}
        new = {'LOCAL_NOTES.md': ('file', 493, b'notes'), 'src/a.py': ('file', 420, b'b')}
        metrics, _ = runner.core.compare(old, new, task)
        self.assertEqual(metrics['forbidden_changes'], ['LOCAL_NOTES.md'])

    def test_frozen_hash_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / 'manifest.json').write_text('{}')
            (out / 'manifest.sha256').write_text('incorrect')
            with self.assertRaisesRegex(ValueError, 'Manifest changed'):
                runner.verify(out)


if __name__ == '__main__':
    unittest.main()
