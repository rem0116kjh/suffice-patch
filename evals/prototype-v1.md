---
name: suffice-patch
description: Solve coding changes with sufficient research, bounded scope, and evidence-based completion. Use for implementation and bug fixes where unnecessary context, dependencies, or refactoring would increase cost.
---

# SufficePatch

Deliver the requested behavior with the least total work that proves it correct.
Use this loop for the current task; do not install hooks, persist a mode, or load
other skills merely to execute it.

## Intent → context → solution → plan

1. Identify the requested outcome, acceptance evidence, and relevant safety
   invariants. Honor explicit requirements; YAGNI removes speculative work,
   never requested behavior. Inspect applicable project instructions and existing
   changes before editing; preserve unrelated work.
2. Start at the lowest sufficient context level:
   - **L0:** prompt only, when it contains everything needed.
   - **L1:** 1–3 directly relevant files and their applicable instructions.
   - **L2:** related module, callers, shared helpers, and tests.
   - **L3:** cross-module contracts, configuration, architecture.
   - **L4:** repository-wide investigation.
   Escalate when a concrete unknown blocks correctness; briefly name that unknown.
   Safety or shared contracts can require jumping levels. File counts are guides,
   not caps. Search filenames/symbols before reading bodies; bound search output.
   Trace changed behavior through relevant callers and trust boundaries. Research
   is sufficient once the change location, contract, reuse options, and verification
   path are known and no material correctness or security uncertainty remains.
   Use external primary docs when local evidence cannot settle an API or version
   question. Do not browse registries or inventory the repository by default.
3. Choose the first adequate solution: necessary at all? → existing code →
   standard library → native platform → installed dependency → tiny local edit →
   smallest sufficient implementation. Compare candidates against the actual
   contract, including edge cases; line count never decides correctness.
4. Budget the change: reuse existing code → use an existing dependency →
   stdlib/native → local modification → small helper → new abstraction → new
   dependency → architecture change. This orders change risk, not mandatory
   attempts: existing project usage usually beats introducing a new pattern;
   stdlib/native beats an otherwise equivalent unused dependency API. Each step
   down needs stronger evidence that cheaper choices cannot meet the contract.
   Before adding a helper, wrapper, abstraction, configuration layer, dependency,
   speculative feature, unrelated refactor, or architecture change, ask whether
   it is necessary for this request. If not, omit it.
5. Pick the smallest change and a check that could falsify it. A trivial task
   needs only a mental plan; multi-step work gets a short plan, not new planning
   files. Reproduce bugs or add a regression test first when needed to establish
   the failure and protect changed logic. Reuse the existing test infrastructure.

## Implement → verify

Fix the cause at the appropriate shared boundary, including affected callers.
Do not code-golf or replace proven primitives with fragile custom code.
Never trade away authentication, authorization, trust-boundary validation,
security checks, data-loss prevention, transaction integrity, accessibility,
required error handling, or tests needed to establish correctness.

Review the resulting diff for scope, changed contracts, edge cases, and those
invariants. Run the cheapest checks that establish the acceptance evidence:
syntax/type → targeted test → module tests → integration → full suite.
Skip inapplicable rungs; syntax alone does not prove behavior. Use broader checks
for shared contracts, security-sensitive changes, uncertain impact, or explicit
project requirements. UI behavior may require browser/keyboard checks; migrations
may require rollback/integrity checks. Keep required repository checks.
A failed check informs the next fix; rerun affected checks. Broaden or repeat
only for new evidence, remaining risk, or a requirement. Missing tools or an
unrun check means unverified, never passed. Do not weaken tests to obtain green.

## STOP

Stop when the requested behavior is implemented, sufficient checks pass, the
review finds no unresolved material issue introduced by this change, and the
diff contains only necessary work. Report outcome, verification, and remaining
limitations concisely. Do not append optional refactoring, abstraction, docs,
dependencies, architecture work, or another review cycle after this gate.

If blocked, state the missing evidence or prerequisite; do not declare success
because a budget was exhausted. Continue authorized independent work if possible.
Remember a reusable lesson only when explicitly requested, using the existing
memory mechanism and non-sensitive evidence. Improve this skill only through a
separate requested evaluation; no automatic transcript capture or self-rewriting.
