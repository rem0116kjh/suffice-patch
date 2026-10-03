---
name: suffice-patch
description: Reduce tool round trips when fixing localized bugs or making small code changes in identified files or functions.
---

# SufficePatch

For localized maintenance, spend tool calls on evidence and behavior, not orientation.

When the request names files, include their contents, applicable project instructions,
and relevant Git status/diff in the first inspection call. Avoid a separate pwd or
directory-listing round. Search only for missing targets, callers, or dependencies
needed to decide the change.

After inspection, compose the edit, focused behavioral checks, and final diff into
one tool request when supported, executing them sequentially and stopping on failure.
For a small exact replacement, a shell/Python edit must assert that the expected
old text occurs exactly once before writing. Otherwise use the normal patch tool.
Preserve unrelated changes; never rewrite unseen contents. Do not add a helper or
dependency merely to batch commands.

If already correct, verify and leave files unchanged. Keep required tests and project
checks. Broaden investigation or verification for shared contracts, authorization,
data integrity, unclear behavior, or failures; never enforce a call budget at their
expense. Report actual results and unresolved limits, then stop.
