---
name: suffice-patch
description: Reduce tool round trips for localized maintenance in identified files or functions while preserving behavioral checks.
---

# SufficePatch

For a localized fix, prefer an inspection call followed by an edit-and-check call.
Extra calls are appropriate when evidence, safety, or project instructions require them.

The inspection must return source contents, not just filenames. Start with the
named file or module (`api.customer_label` suggests `api.py`); include relevant
Git changes, project instructions, and known callers/tests. If locating files is
necessary, locate and read matching sources in that same call. Avoid unrelated files.

Once the change is understood, execute the edit, focused behavioral checks, and
final diff sequentially in one tool request, stopping on failure. A small shell/Python
replacement must assert a unique exact old-text match before writing; otherwise use
the normal patch tool. Preserve unrelated work and never overwrite unseen contents.
Use `python3 -B` for local Python checks to avoid creating bytecode cleanup work.

If already correct, verify without changes. Keep required tests; broaden checks for
shared contracts, authorization, data integrity, unclear behavior, or failures.
Never trade correctness for a call target. Report actual checks and unresolved limits.
