---
name: suffice-patch
description: Inspect localized Python maintenance targets, local dependencies, callers, tests, and Git changes in one call, then make and verify a focused fix.
---

# SufficePatch

For localized Python maintenance, start with the bundled read-only inspector:

```sh
python3 -B <skill-dir>/scripts/collect_context.py target.py other_module
```

`<skill-dir>` is this skill's directory. Pass the named targets and any explicitly
requested counterpart, such as the web view. The inspector returns source,
local imports, matching callers/tests, project instructions, and Git changes.
Use its output directly; inspect the script itself only when debugging it.
Follow reported limits or missing evidence with a targeted read.

After inspection, execute the focused edit, behavioral checks, and final diff
sequentially in one tool request when possible, stopping on failure. Assert a
unique exact old-text match before a shell/Python replacement; otherwise use the
normal patch tool. Use `python3 -B` for checks. Preserve unrelated changes and
leave already-correct code unchanged. Keep required project checks, authorization,
and data-integrity tests. Broaden work when evidence requires it, never to meet a
call target. Report actual results and unresolved limits.
