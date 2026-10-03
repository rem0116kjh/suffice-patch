---
name: suffice-patch
description: Complete focused coding changes with the smallest sufficient evidence, edit, and verification.
---

# SufficePatch

Use the smallest evidence, change, and verification sufficient to safely satisfy
the request, then stop. Follow project instructions and preserve unrelated work.

Fast path: for a clear local change without new dependencies, architecture changes,
public API changes, migration, or security impact, read the relevant file, edit,
run the nearest meaningful check, and stop. Batch independent reads and checks.

Search only when the answer could change the implementation or safety decision.
Reuse existing code, dependencies, or standard/native facilities. Omit optional
helpers, refactoring, documentation, and features.

Check behavior, not just syntax. Broaden verification only for shared contracts, cross-module effects, security,
data integrity, failed checks, or project requirements. Never sacrifice
authentication, authorization, security validation, trust-boundary validation, data-loss prevention,
transaction integrity, accessibility, required error handling, or correctness
tests. Review the patch with verification. Report actual checks and unresolved
limitations; incomplete is not success.
