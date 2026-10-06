# itsdangerous historical external task

Prepared 2026-10-06 (Asia/Seoul). This is an actual historical upstream bug, not an injected mutation. Repository: [pallets/itsdangerous](https://github.com/pallets/itsdangerous).

- [Upstream PR 296](https://github.com/pallets/itsdangerous/pull/296), merged March 9, 2022, describes a bad signed timestamp reaching `datetime.fromtimestamp` and leaking `ValueError` during Flask session loading.
- Base: [`85b1e3b76e0e37473dc286450ada725cd02981b4`](https://github.com/pallets/itsdangerous/commit/85b1e3b76e0e37473dc286450ada725cd02981b4). It adds the upstream failing regression but does not fix the production code.
- Reference fix and direct child of base: [`37f09970fa32a330a6660ded3abdb264086531b5`](https://github.com/pallets/itsdangerous/commit/37f09970fa32a330a6660ded3abdb264086531b5). It updates `TimestampSigner.unsign` in `src/itsdangerous/timed.py` and the changelog.
- The PR and commit pages were read with the web tool, and the commit parent and source diff were independently verified in the official cloned Git repository.

At the base there are **57 tracked files, 16 Python files, and 8 production Python files**. This is a small real Python library. It does not substantiate large-repository, cross-language, cross-platform, or unseen-benchmark claims. Since the bug and solution have been public since 2022, model training contamination is possible and cannot be excluded.

## Contract and evaluation

`task.json` names the affected public function and required behavior without exposing the reference commit or patch in the agent-facing prompt. Agents may modify only `src/itsdangerous/timed.py`; existing tests are immutable. All graders remain outside the agent checkout, supplied over standard input after the attempt. The target repository must be on `PYTHONPATH=src` when grading.

The independent grader creates its own invalid tokens with stdlib base64 encoding. It covers four out-of-range timestamps and three payload shapes; correct exception type, preserved payload, unset signing date; `validate` and `TimedSerializer` callers; preserved metadata for ordinary invalid signatures; valid signatures at the exact expiration boundary; expired signatures; and propagation of an unrelated converter error. This gives 30 grouped checks. These cases were not copied from the upstream regression token. Grader counts represent checks, not independent task samples.

`noop.json` uses the fixed source and an already-satisfied expiration contract. Its 52 grouped checks cover empty/text/dotted/Unicode payloads, age exactly equal to `max_age`, valid younger signatures, future and expired signatures, UTC timestamps, and signatures without a maximum age. The harness must also require an unchanged checkout: behavior alone cannot enforce the no-op condition.

The original upstream regression remains visible to the agent. This is a realistic reproduction-plus-fix task, not a claim that the model inferred an undisclosed failure from symptoms alone.

## Reproduction and measured reference verification

Preparation checkout: `/tmp/suffice-itsdangerous-prep`. Isolated Python: `/tmp/suffice-itsdangerous-py312/bin/python`, Python 3.12.14 on macOS arm64. Dependencies: `pytest==8.3.5`, `freezegun==1.5.1`; the full resolved dependency list is recorded in `reference_validation.json`. No package installation into the global interpreter was performed. The code is portable Python and does not execute any Linux binary.

From a clean checkout at the selected revision:

```sh
PYTHONPATH=src /tmp/suffice-itsdangerous-py312/bin/python -m pytest -q tests
PYTHONPATH=src /tmp/suffice-itsdangerous-py312/bin/python -m pytest -q tests/test_itsdangerous/test_timed.py
PYTHONPATH=src /tmp/suffice-itsdangerous-py312/bin/python - < /path/to/external_tasks/itsdangerous/grader.py
```

| Revision | Independent bug grader | Full upstream suite |
| --- | --- | --- |
| Base `85b1e3b` | Fails with `ValueError: year 10000 is out of range` | 1 failed, 296 passed in 0.53 s |
| Reference `37f0997` | 30 / 30 grouped checks passed | 297 passed in 0.43 s |
| No-op at `37f0997` | 52 / 52 grouped checks passed | Same fixed-source upstream suite passed |

Raw commands, exit statuses, stdout, stderr, dependency versions, and source file counts are in `reference_validation.json`. These measurements verify the task and grader; they are not agent performance measurements. No native agent model calls were made during preparation.

The selected reference fix handles `ValueError` on the measured macOS runtime. Upstream later added separate Windows `OSError` and 32-bit `OverflowError` handling. This task deliberately evaluates the year-range `ValueError` contract and makes no Windows or 32-bit validation claim.
