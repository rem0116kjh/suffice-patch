---
name: suffice-patch
description: For code, test, configuration, and documentation changes across languages and monorepos, collect bounded source, local dependencies, textual references, project instructions, and Git changes before editing. Use for focused fixes or successive parts of larger repository work.
---

# SufficePatch

Use the bundled read-only inspector from the project root. Its Python runtime
is an implementation detail; the inspected project can use other languages.

```sh
python3 -B <skill-dir>/scripts/collect_context.py packages/web/src/cart.ts --scope packages/web
python3 -B <skill-dir>/scripts/collect_context.py src/lib.rs include/parser.h
```

`<skill-dir>` is this skill's directory. Pass named files and explicitly requested
counterparts. Python module/function names also work. With no known files, pass a
directory for a bounded file map, then choose files based on the task:

```sh
python3 -B <skill-dir>/scripts/collect_context.py . --scope packages/api
```

The inspector reads source, local dependencies where resolvable, matching
references/tests, ancestor `AGENTS.md`, nearby manifests, and scoped Git changes.
Use the output directly; read its implementation only to debug the inspector.
Python imports use AST; JS/TS, Go, Rust, and C/C++ use limited static heuristics.
Other text formats use textual symbols/references. Treat candidates as evidence
to inspect, not a complete dependency graph. Resolve reported aliases, generated
code, build tags, dynamic references, or omitted files with targeted reads.

For a large repository, repeat `--scope` for relevant packages; connected local
imports may cross these search scopes but remain inside the repository root.
Use `--symbol` to narrow ambiguous references. Default limits are 16 source files,
40,000 source bytes, 200 search candidates, and 5 seconds per search. Directory
maps do not load file contents. Increase limits only when the missing evidence
justifies it. Divide larger work by dependency or behavior, then run the required
integration checks across affected packages; do not treat one bounded read as a
whole-repository review.

Edit and verify using the project's actual language and declared tooling. Read
relevant manifest scripts before running them; the inspector never runs project
code, installs dependencies, or chooses a test command for you. Keep required
project checks and data-integrity tests. Preserve unrelated work and leave
already-correct code unchanged. When grouping edit/check/diff steps, keep them
sequential and stop on failure. Assert a unique old-text match for replacements,
or use the normal patch tool. Report changed behavior, actual checks, and any
remaining coverage or environment limits. Do not infer token or time savings
from using the helper; performance evidence is specific to its tested version.
