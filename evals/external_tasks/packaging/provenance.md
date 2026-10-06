# packaging: epoch-aware wildcard matching

Selected on 2026-10-06 before any evaluated model run. This is an actual historical bug, not an injected mutation. [Issue #683](https://github.com/pypa/packaging/issues/683) reports incorrect prefix matching when the specifier has more release components than the candidate and an epoch is present. [PR #712](https://github.com/pypa/packaging/pull/712) was merged on 2023-10-02. Its [merged commit](https://github.com/pypa/packaging/commit/c52d2b30465ace6d11f54c01b6ea30419a94b5ef) changes production version matching and adds three upstream regression cases. These official pages were fetched and checked during task preparation; the full Git parent relationship and diff were checked locally.

- Repository: `https://github.com/pypa/packaging.git`
- Base: `cc0c65cb43537491ba468da1ba9b9f49c932d9eb`
- Reference: `c52d2b30465ace6d11f54c01b6ea30419a94b5ef`
- Base size: 84 tracked files, including 31 Python files.
- Allowed production path: `src/packaging/specifiers.py`.
- Runtime dependencies: none. Grading checks use the standard library and the checkout's package only.
- Tests: full upstream suite, not a handpicked subset; run with Python 3.12.14 and the dependency pins in `task.json` / `reference_validation.json`.

The independent grader exercises public `Specifier` and `SpecifierSet` APIs using multiple epochs, release widths, inclusion/exclusion, version objects, filtering, suffixes, local versions, and compatible release boundaries. It does not inspect or require a particular implementation. It asserts imports came from the checkout. The installed `packaging==26.3` is a pytest dependency; `PYTHONPATH=src` shadows it for both tests and grading. Two hundred and two assertions are checks within one task, not 202 independent coding tasks.

Validation was run in a dedicated `/tmp` Python virtual environment. No project source or upstream tests were edited for validation. The base grader fails 77 of 202 checks; the reference passes all 202. The base upstream suite passes 26,824 tests and skips one; the reference suite passes 26,827 and skips one. Full raw outputs and exit codes are retained here. The preparation checkout is restored to the base commit with clean Git status.

```sh
cd /tmp/suffice-packaging-prep
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  /tmp/suffice-packaging-venv/bin/python -m pytest -q
PYTHONPATH=src /tmp/suffice-packaging-venv/bin/python -B - \
  < /Users/luka/Desktop/ctf/suffice-patch/evals/external_tasks/packaging/grader.py
```

For evaluated agents, export only the pinned base tree into a fresh repository without upstream history. Keep this directory, the grader, upstream reference commit, and provenance outside the agent workspace. The task prompt gives behavior and a starting symbol, but contains no implementation, issue link, or reference hash. Preserve existing tests and instructions, permit added tests, and verify changed source paths independently. Public historical tasks can overlap model pretraining; this is evidence about this workflow on the selected task, not proof of unseen-bug performance or universal effectiveness.
