[한국어](README.md) · English

# SufficePatch v5.0.0

**Collect the files you need before changing the code.**

SufficePatch helps Codex and Claude Code collect a bounded set of source files, project
instructions and Git changes. Starting from requested files, it finds local dependencies
and reference/test candidates to help the agent decide what to read and check next.

Use it for focused bug fixes or package-level work in a monorepo. The inspector is read-only;
the AI agent performs edits and runs checks using the project's own tools.

[Download v5.0.0](dist/suffice-patch-v5.0.0.zip) · [Real-project comparison](evals/V5_EXTERNAL_20261015.en.md) · [Functional validation](evals/V5_20261015.md) · [CLI and JSON guide](references/cli.md) · [Project website](https://rem0116kjh.github.io/suffice-patch/?lang=en)

## When to use it

| Task | Start with | What you get |
|---|---|---|
| Fix a specific function or file | A file path | Source, local dependencies, reference/test candidates |
| Inspect existing edits | `--changed all` or `--changed staged` | Changed paths, current source, staged and unstaged diffs |
| Explore a large monorepo | `--scope packages/web` | File maps and reference candidates for the selected package |
| Triage the scope first | `--summary` | Paths, hashes, limits and omissions without source bodies |
| Connect another tool | `--format json` | A structured result with a schema version |

One collection does not establish every effect of a change. Inspect relevant files in bounded
parts, then run integration checks when a change affects multiple packages.

## Installation and quick start

The inspector needs **Python 3.9+, Git and ripgrep (`rg`)**. Your project does not need to use
Python. No additional Python packages or project dependencies are required.

Extract the [installation ZIP](dist/suffice-patch-v5.0.0.zip), enter its `suffice-patch` folder,
and run these commands to install for Codex. Copy all five files: the skill instructions,
three Python helpers and CLI reference.

```sh
mkdir -p "$HOME/.agents/skills/suffice-patch/scripts" "$HOME/.agents/skills/suffice-patch/references"
cp SKILL.md "$HOME/.agents/skills/suffice-patch/SKILL.md"
cp scripts/*.py "$HOME/.agents/skills/suffice-patch/scripts/"
cp references/cli.md "$HOME/.agents/skills/suffice-patch/references/"
python3 -B "$HOME/.agents/skills/suffice-patch/scripts/collect_context.py" --version
# SufficePatch 5.0.0
```

For Claude Code, replace `.agents/skills` with `.claude/skills` in the paths above.
Use the [SHA256 manifest](dist/release.json) to verify archives and files.
The [previous v4 archive](dist/suffice-patch-v4.zip) remains available.

After installation, start a new conversation and describe the files, behavior and packages
you want to change. Codex may select the skill for a relevant request; you can also name it:

```text
$suffice-patch Fix the cart calculation bug in packages/web.
Preserve the existing response format and check the relevant tests.
```

In Claude Code, invoke `/suffice-patch`. Automatic selection is not guaranteed. Current checks
ran on macOS Apple Silicon; other operating systems and users' environments need validation.

## v5 change selection and output controls

- **Changed-file selection**: start from Git status with `--changed all|staged|worktree`. Handle deletions, renames and nested roots; restrict automatic selection with `--scope`.
- **Summary and JSON**: `--summary` returns paths and hashes without source bodies or diffs. `--format json` emits a versioned structured result.
- **Less repeated analysis**: share path checks, manifest reads and package listings within one invocation. Discard caches on exit.
- **Repeatable searches**: sort paths before applying candidate limits. Check the installed release with `--version`.

```sh
python3 -B scripts/collect_context.py --changed all --scope packages/web
python3 -B scripts/collect_context.py --changed staged --summary
python3 -B scripts/collect_context.py --changed worktree --include-untracked --format json
python3 -B scripts/collect_context.py --version
```

Untracked files require `--include-untracked`, valid with all/worktree. Even staged mode
returns current working-tree source; staged changes have their own diff. Summary still reads
files to compute hashes and dependencies: it reduces **emitted content**. Read full bodies
and diffs before editing.

## Language and monorepo support

| Target | Collection method |
|---|---|
| Python | AST-based local and relative imports, `src` layouts, defined symbols |
| JS/TS, JSX/TSX, Vue/Svelte | Relative imports, exports, `require`, string-literal dynamic imports, TypeScript extension and index-file candidates |
| Go | Local packages within a `go.mod` module and source candidates in the same package |
| Rust | Local module candidates from `mod` and `crate`/`self`/`super` paths |
| C/C++ | Quoted includes and candidates in nearby include directories |
| Java/Kotlin/C#/Swift/Ruby/PHP, Shell, HTML/CSS, SQL, configuration, documentation | Text and symbol reference search, nearby project manifests |

Language hints are not a complete compiler analysis. Aliases, package names across workspaces,
dynamic references, conditional builds, and generated code require follow-up when the helper
reports gaps. Dependency discovery in Vue/Svelte covers inline scripts. The helper also searches
for tests in other languages; use the project manifests and instructions to determine how to
run them.

```sh
# List candidate paths within one monorepo package
python3 -B scripts/collect_context.py . --scope packages/web
# Collect files, dependencies, references, and tests
python3 -B scripts/collect_context.py packages/web/src/cart.ts --scope packages/web
# Search two connected packages and narrow references to a specific symbol
python3 -B scripts/collect_context.py services/api/main.go --scope services/api --scope packages/shared --symbol Calculate
```

Default limits are 16 source files, 40,000 source bytes, 200 search candidates, and 5 seconds
per search. `--scope` limits path listings and reference searches; connected local imports may
still lead to other packages inside the repository. A directory target returns a file map
without automatically dumping file contents. Dependency directories and build output are
excluded from searches, and search/Git output has size and time limits.

v4 passed **54/54 regression checks** and **57/57 independent API checks** across JS/TS, Go, C,
and Java. Collection limits were also checked with a fixture containing 2,000 unrelated files.
Rust execution and TypeScript static type checking remain unverified.
The [v4 validation report](evals/MULTILANG_20261006.md) distinguishes supported behavior from
checks that were not run.
The next section compares v4 and v5 on actual editing tasks. The v3 records near the end of
this page describe separate experiments and are not pooled with this v4/v5 comparison.

## v5 real-project comparison (2026-10-15)

**v5 succeeded in 9/9 real bug-fix attempts on public projects. v4 also succeeded in 9/9.**
We used pinned historical bugs in `python-dotenv`, `packaging`, and `itsdangerous`, with
three repetitions per version and project: **18 runs** in total. Both versions received the
same model, prompts and initial project files. Automatic skill execution and protected-file
preservation were verified in all nine attempts per version.

### Overall usage: nine-run totals per version

| Metric | v4 | v5 | v5 change |
|---|---:|---:|---:|
| Successful fixes | 9/9 | 9/9 | Unchanged |
| Total tokens: input + output | 1,467,232 | 1,360,626 | 7.27% lower |
| Uncached input tokens | 267,365 | 231,154 | 13.54% lower |
| Agent task time | 667.35s | 608.37s | 8.84% lower |

Total tokens include cached input. Time includes the agent's exploration, edits and own
tests, excluding environment preparation and independent post-run grading. Actual billing
cost was not measured.

### Per-project results: medians of three runs

| Project | v4 total tokens | v5 total tokens | v4 time | v5 time |
|---|---:|---:|---:|---:|
| python-dotenv | 151,161 | 145,102 | 63.9s | 73.4s |
| packaging | 226,724 | 193,253 | 93.6s | 80.5s |
| itsdangerous | 124,943 | 125,527 | 45.0s | 48.1s |

Both versions passed 3/3 attempts on every project. `packaging` used fewer tokens and less
time with v5; the other two projects had higher median task times with v5.

### How to interpret the results

The prespecified comparison takes the v5/v4 ratio for each paired repetition, its median
within each project, then the geometric mean with equal weight for all three projects.
This differs from raw totals or directly dividing the per-version medians above.

| Prespecified metric | Equal-project comparison | Descriptive bootstrap 95% interval | Improvement criterion |
|---|---:|---:|---|
| Total tokens | 5.68% lower | −14.76% to +0.02% | Not met |
| Task time | 1.36% lower | −13.98% to +6.97% | Not met |

An improvement required preserved success, at least 10% fewer tokens or 5% less time,
and an interval upper bound below 0% for the respective metric. Neither metric met these
conditions. With only three projects, the intervals are descriptive measures of variation.

**The workflow worked on these tasks. Consistent token or time improvements were not established.**
One `itsdangerous` v4 run took 99.02s and affected the raw time total. These results cover
three historical public Python bugs on one macOS environment, not other languages, large
repositories or production environments. There was no skill-disabled control.

Settings were `gpt-6-astra / low`, Codex CLI `0.162.1`, Python 3.12 and locked dependencies.
Success required hidden behavioral checks, existing tests, correct import origins and
protected-file preservation. One dotenv test incompatible with macOS was excluded equally
in both versions. There were no failed attempts, timeouts or replacement retries.

[Detailed report and all 18 runs](evals/V5_EXTERNAL_20261015.en.md) ·
[Measurements, environment and audit](evals/v5-external-results.json) ·
[Prespecified evaluation plan](evals/V5_EXTERNAL_PLAN_20261015.md) ·
[Reproducible runner](evals/version_compare.py)

## v5 inspector and installation validation

**Functional checks passed. Speed and output claims are limited to the measured cases.**

| Check | Result | What it establishes |
|---|---:|---|
| Full functional/regression suite | 69/69 passed | 29 existing inspector tests + 15 new tests + 25 evaluation-tool tests |
| Python 3.12 compatibility | 44/44 passed | Inspector and v5 behavior checks |
| Extracted ZIP execution | 44/44 passed | Packaged behavior and skill-format validation |
| Codex and Claude installations | Matching hashes and successful execution | Codex also discovered the new description with the skill enabled |
| Summary output | 61,706 → 7,833 bytes | 87.3% less emitted content in one self-inspection case |

Summary retains the same source paths and hashes while omitting bodies and diffs. The
**87.3% figure measures output bytes**, not model tokens, cost or task accuracy. Read relevant
source and diffs after triage; a summary alone is insufficient for editing.

The helper-only v4/v5 comparison used one warm-up and seven measured runs per condition.
These are medians, not measurements of an AI agent completing an editing task.

| Case | v4 | v5 | Observation |
|---|---:|---:|---|
| Small Python repository | 99.3ms | 99.0ms | 0.3% faster |
| Repeated imports | 101.8ms | 103.4ms | 1.6% slower |
| 2,000 reference files | 271.4ms | 293.9ms | 8.3% slower |
| One-file limit | 88.7ms | 90.5ms | 2.1% slower |
| 12 files in one Go package | 107.3ms | 101.3ms | 5.6% faster |

The helper-only measurements showed both improvements and regressions. **These figures alone
do not establish overall agent speed or token savings.** The initial candidate-selection mismatch
and invalid pilot are preserved.
[Method and limitations](evals/V5_20261015.md) · [Raw measurements](evals/v5-benchmark.json) ·
[Summary comparison](evals/v5-summary-output.json) · [Installation verification](evals/v5-installation.json)

## Helper requirements and limitations

The helper uses Python 3.9 or later, `rg`, and `git`. You can also run it directly from the
project root:

```sh
python3 -B scripts/collect_context.py src/lib.rs --scope src
python3 -B -m unittest evals.test_inspect evals.test_multilang evals.test_v5 -v
```

The helper does not execute project code or read project source outside the repository.
The default source budget is 16 files and 40,000 bytes. It reports omissions, limits, and
search failures. Search results are reference candidates, not a complete call graph.
Investigate reported gaps and run the required language-specific and integration checks.
Staying within collection limits does not establish better performance on large repositories
or guarantee discovery of every affected dependency.

## Update history

- **2026-10-15 · v5 real-project comparison** — Compared v4/v5 across three public projects in 18 runs. Published 9/9 successes for both versions, 7.27% lower total tokens and 8.84% lower total time, alongside the unmet prespecified improvement criteria. [Detailed results and reproduction](evals/V5_EXTERNAL_20261015.en.md)

- **2026-10-15 · v5 website documentation** — Reorganized use cases, installation, quick start and validation in Korean and English, distinguishing output reduction from timing results.

- **2026-10-15 · v5.0.0** — Added Git change selection, summary/JSON output, per-invocation analysis caches and sorted searches. Updated installations and versioned archives; documented both improvements and regressions. [Validation](evals/V5_20261015.md)

- **2026-10-06 · Automatic documentation sync** — Generate the website content from the Korean and English READMEs, with language selection and a table of contents. The blue-and-black design is preserved.
- **2026-10-06 · v4** — Added language and monorepo exploration, repeatable `--scope`, `--symbol`, file maps, and output limits. [Functional validation and limitations](evals/MULTILANG_20261006.md)
- **2026-10-06 · Documentation website** — Connected the Korean and English READMEs, installation instructions, cumulative updates, and validation reports through one project page. [Website source](index.html) · [한국어 README](README.md)
- **2026-10-06 · Website design** — Applied a blue-and-black palette and a documentation-focused layout to the project page. [Project website](https://rem0116kjh.github.io/suffice-patch/?lang=en)
- **2026-10-06 · v3 external repository evaluation** — Completed 24 comparisons on historical problems and a raw-evidence audit, and verified evaluation setup at a new path without additional model calls. [Report](evals/GENERALIZATION_20261006.md) · [Prespecified plan](evals/GENERALIZATION_PLAN_20261006.md) · [All results](evals/runs/generalization-20261006/RESULTS.md)
- **2026-10-06 · v3 optimization** — Reduced duplicate collection work and searches after budget exhaustion, recording helper-only measurements separately from the agent rerun. [Optimization record](evals/OPTIMIZATION_20261006.md)
- **2026-10-03 · v3 automatic selection** — Preserved the Python task comparison with automatic selection, the separate workflow comparison, and failed candidates. [v3 measurements](evals/V3_RESULTS.md)
- **2026-10-03 · v2** — Preserved the decision to stop the research after tokens increased by 5.36%, despite both conditions succeeding in 16/16 attempts. [Detailed results](evals/EVAL_RESULTS.md) · [README at the time](evals/README_V2.md)
- **Initial design · v1 (date not recorded)** — Defined the workflow: intent → context → minimal solution → implementation → verification → stop. [Initial draft](evals/prototype-v1.md) · [v1 record](evals/v1.md)

## Earlier validation records

These results belong to their respective versions and are not combined as evidence for v5.

### Earlier Python-only v3: external repository evaluation (2026-10-06)

Three real historical bugs in `python-dotenv`, `packaging`, and `itsdangerous`, plus one task
requiring no changes, were compared with three repetitions per condition. Across **24 runs
under a plan fixed in advance**, both the skill-enabled and skill-disabled conditions succeeded
in 12/12 attempts. Success required independent behavioral checks, existing tests, and
preservation of unrelated files. Helper execution was confirmed in all 12 automatic-selection
attempts.

| Prespecified primary metric | Automatic selection / disabled | Result |
|---|---:|---|
| Agent execution time | 0.753 (**24.7% lower**) | Improvement criterion met |
| Total tokens | 1.204 (**20.4% higher**) | Improvement criterion not met |
| Correctness | Both conditions succeeded in 12/12 attempts | Same observed success rate |

Ratios were calculated for each paired repetition, reduced to a median per task, then combined
as an equally weighted geometric mean across the four tasks. The task-bootstrap 95% interval
was 0.679–0.836 for execution time and 1.118–1.327 for tokens. Raw totals were 756.9 → 611.2
seconds and 1,176,381 → 1,450,245 tokens. Uncached input tokens also increased, from 239,243
to 326,592. Actual billing costs were not measured.

**This evidence supports shorter execution time on the selected Python maintenance tasks.**
It does not establish token savings or improved correctness. The results come from three
small public repositories on one macOS host using Codex CLI 0.160.0, `gpt-6-astra`, and `low`
reasoning effort. They do not guarantee the same effect for other users, models, languages,
or large repositories. Historical public problems may also have appeared in model training
data.

The [evaluation report](evals/GENERALIZATION_20261006.md),
[prespecified plan](evals/GENERALIZATION_PLAN_20261006.md),
[all 24 results](evals/runs/generalization-20261006/RESULTS.md), and
[raw-evidence audit](evals/runs/generalization-20261006/audit.json) preserve outcomes, usage,
limitations, and reproduction steps. These results are not pooled with the earlier synthetic
task results below.

### Earlier v3: code optimization and rerun (2026-10-06)

The helper was optimized to avoid repeated path discovery, AST analysis, and queue processing,
and to skip searches once the budget was exhausted. Git filters and ripgrep preprocessors
were also prevented from executing. All 12/12 regression checks passed, and the updated
helper was copied to the Codex and Claude installations.

A real Codex inventory-reservation modification task was run once with the skill disabled and
once with automatic selection. Both passed all 3/3 independent checks. Total tokens changed
from **54,549 → 42,875 (21.4% lower)**, execution time from **26.4 → 29.5 seconds**, and tool
events from 4 → 4. Uncached input tokens increased by 5.0%, so these results do not establish
cost savings.

In separate helper-only measurements, execution time decreased by 42.2% on a repeated-import
case and 64.6% on a case with 2,000 caller candidates. A small project took about 10 ms longer.
These are synthetic observations, not evidence of faster end-to-end agent execution. The
[optimization report](evals/OPTIMIZATION_20261006.md) records the tested version, the later
`.pyi` compatibility change, raw measurements, and reproduction commands.

### Earlier v3 measurements (2026-10-03)

Two Python tasks were each compared twice with Codex automatically selecting the final v3
version.

| Metric | Skill disabled | v3 automatic selection |
|---|---:|---:|
| Task success | 4/4 | 4/4 |
| Total tokens | 218,696 | 172,548 (**21.1% lower**) |
| Tool events | 16 | 19 |
| Total measured time | 228 seconds | 270 seconds |

**The observed improvement was token usage. These runs do not support a claim of faster
execution or fewer tool calls.** They used small synthetic tasks with Codex CLI 0.160.0,
`gpt-6-astra`, and `low` reasoning effort, and do not guarantee lower bills or savings across
large real repositories.

A separate workflow comparison of four tasks with two repetitions also passed 8/8 attempts
in both conditions and used 21.6% fewer tokens. That comparison did not include the overhead
of native automatic skill selection. Failed candidates, a pilot excluded because of a
measurement error, detailed figures, and raw evidence are preserved in the
[v3 evaluation report](evals/V3_RESULTS.md).

### Preserved history

v2 maintained the success rate but used 5.36% more tokens. Its stop decision is preserved in
the [v2 README](evals/README_V2.md) and [detailed v2 results](evals/EVAL_RESULTS.md).
The later results belong to a separate v3 experiment resumed at the user's request.
Previous installations are preserved in the
[backup and installation record](evals/installation-v3.json).

## Updating the documentation and website

The Korean website content comes from `README.md`; the English content comes from
`README.en.md`. Edit the relevant file, then commit and push to `main`. GitHub Pages
converts both documents to static HTML and publishes them once the build and deployment
finish.

`index.html` is the template for the blue-and-black design and document navigation.
Edit the introduction, support details, measurements, and updates in the README for the
relevant language. The website table of contents is also generated from README headings.
Edit the template only when changing the design.
