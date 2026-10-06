[한국어](README.md) | English

# SufficePatch v4

[Project website](https://rem0116kjh.github.io/suffice-patch/) · [Website source](index.html) · [Updates](https://rem0116kjh.github.io/suffice-patch/#updates)

A Codex/Claude skill that collects a bounded set of files and references for changes to code,
tests, configuration, and documentation across multiple languages. It guides package-level
exploration in monorepos, divides larger changes into manageable parts, and finishes with
integration checks. The helper is written in Python, but target projects do not have to use
Python. Automatic skill selection remains enabled.

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
**The time and token measurements below belong to the earlier Python-only v3; they are not
performance evidence for v4.** Token savings and execution-time improvements for v4 have not
yet been measured in a controlled comparison.

## Earlier Python-only v3: external repository evaluation (2026-10-06)

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

## Earlier v3: code optimization and rerun (2026-10-06)

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

## Earlier v3 measurements (2026-10-03)

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

## Usage

Describe the files, behavior, and target packages you want to change. Codex may automatically
select the skill for a relevant request; selection is not guaranteed. You can also invoke it
explicitly:

```text
$suffice-patch Update cart calculations in packages/web and validation in services/api together. Preserve the existing response format.
```

In Claude Code, invoke `/suffice-patch` explicitly. Claude's functional checks and Codex's
comparative measurements are separate evidence; token savings in Claude have not been
measured.

Current installation locations:

- Codex: `~/.agents/skills/suffice-patch/`
- Claude: `~/.claude/skills/suffice-patch/`

For a new installation, **copy both `SKILL.md` and `scripts/`**. The
[installation ZIP](dist/suffice-patch.zip) contains the current v4 `SKILL.md` and its two Python
helper files. You do not need to add Python code to your project. Linux, Windows, and
installations by other users have not been tested. Do not add configuration that disables
automatic selection.

```sh
mkdir -p "$HOME/.agents/skills/suffice-patch/scripts"
cp SKILL.md "$HOME/.agents/skills/suffice-patch/SKILL.md"
cp scripts/collect_context.py scripts/context_languages.py "$HOME/.agents/skills/suffice-patch/scripts/"
```

## Helper requirements and limitations

The helper uses Python 3.9 or later, `rg`, and `git`. You can also run it directly from the
project root:

```sh
python3 -B scripts/collect_context.py src/lib.rs --scope src
python3 -B -m unittest evals.test_inspect evals.test_multilang -v
```

The helper does not execute project code or read project source outside the repository.
The default source budget is 16 files and 40,000 bytes. It reports omissions, limits, and
search failures. Search results are reference candidates, not a complete call graph.
Investigate reported gaps and run the required language-specific and integration checks.
Staying within collection limits does not establish better performance on large repositories
or guarantee discovery of every affected dependency.

## Preserved history

v2 maintained the success rate but used 5.36% more tokens. Its stop decision is preserved in
the [v2 README](evals/README_V2.md) and [detailed v2 results](evals/EVAL_RESULTS.md).
The later results belong to a separate v3 experiment resumed at the user's request.
Previous installations are preserved in the
[backup and installation record](evals/installation-v3.json).
