# Frozen v4 versus v5 external evaluation

Registered before any model trial on 2026-10-15. This is a new comparison;
historical v3/no-skill results are not its baseline.

- Arms: released `dist/suffice-patch-v4.zip` and `dist/suffice-patch-v5.0.0.zip`.
- Tasks: the existing real upstream dotenv backslash, packaging epoch-prefix,
  and itsdangerous invalid-timestamp fixes. Use full pinned base repositories,
  original prompts, immutable existing tests, and independent graders.
- Three repetitions per task and arm, 18 sequential runs. Pair order is shuffled
  with seed 20261015; within-pair arm order alternates by task and repetition.
- Codex CLI 0.162.1, `gpt-6-astra`, reasoning `low`, 300-second agent timeout.
  This matches historical evaluation settings, not the interactive chat effort.
- Native automatic skill selection. Only the assigned local skill is enabled;
  host skills, plugins, memory, web search, and agent delegation are disabled.
  Both arms get byte-identical task prompts. No forced helper invocation.
- Python 3.12 and locked dependencies in per-project virtual environments.
  Existing macOS-only dotenv `printenv --version` exclusion is retained exactly.
- Before model runs, verify failing base and passing reference with the hidden
  graders, run both upstream suites, and prove imports originate in each checkout.
- Freeze sources, skill archives, plan, runner, runtime versions, prompts,
  initial snapshots, native discovery, and manifest hashes before model runs.
- Success requires completed agent execution, independent grader and upstream
  suite passing, correct import origin, and preservation of protected files.
  Include all failed attempts. Never replace a task or retry for a better score.
  Stop after two consecutive infrastructure failures; preserve partial evidence.
- Record raw CLI usage: input, cached input, output, and any separately reported
  reasoning tokens. Total = input + output (do not add reasoning twice).
  Uncached input = input - cached input only when both are known. Missing is null.
  Account billing cost is unavailable; tokens are not dollar-cost estimates.
- Time is wall-clock agent process time, including its tool use and own tests,
  excluding environment setup and independent post-run grading. Also save grading
  durations. Sequential adjacent pairs reduce, but do not eliminate, service noise.
- Report success, helper activation, per-task median tokens/time, raw arm totals,
  and every run. Primary effect: median paired v5/v4 ratio within each task,
  then geometric mean across the three tasks (equal project weight).
  Show descriptive task-bootstrap 95% intervals (10,000 samples, seed 20261015).
- Claim an observed efficiency win only if v5 has no lower overall or per-task
  success, all 18 comparisons are valid, all required metrics are reported, and
  paired token ratio <= 0.90 or time ratio <= 0.95 respectively, with corresponding
  interval upper bound < 1. Otherwise report the measured direction without
  asserting a reliable improvement. Three Python projects cannot establish broad
  language, production, or unseen-task performance; public bug contamination and
  prompt caching remain limitations. No no-skill arm is included.

The evaluated releases and task graders must not change after observing results.
