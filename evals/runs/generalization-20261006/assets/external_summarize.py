#!/usr/bin/env python3
"""Summarize every frozen external trial without making any model calls."""

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import statistics


ARMS = ("baseline", "implicit")
SEED = 20261006
BOOTSTRAP_SAMPLES = 10000
METRICS = (
    "total_tokens", "input_tokens", "cached_input_tokens", "uncached_input_tokens",
    "output_tokens", "tool_calls", "duration_seconds",
)


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def measurements(row):
    values = {name: row.get(name) if number(row.get(name)) else None for name in METRICS}
    incoming, cached, outgoing = (values[name] for name in ("input_tokens", "cached_input_tokens", "output_tokens"))
    values["total_tokens"] = incoming + outgoing if incoming is not None and outgoing is not None else None
    values["uncached_input_tokens"] = incoming - cached if incoming is not None and cached is not None and cached <= incoming else None
    return values


def key(row):
    return row.get("task"), row.get("repeat"), row.get("arm")


def geometric_mean(values):
    if not values:
        return None
    if 0 in values:
        return 0.0
    return math.exp(statistics.mean(math.log(value) for value in values))


def percentile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def interval(values):
    return [percentile(values, 0.025), percentile(values, 0.975)]


def bootstrap(task_values, repositories):
    """Keep the equal-task estimand; a drawn project brings all its tasks."""
    if not task_values:
        return {"task_ci95": None, "repo_cluster_ci95": None}
    rng = random.Random(SEED)
    values = list(task_values.values())
    task_samples = [geometric_mean(rng.choices(values, k=len(values))) for _ in range(BOOTSTRAP_SAMPLES)]
    clusters = defaultdict(list)
    for task_id, value in task_values.items():
        clusters[repositories[task_id]].append(value)
    cluster_values = list(clusters.values())
    rng = random.Random(SEED)
    project_samples = [
        geometric_mean([value for cluster in rng.choices(cluster_values, k=len(cluster_values)) for value in cluster])
        for _ in range(BOOTSTRAP_SAMPLES)
    ]
    return {"task_ci95": interval(task_samples), "repo_cluster_ci95": interval(project_samples)}


def arm_totals(rows, schedule):
    result = {}
    for arm in ARMS:
        selected = [row for row in rows if row.get("arm") == arm]
        planned = [case for case in schedule if case["arm"] == arm]
        values = [measurements(row) for row in selected]
        result[arm] = {
            "recorded_attempts": len(selected),
            "planned_attempts": len(planned),
            "successes": sum(row.get("success") is True for row in selected),
            "invalid_comparisons": sum(row.get("comparison_valid") is not True for row in selected),
            "metrics": {
                metric: {
                    "sum": sum(value[metric] for value in values if value[metric] is not None),
                    "observed_attempts": sum(value[metric] is not None for value in values),
                    "missing_recorded_attempts": sum(value[metric] is None for value in values),
                }
                for metric in METRICS
            },
        }
    return result


