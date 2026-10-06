"""Synthetic controls for frozen evaluation statistics and failure accounting."""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


spec = importlib.util.spec_from_file_location("external_summarize", Path(__file__).with_name("external_summarize.py"))
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


def fixture(token_ratios=(0.8, 0.8, 0.8, 0.8), time_ratio=0.9):
    tasks = [{"id": f"task-{index}", "repo_url": f"https://example.org/repo{min(index, 2)}", "expected_noop": index == 3} for index in range(4)]
    manifest = {"tasks": tasks, "repeats": 3, "discovery_passed": True, "schedule": []}
    rows = []
    for index, task in enumerate(tasks):
        for repeat in range(1, 4):
            for arm in summary.ARMS:
                case = {"task": task["id"], "repeat": repeat, "arm": arm}
                manifest["schedule"].append(case)
                ratio = token_ratios[index] if arm == "implicit" else 1
                rows.append({**case, "success": True, "comparison_valid": True, "input_tokens": 900 * ratio,
                             "cached_input_tokens": 600 * ratio, "output_tokens": 100 * ratio,
                             "tool_calls": 3, "duration_seconds": 10 * (time_ratio if arm == "implicit" else 1),
                             "helper_success": arm == "implicit"})
    return manifest, rows


class SummaryTests(unittest.TestCase):
    def test_known_improvement_and_no_cached_double_count(self):
        manifest, rows = fixture()
        result = summary.summarize(manifest, rows)
        self.assertTrue(result["gates"]["tokens"]["passed"])
        self.assertTrue(result["gates"]["latency"]["passed"])
        self.assertAlmostEqual(result["metrics"]["total_tokens"]["equal_task_geometric_mean_ratio"], 0.8)
        self.assertEqual(result["metrics"]["total_tokens"]["task_ci95"], [0.8, 0.8])
        self.assertEqual(result["arms"]["baseline"]["metrics"]["total_tokens"]["sum"], 12000)
        self.assertEqual(result["arms"]["baseline"]["metrics"]["uncached_input_tokens"]["sum"], 3600)
        self.assertEqual(result["helper"]["planned_implicit_attempts"], 12)
        self.assertEqual(result["groups"]["bug_only"]["arms"]["baseline"]["planned_attempts"], 9)
        self.assertEqual(result["groups"]["noop"]["arms"]["baseline"]["planned_attempts"], 3)
        self.assertFalse(result["actual_cost"]["measured"])

    def test_loss_blocks_both_efficiency_gates(self):
        manifest, rows = fixture(token_ratios=(1.2,) * 4, time_ratio=1.1)
        result = summary.summarize(manifest, rows)
        self.assertFalse(result["gates"]["tokens"]["passed"])
        self.assertFalse(result["gates"]["latency"]["passed"])

    def test_per_task_accuracy_cannot_be_offset_by_another_task(self):
        manifest, rows = fixture()
        rows[1]["success"] = False  # implicit loses one on task 0
        rows[6]["success"] = False  # baseline loses one on task 1
        result = summary.summarize(manifest, rows)
        self.assertTrue(result["accuracy"]["overall_non_decreased"])
        self.assertFalse(result["accuracy"]["per_task_non_decreased"])
        self.assertFalse(result["gates"]["tokens"]["passed"])
        self.assertAlmostEqual(result["metrics"]["total_tokens"]["equal_task_geometric_mean_ratio"], 0.8)
        self.assertEqual(result["arms"]["implicit"]["metrics"]["total_tokens"]["sum"], 9600)

    def test_missing_metrics_and_unfinished_are_explicit_not_zero(self):
        manifest, rows = fixture()
        rows[1]["output_tokens"] = None
        rows.pop()
        result = summary.summarize(manifest, rows)
        self.assertEqual(result["completion"]["unfinished_attempts"], 1)
        self.assertEqual(len(result["completion"]["missing_metric_attempts"]), 1)
        self.assertIsNone(result["metrics"]["total_tokens"]["equal_task_geometric_mean_ratio"])
        self.assertFalse(result["gates"]["tokens"]["passed"])
        self.assertEqual(result["arms"]["implicit"]["metrics"]["total_tokens"]["observed_attempts"], 10)
        self.assertEqual(result["helper"]["planned_implicit_attempts"], 12)
        self.assertEqual(result["helper"]["recorded_implicit_attempts"], 11)
        self.assertIn("미완료", summary.render_markdown(result))

    def test_contamination_and_discovery_failure_block_positive_claim(self):
        manifest, rows = fixture()
        rows[0]["comparison_valid"] = False
        manifest["discovery_passed"] = False
        result = summary.summarize(manifest, rows)
        self.assertFalse(result["gates"]["tokens"]["passed"])
        self.assertIn("invalid_comparisons", result["gates"]["tokens"]["reasons"])
        self.assertIn("skill_discovery_not_verified", result["gates"]["tokens"]["reasons"])
        self.assertEqual(result["arms"]["baseline"]["metrics"]["total_tokens"]["sum"], 12000)

    def test_task_medians_then_equal_task_weight_not_pooled_ratio(self):
        manifest, rows = fixture(token_ratios=(0.5, 0.8, 1.0, 1.2))
        # One much larger task must not dominate the equal-task estimate.
        for row in rows[:6]:
            for name in ("input_tokens", "cached_input_tokens", "output_tokens"):
                row[name] *= 100
        # An extreme first replicate does not change task 0's median.
        rows[1]["input_tokens"] *= 100
        rows[1]["cached_input_tokens"] *= 100
        rows[1]["output_tokens"] *= 100
        result = summary.summarize(manifest, rows)
        expected = (0.5 * 0.8 * 1.0 * 1.2) ** 0.25
        self.assertAlmostEqual(result["metrics"]["total_tokens"]["equal_task_geometric_mean_ratio"], expected)
        self.assertEqual(result["tasks"][0]["task_median_ratios"]["total_tokens"], 0.5)
        self.assertGreaterEqual(result["metrics"]["total_tokens"]["task_ci95"][1], 1.0)
        self.assertFalse(result["gates"]["tokens"]["passed"])

    def test_project_bootstrap_retains_cluster_dependence(self):
        values = {"a": 0.5, "b": 0.6, "c": 1.4, "d": 1.4}
        repos = {"a": "one", "b": "two", "c": "three", "d": "three"}
        estimate = summary.bootstrap(values, repos)
        self.assertEqual(estimate, summary.bootstrap(values, repos))
        self.assertNotEqual(estimate["task_ci95"], estimate["repo_cluster_ci95"])
        self.assertAlmostEqual(estimate["repo_cluster_ci95"][1], 1.4)

    def test_duplicate_trials_never_select_a_favorable_rerun(self):
        manifest, rows = fixture()
        extra = copy.deepcopy(rows[1])
        extra["input_tokens"] = 1
        extra["cached_input_tokens"] = 0
        rows.append(extra)
        result = summary.summarize(manifest, rows)
        self.assertEqual(len(result["completion"]["duplicate_keys"]), 1)
        self.assertIsNone(result["tasks"][0]["task_median_ratios"]["total_tokens"])
        self.assertFalse(result["gates"]["tokens"]["passed"])
        self.assertEqual(result["arms"]["implicit"]["recorded_attempts"], 13)

    def test_failed_nonselection_remains_in_helper_denominator(self):
        manifest, rows = fixture()
        for row in rows:
            if row["arm"] == "implicit":
                row["helper_success"] = False
        rows[1]["helper_success"] = True
        rows[3]["success"] = False
        result = summary.summarize(manifest, rows)
        self.assertEqual(result["helper"]["success_rate_over_all_recorded_implicit"], 1 / 12)
        self.assertEqual(result["helper"]["success_rate_over_all_planned_implicit"], 1 / 12)

    def test_missing_cache_and_impossible_cache_block_claims(self):
        for cached in (None, 99999):
            manifest, rows = fixture()
            rows[1]["cached_input_tokens"] = cached
            result = summary.summarize(manifest, rows)
            self.assertFalse(result["gates"]["tokens"]["passed"])
            self.assertIsNone(result["attempts"][1]["metrics"]["uncached_input_tokens"])

    def test_cli_outputs_reproducible_json_and_readable_report(self):
        manifest, rows = fixture()
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "manifest.json").write_text(json.dumps(manifest))
            (folder / "results.json").write_text(json.dumps(rows))
            command = [sys.executable, str(Path(summary.__file__)), "--run", str(folder)]
            subprocess.run(command, check=True, capture_output=True)
            first = (folder / "summary.json").read_bytes()
            subprocess.run(command, check=True, capture_output=True)
            self.assertEqual(first, (folder / "summary.json").read_bytes())
            report = (folder / "RESULTS.md").read_text()
            self.assertIn("실제 청구 비용은 측정하지 않았습니다", report)
            self.assertIn("24회", report)
            self.assertIn("cache", report)


if __name__ == "__main__":
    unittest.main()
