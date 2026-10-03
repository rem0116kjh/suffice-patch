---
name: suffice-patch
description: Make focused coding changes using only the evidence, edits, and checks needed for safe completion. Use for bounded fixes and implementation work.
---

# SufficePatch

Use the smallest evidence, change, and verification sufficient to safely satisfy
the request. Follow applicable project instructions and preserve unrelated work.

**Fast path:** When the location is clear and the change is local, with no new
dependency, architecture, public API, migration, or security boundary involved,
read the relevant file, make the obvious edit, run the nearest meaningful check,
and stop. Keep the plan mental. Batch independent state checks and relevant reads;
do not spend a separate call listing files whose paths are already known.

**Search until sufficient, not certain.** Read direct dependencies or callers only
to resolve a specific uncertainty. Before another search, identify what decision
its result could change; otherwise omit it. Broaden scope when evidence exposes
shared behavior or a safety risk.

Reuse existing code and established dependencies; otherwise prefer standard
library or native features. Add a helper, wrapper, dependency, configuration,
refactor, or abstraction only when necessary for the requested behavior.

**Verify nearest, then stop.** Choose a check that could falsify the change;
syntax alone does not prove behavior. Run a pre-fix reproduction when the cause
or regression coverage is uncertain, not ceremonially. Add necessary regression
coverage. Broaden checks for shared modules, public APIs, cross-module behavior,
security boundaries, data integrity, failed targeted checks, or project mandates.
Review the patch while checking it; do not repeat passed checks without changed
code or unresolved risk.

Never trade away authentication, authorization, trust-boundary validation,
security, data-loss prevention, transaction integrity, accessibility, required
error handling, or correctness tests.

Stop when the requested behavior and safety obligations have adequate evidence.
Report the result, actual verification, and remaining limitations. No optional
cleanup, documentation, extra review, or speculative features. An unresolved
requirement means incomplete, not success.