def summarize(manifest, records):
    tasks = manifest["tasks"]
    schedule = manifest["schedule"]
    repeats = manifest["repeats"]
    if not tasks or not isinstance(repeats, int) or repeats < 1:
        raise ValueError("Manifest needs task definitions and a positive repeat count")
    definitions = {task["id"]: task for task in tasks}
    if len(definitions) != len(tasks) or any(not task.get("repo_url") for task in tasks):
        raise ValueError("Manifest task IDs must be unique and have repo_url")
    planned_keys = [key(case) for case in schedule]
    expected = {(task["id"], repeat, arm) for task in tasks for repeat in range(1, repeats + 1) for arm in ARMS}
    if len(planned_keys) != len(set(planned_keys)) or set(planned_keys) != expected:
        raise ValueError("Schedule must contain each planned task/repeat/arm exactly once")

    grouped = defaultdict(list)
    for row in records:
        grouped[key(row)].append(row)
    duplicates = [list(case) for case, rows in grouped.items() if len(rows) > 1]
    unexpected = [list(case) for case in grouped if case not in expected]
    unfinished = [case for case in schedule if not grouped[key(case)]]
    invalid = [row for row in records if row.get("comparison_valid") is not True]
    missing = [
        {"task": row.get("task"), "repeat": row.get("repeat"), "arm": row.get("arm"),
         "metrics": [name for name, value in measurements(row).items() if value is None]}
        for row in records if any(value is None for value in measurements(row).values())
    ]
    malformed_status = [list(key(row)) for row in records if not isinstance(row.get("success"), bool) or not isinstance(row.get("helper_success"), bool)]
    complete = not unfinished and not duplicates and not unexpected and len(records) == len(schedule)
    repositories = {task["id"]: task["repo_url"] for task in tasks}
    per_task = []
    attempts = []
    for case in schedule:
        found = grouped[key(case)]
        row = found[0] if len(found) == 1 else None
        attempts.append({
            "task": case["task"], "repeat": case["repeat"], "arm": case["arm"],
            "recorded": bool(found), "record_count": len(found),
            "success": row.get("success") if row else None,
            "comparison_valid": row.get("comparison_valid") if row else None,
            "helper_success": row.get("helper_success") if row else None,
            "metrics": measurements(row) if row else dict.fromkeys(METRICS),
        })
    for task in tasks:
        selected = [row for row in records if row.get("task") == task["id"]]
        task_schedule = [case for case in schedule if case["task"] == task["id"]]
        pairs = []
        for repeat in range(1, repeats + 1):
            arms = {arm: grouped[(task["id"], repeat, arm)] for arm in ARMS}
            paired = all(len(rows) == 1 for rows in arms.values())
            values = {arm: measurements(rows[0]) for arm, rows in arms.items()} if paired else {}
            ratios = {}
            for metric in METRICS:
                base = values["baseline"][metric] if paired else None
                skill = values["implicit"][metric] if paired else None
                ratios[metric] = skill / base if base is not None and base > 0 and skill is not None else None
            pairs.append({
                "repeat": repeat, "both_recorded_once": paired,
                "comparison_valid": paired and all(rows[0].get("comparison_valid") is True for rows in arms.values()),
                "ratios_implicit_over_baseline": ratios,
            })
        medians = {}
        observed = {}
        for metric in METRICS:
            ratios = [pair["ratios_implicit_over_baseline"][metric] for pair in pairs]
            observed[metric] = sum(value is not None for value in ratios)
            medians[metric] = statistics.median(ratios) if all(value is not None for value in ratios) else None
        totals = arm_totals(selected, task_schedule)
        per_task.append({
            "id": task["id"], "repo_url": task["repo_url"], "expected_noop": bool(task.get("expected_noop")),
            "platform_exclusions": task.get("platform_exclusions", []),
            "arms": totals, "pairs": pairs, "task_median_ratios": medians,
            "observed_paired_ratios": observed,
            "accuracy_non_decreased": totals["implicit"]["successes"] >= totals["baseline"]["successes"],
        })

    overall = arm_totals(records, schedule)
    accuracy = {
        "overall_non_decreased": overall["implicit"]["successes"] >= overall["baseline"]["successes"],
        "per_task_non_decreased": all(task["accuracy_non_decreased"] for task in per_task),
        "baseline_successes": overall["baseline"]["successes"],
        "implicit_successes": overall["implicit"]["successes"],
    }
    accuracy["gate_passed"] = complete and not malformed_status and accuracy["overall_non_decreased"] and accuracy["per_task_non_decreased"]
    metric_results = {}
    for metric in METRICS:
        observed_values = {task["id"]: task["task_median_ratios"][metric] for task in per_task if task["task_median_ratios"][metric] is not None}
        all_tasks = len(observed_values) == len(tasks)
        metric_results[metric] = {
            "task_median_ratios": {task["id"]: task["task_median_ratios"][metric] for task in per_task},
            "tasks_with_complete_ratios": len(observed_values),
            "equal_task_geometric_mean_ratio": geometric_mean(list(observed_values.values())) if all_tasks else None,
            **(bootstrap(observed_values, repositories) if all_tasks else {"task_ci95": None, "repo_cluster_ci95": None}),
        }

    design_matches = len(tasks) == 4 and len(set(repositories.values())) == 3 and repeats == 3
    common_reasons = []
    for failed, reason in (
        (not design_matches, "design_differs_from_frozen_4_tasks_3_projects_3_repeats"),
        (not complete, "unfinished_duplicate_or_unplanned_attempts"),
        (bool(invalid), "invalid_comparisons"),
        (manifest.get("discovery_passed") is not True, "skill_discovery_not_verified"),
        (bool(missing), "missing_metrics"),
        (bool(malformed_status), "missing_or_malformed_status"),
        (not accuracy["gate_passed"], "accuracy_gate_not_met"),
    ):
        if failed:
            common_reasons.append(reason)
    gates = {}
    for name, metric, cutoff in (("tokens", "total_tokens", 0.90), ("latency", "duration_seconds", 0.95)):
        estimate = metric_results[metric]
        ratio = estimate["equal_task_geometric_mean_ratio"]
        bounds = estimate["task_ci95"]
        reasons = list(common_reasons)
        if ratio is None or bounds is None:
            reasons.append("missing_or_undefined_paired_ratios")
        else:
            if ratio > cutoff:
                reasons.append("ratio_threshold_not_met")
            if bounds[1] >= 1.0:
                reasons.append("task_bootstrap_upper_not_below_one")
        gates[name] = {"passed": not reasons, "ratio_cutoff": cutoff, "required_ci_upper_below": 1.0, "reasons": reasons}

    grouped_results = {}
    for label, is_noop in (("bug_only", False), ("noop", True)):
        selected_ids = {task["id"] for task in per_task if task["expected_noop"] == is_noop}
        grouped_results[label] = {
            "task_ids": sorted(selected_ids),
            "arms": arm_totals([row for row in records if row.get("task") in selected_ids], [case for case in schedule if case["task"] in selected_ids]),
            "equal_task_geometric_mean_ratios": {
                metric: geometric_mean([task["task_median_ratios"][metric] for task in per_task if task["id"] in selected_ids])
                if selected_ids and all(task["task_median_ratios"][metric] is not None for task in per_task if task["id"] in selected_ids) else None
                for metric in METRICS
            },
        }
    implicit = [row for row in records if row.get("arm") == "implicit"]
    helper_count = sum(row.get("helper_success") is True for row in implicit)
    planned_implicit = overall["implicit"]["planned_attempts"]
    return {
        "schema_version": 1,
        "methodology": {
            "bootstrap_seed": SEED, "bootstrap_samples": BOOTSTRAP_SAMPLES,
            "primary": "Median of all paired ratios within each task, then equal-task geometric mean; failures remain included",
            "repo_cluster": "Resample projects with replacement, retaining every task median in each selected project",
            "interval": "Percentile 95%, linear interpolation; descriptive convenience-sample intervals, not population guarantees",
            "token_definition": "total_tokens = input_tokens + output_tokens; cached_input_tokens is already included in input_tokens",
        },
        "completion": {
            "planned_attempts": len(schedule), "recorded_attempts": len(records),
            "unfinished_attempts": len(unfinished), "unfinished_cases": unfinished,
            "invalid_comparisons": len(invalid), "missing_metric_attempts": missing,
            "duplicate_keys": duplicates, "unexpected_keys": unexpected,
            "malformed_status_keys": malformed_status, "complete": complete,
            "matches_frozen_design": design_matches,
        },
        "accuracy": accuracy, "arms": overall, "tasks": per_task,
        "groups": grouped_results, "metrics": metric_results, "gates": gates,
        "helper": {
            "successful_implicit_attempts": helper_count, "planned_implicit_attempts": planned_implicit,
            "recorded_implicit_attempts": len(implicit),
            "success_rate_over_all_planned_implicit": helper_count / planned_implicit if planned_implicit else None,
            "success_rate_over_all_recorded_implicit": helper_count / len(implicit) if implicit else None,
            "note": "All implicit attempts are the denominator, including failures and non-selection; unfinished attempts remain unknown",
        },
        "actual_cost": {"measured": False, "usd": None},
        "attempts": attempts,
        "limits": [
            "Three small Python projects, named localized tasks, one computer/model/configuration; no other-user or broad language/platform claim",
            "Historical public fixes may occur in model training data",
            "Four tasks are not 24 independent tasks; one project's two tasks are dependent",
            "Repeated runs are not independent human users; bootstrap intervals are descriptive",
            "Failed attempts and automatic non-selection remain in accuracy, totals, and paired ratios",
            "No actual billing or monetary savings were measured",
        ],
    }


