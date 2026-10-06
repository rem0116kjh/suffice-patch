# python-dotenv: preserving backslashes through writing and parsing

Prepared on 2026-10-06 (Asia/Seoul), before any native model trials for this task.

## Upstream source

- Repository: <https://github.com/theskumar/python-dotenv>
- Reported defect: <https://github.com/theskumar/python-dotenv/issues/661>
- Pinned base: [`751f8c148222e58aa173c83c4e5e6cfccb2cc124`](https://github.com/theskumar/python-dotenv/commit/751f8c148222e58aa173c83c4e5e6cfccb2cc124)
- Reference fix: [`f7b18d9c72d1abcc2ad4023424b84f5bee30d266`](https://github.com/theskumar/python-dotenv/commit/f7b18d9c72d1abcc2ad4023424b84f5bee30d266), authored/committed 2026-08-16.

The official GitHub issue and commit were opened with the browser tool. A fresh public Git clone independently verified the complete hashes, the parent relationship, and the actual changed source. The defect was already present upstream; no bug was inserted for this experiment. The fix changes the writer in `src/dotenv/main.py` and quoted-value recognition in `src/dotenv/parser.py`. The task prompt describes the observable behavior and affected locations without providing the patch, fix hash, or issue URL.

The pinned base contains **46 tracked files**, **20 Python files**, and **8 Python files under `src/`**, totaling 162,285 tracked file bytes. This is a small real repository, not evidence about large repositories.

## Independent judge

`grader.py` is a new, deterministic behavioral judge, not a copy of the reference patch or its test diff. It runs offline from stdin with the candidate's `src/` on `PYTHONPATH`. It checks:

- 52 write/read scenarios: 13 fixed values, two quoting modes, and append/replacement operations, with export handling and unrelated bindings preserved.
- 12 direct parser scenarios: both quoting styles, three backslash-run lengths, and both end-of-file variants, checking that a following assignment and its line number survive.
- One preservation check for `quote_mode="never"`.

These **65 scenarios are one bug-fix task**, not 65 independent tasks or users. The values include repeated/trailing backslashes, adjacent quotes, multiline text, and non-ASCII text. A write is followed by another write to test persistence of the first value. Success also requires the separately executed existing upstream tests and the harness's preservation of files outside the allowed edit scope.

## Control validation

The full output, package freeze, interpreter, hashes, and commands are recorded in `reference_validation.json`.

| Pinned source | Independent judge | Compatible upstream tests | Entire unchanged upstream suite |
| --- | --- | --- | --- |
| Base parent | 25/65 pass; 40 fail | 222 pass; 1 deselected | 222 pass; 1 fail |
| Upstream reference fix | 65/65 pass | 240 pass; 1 deselected | 240 pass; 1 fail |

The identical whole-suite failure is the historical `tests/test_cli.py::test_run_with_command_flags`: it assumes GNU `printenv --version`, whereas macOS ships BSD `printenv`, which rejects that option. The one test is excluded by name **before native trials**; no test files are modified. The reference revision includes 18 added upstream tests, explaining the different test counts. Remaining CLI tests, IPython integration, FIFO tests, and library tests run normally. This is a qualified suite result, not a claim that the entire historical suite passed on macOS.

Validation used native macOS arm64 **Python 3.12.14** for this pure Python library, with `pytest==9.1.1`, `click==8.5.0`, and `ipython==9.17.1`. No x86 Linux binary or debugger is involved. The base package is installed into the isolated venv to provide the `dotenv` console entry point; an absolute candidate `PYTHONPATH` takes precedence for both direct imports and CLI subprocesses.

## Reproduction

Preparation checkout: `/tmp/suffice-dotenv-prep-20261006` (left at the pinned base).

Preparation interpreter: `/tmp/suffice-dotenv-prep-py312-20261006/bin/python`.

For a fresh checkout at either pinned revision, create a Python 3.12 venv, install the three pinned dependencies and the base package, then set `PYTHONPATH` to that checkout's absolute `src` directory and prepend the venv's `bin` directory to `PATH`. From the checkout root:

```sh
python -B - < /absolute/path/to/evals/external_tasks/dotenv/grader.py
python -m pytest -q -k 'not test_run_with_command_flags'
```

The evaluation harness must give each arm a new archive of the base with a fresh Git history. It must not copy this grader, provenance, reference validation, or reference commit into the task workspace. Allowed modifications to existing files are limited to the two source files; adding tests is permitted, changing existing tests is not.

## Limits

This is a deliberately selected, localized Python bug with named source files. Public historical code and its solution may occur in model training data, so memorization cannot be excluded even when future Git history and network access are hidden during trials. The same dependency environment must be used in both arms. Results cannot establish benefits for other languages, large projects, individual human users, other agent models, or general execution cost. All prepared tasks and both successful and unsuccessful trials should be retained when reporting the aggregate.
