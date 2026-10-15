import copy
import unittest

from version_summarize import summarize


def fixture():
    tasks = [{'id': str(i)} for i in range(3)]
    schedule = [{'task': t['id'], 'repeat': r, 'arm': a} for t in tasks for r in range(1, 4) for a in ('v4', 'v5')]
    manifest = {'tasks': tasks, 'repeats': 3, 'seed': 20261015, 'schedule': schedule, 'discovery_passed': True}
    rows = [{**c, 'success': True, 'comparison_valid': True, 'helper_success': True,
             'input_tokens': 100 if c['arm'] == 'v4' else 70, 'cached_input_tokens': 20,
             'output_tokens': 10, 'tool_calls': 2, 'duration_seconds': 10 if c['arm'] == 'v4' else 8} for c in schedule]
    return manifest, rows


class SummaryTests(unittest.TestCase):
    def test_paired_math_and_usage(self):
        manifest, rows = fixture()
        result = summarize(manifest, rows)
        self.assertAlmostEqual(result['effects_v5_over_v4']['total_tokens']['ratio'], 80 / 110)
        self.assertEqual(result['arms']['v5']['metrics']['uncached_input_tokens']['sum'], 450)
        self.assertTrue(result['efficiency_win_gates']['total_tokens'])

    def test_missing_usage_blocks_token_claim(self):
        manifest, rows = fixture()
        rows[1]['input_tokens'] = None
        result = summarize(manifest, rows)
        self.assertIsNone(result['effects_v5_over_v4']['total_tokens']['ratio'])
        self.assertFalse(result['efficiency_win_gates']['total_tokens'])

    def test_failures_remain_in_metrics_and_block_win(self):
        manifest, rows = fixture()
        rows[1]['success'] = False
        result = summarize(manifest, rows)
        self.assertEqual(result['arms']['v5']['metrics']['total_tokens']['sum'], 720)
        self.assertFalse(result['efficiency_win_gates']['duration_seconds'])

    def test_incomplete_is_not_success(self):
        manifest, rows = fixture()
        result = summarize(manifest, rows[:-1])
        self.assertFalse(result['complete'])
        self.assertFalse(result['efficiency_win_gates']['total_tokens'])

    def test_duplicate_is_rejected(self):
        manifest, rows = fixture()
        with self.assertRaises(ValueError):
            summarize(manifest, rows + [copy.deepcopy(rows[0])])

    def test_equal_project_weight(self):
        manifest, rows = fixture()
        for row in rows:
            if row['task'] == '0':
                row['input_tokens'] *= 1000
                row['output_tokens'] *= 1000
        self.assertAlmostEqual(summarize(manifest, rows)['effects_v5_over_v4']['total_tokens']['ratio'], 80 / 110)


if __name__ == '__main__':
    unittest.main()