def shown(value, places=3):
    if value is None:
        return "미측정"
    return f"{value:.{places}f}" if isinstance(value, float) else str(value)


def render_markdown(summary):
    completion = summary["completion"]
    lines = [
        "# SufficePatch 외부 저장소 평가 결과", "",
        f"계획 {completion['planned_attempts']}회 중 {completion['recorded_attempts']}회 기록, 미완료 {completion['unfinished_attempts']}회. "
        f"비교 무효 {completion['invalid_comparisons']}회. 성공·실패·스킬 미선택을 모두 포함했습니다.", "",
        f"토큰 개선 기준: **{'충족' if summary['gates']['tokens']['passed'] else '미충족'}**. "
        f"전체 에이전트 시간 개선 기준: **{'충족' if summary['gates']['latency']['passed'] else '미충족'}**. "
        "실제 청구 비용은 측정하지 않았습니다.", "",
        "| 항목 | baseline | 자동 선택 |", "| --- | ---: | ---: |",
    ]
    arms = summary["arms"]
    lines.append(f"| 성공 / 계획 | {arms['baseline']['successes']} / {arms['baseline']['planned_attempts']} | {arms['implicit']['successes']} / {arms['implicit']['planned_attempts']} |")
    for metric in METRICS:
        values = []
        for arm in ARMS:
            entry = arms[arm]["metrics"][metric]
            values.append(f"{shown(entry['sum'])} (관측 {entry['observed_attempts']}/{arms[arm]['planned_attempts']}, 기록 내 누락 {entry['missing_recorded_attempts']})")
        lines.append(f"| {metric} 합계 | {' | '.join(values)} |")
    lines += ["", "총 토큰은 input + output입니다. cached input은 input에 이미 포함되므로 다시 더하지 않았습니다. 누락값을 0으로 대체하지 않았으며, 합계는 관측된 모든 시도의 합입니다.", "", "## 과제별 결과", "", "| 과제 | 유형 | baseline 성공 | 자동 선택 성공 | 토큰 비율 중앙값 | 시간 비율 중앙값 |", "| --- | --- | ---: | ---: | ---: | ---: |"]
    for task in summary["tasks"]:
        lines.append(f"| {task['id']} | {'변경 불필요' if task['expected_noop'] else '버그 수정'} | {task['arms']['baseline']['successes']}/{task['arms']['baseline']['planned_attempts']} | {task['arms']['implicit']['successes']}/{task['arms']['implicit']['planned_attempts']} | {shown(task['task_median_ratios']['total_tokens'])} | {shown(task['task_median_ratios']['duration_seconds'])} |")
    lines += ["", "비율은 자동 선택 / baseline이며 1보다 작으면 적게 사용한 것입니다. 각 과제의 모든 반복쌍을 포함하며 하나라도 필요한 값이 없으면 그 과제 중앙값을 산출하지 않습니다.", ""]
    for task in summary["tasks"]:
        for exclusion in task["platform_exclusions"]:
            lines.append(f"- 사전 플랫폼 제외 ({task['id']}): {exclusion['node']} — {exclusion['reason']}")
    lines += ["", "## 사전 고정한 통계", "", "| 지표 | 과제 동일 가중 기하평균 비율 | 과제 bootstrap 95% | 프로젝트 cluster bootstrap 95% |", "| --- | ---: | --- | --- |"]
    for metric in METRICS:
        entry = summary["metrics"][metric]
        intervals = ["미측정" if entry[name] is None else " – ".join(shown(value) for value in entry[name]) for name in ("task_ci95", "repo_cluster_ci95")]
        lines.append(f"| {metric} | {shown(entry['equal_task_geometric_mean_ratio'])} | {' | '.join(intervals)} |")
    lines += ["", "반복쌍 비율 → 과제별 중앙값 → 4개 과제 동일 가중 기하평균 순서입니다. seed 20261006, 10,000회 복원추출, percentile 95% 구간입니다. 프로젝트 보조 구간은 동일 프로젝트의 두 과제를 함께 재표집합니다. 적은 편의 표본의 기술적 구간이며 사용자 모집단의 통계적 보장이 아닙니다.", ""]
    for name, gate in summary["gates"].items():
        lines.append(f"- {name}: {'충족' if gate['passed'] else '미충족'}; 요구 비율 ≤ {gate['ratio_cutoff']}, 과제 구간 상한 < 1.0; 사유: {', '.join(gate['reasons']) or '모든 사전 기준 충족'}.")
    lines += ["", "## 버그 수정과 변경 불필요 과제", "", "| 그룹 | baseline 성공 / 계획 | 자동 선택 성공 / 계획 | 토큰 기하평균 비율 | 시간 기하평균 비율 |", "| --- | ---: | ---: | ---: | ---: |"]
    for name, group in summary["groups"].items():
        a = group["arms"]
        lines.append(f"| {name} | {a['baseline']['successes']}/{a['baseline']['planned_attempts']} | {a['implicit']['successes']}/{a['implicit']['planned_attempts']} | {shown(group['equal_task_geometric_mean_ratios']['total_tokens'])} | {shown(group['equal_task_geometric_mean_ratios']['duration_seconds'])} |")
    lines += ["", "아래는 그룹별 모든 기록의 관측 합계입니다. 누락 횟수와 과제별 세부 합계는 `summary.json`에 보존합니다.", "", "| 그룹 / 조건 | 총 토큰 | cached input | uncached input | output | 시간(s) |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for name, group in summary["groups"].items():
        for arm in ARMS:
            metrics = group["arms"][arm]["metrics"]
            sums = [shown(metrics[metric]["sum"]) for metric in ("total_tokens", "cached_input_tokens", "uncached_input_tokens", "output_tokens", "duration_seconds")]
            lines.append(f"| {name} / {arm} | {' | '.join(sums)} |")
    helper = summary["helper"]
    lines += ["", f"도우미 성공 실행: 계획된 자동 선택 시도 전체 {helper['planned_implicit_attempts']}회 중 {helper['successful_implicit_attempts']}회. 기록된 자동 선택 시도는 {helper['recorded_implicit_attempts']}회입니다. 미완료는 미선택으로 확정하지 않습니다.", "", "## 모든 계획 시도", "", "| 과제 | 반복 | 조건 | 성공 | 비교 유효 | 총 토큰 | 시간(s) | 도우미 성공 |", "| --- | ---: | --- | --- | --- | ---: | ---: | --- |"]
    for attempt in summary["attempts"]:
        status = "미완료" if not attempt["recorded"] else "중복 기록" if attempt["record_count"] != 1 else "성공" if attempt["success"] else "실패"
        lines.append(f"| {attempt['task']} | {attempt['repeat']} | {attempt['arm']} | {status} | {shown(attempt['comparison_valid'])} | {shown(attempt['metrics']['total_tokens'])} | {shown(attempt['metrics']['duration_seconds'])} | {shown(attempt['helper_success'])} |")
    lines += ["", "## 한계", ""]
    lines += [f"- {limit}" for limit in summary["limits"]]
    lines += ["", "원시 기록은 `results.json`, 고정 조건은 `manifest.json`, 기계 판독 가능한 전체 합계·반복쌍·판정은 `summary.json`에 있습니다.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    manifest_path, results_path = args.run / "manifest.json", args.run / "results.json"
    manifest = json.loads(manifest_path.read_text())
    records = json.loads(results_path.read_text())
    if not isinstance(records, list):
        raise ValueError("results.json must be a flat list of trial records")
    result = summarize(manifest, records)
    result["input_sha256"] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (manifest_path, results_path)}
    result["summarizer_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (args.run / "summary.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    (args.run / "RESULTS.md").write_text(render_markdown(result))
    print(json.dumps({"run": str(args.run), "completion": result["completion"], "gates": result["gates"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
