---
name: suffice-patch
description: Collect bounded source, local dependencies, reference candidates, project instructions, and Git changes for focused repository edits across languages and monorepos.
metadata:
  version: "5.0.0"
---

# SufficePatch

Use the bundled read-only inspector from the project root. Python runs the
inspector; the project can use any supported language.

```sh
python3 -B <skill-dir>/scripts/collect_context.py packages/web/src/cart.ts --scope packages/web
python3 -B <skill-dir>/scripts/collect_context.py --changed all --scope packages/web
```

`<skill-dir>` is this skill's directory. Pass named files and explicitly requested
counterparts. Python module/function names also work. With no known files, pass a
directory for a bounded file map, then choose files based on the task:

```sh
python3 -B <skill-dir>/scripts/collect_context.py . --scope packages/api
```

For existing changes, use `--changed all`, `staged`, or `worktree`. Untracked
files require `--include-untracked`; source bodies always reflect the working
tree, even with `staged`. Deleted files retain diff and filename-reference hints.
`--summary` returns paths/hashes without bodies or diffs; use it for triage, then
read full context before editing. `--format json` enables structured consumers.
Read [CLI details](references/cli.md) for these modes and the JSON contract.

The inspector reads source, resolvable local imports, matching references/tests,
ancestor `AGENTS.md`, nearby manifests, bounded Git status and file-scoped diffs.
Use its output directly. Python imports use AST; other imports are limited
static hints. Candidates are not a complete dependency graph. Follow reported
alias, generated-code, build-tag and dynamic-reference gaps with targeted reads.

Repeat `--scope` for relevant packages. It bounds discovery, references and
automatic changed-file selection; connected local imports can cross scopes
inside the repository. Explicit targets are retained regardless of scope.
Use `--symbol` to narrow ambiguous references. Default limits are 16 source files,
40,000 source bytes, 200 search candidates, and 5 seconds per search. Directory
maps do not load file contents. Increase limits only when the missing evidence
justifies it. Divide larger work by dependency or behavior, then run the required
integration checks across affected packages; do not treat one bounded read as a
whole-repository review.

Read declared project commands before executing them. The inspector never runs
project code or installs dependencies. Use the project's actual tooling and
required integration/data-integrity checks. Preserve unrelated work and already
correct code. Keep dependent edits and checks sequential; stop on failure.
Report changed behavior, actual checks and coverage limits. Performance evidence
is version-specific; using this helper alone does not prove token or time savings.
