# Native automatic-selection smoke comparison, 2026-10-06

One preselected `inventory` task was run once per arm, baseline then implicit,
with Codex CLI 0.160.0, `gpt-6-astra`, low reasoning effort. No reruns or outcome
selection. Both arms received identical prompt text and passed all three
independent assertion groups. Only `inventory.py` changed; the three unrelated
fixture files and copied skill bundle remained intact.

| Metric | Baseline | Automatic skill | Change |
|---|---:|---:|---:|
| Input + output tokens | 54,549 | 42,875 | -21.40% |
| Input tokens | 53,769 | 41,960 | |
| Cached input tokens (included above) | 39,168 | 26,624 | |
| Uncached input tokens | 14,601 | 15,336 | +5.03% |
| Output tokens | 780 | 915 | |
| Reasoning output tokens (included above) | 30 | 42 | |
| Reported cache-write input tokens | 0 | 0 | |
| Elapsed seconds | 26.441 | 29.470 | +11.46% |
| Tool events | 4 | 4 | 0% |
| Independent assertion groups | 3/3 | 3/3 | |
| Changed files | 1 | 1 | |
| Added lines | 2 | 1 | |

The implicit trace contains a successful read of the repository `SKILL.md`
and a successful execution of `collect_context.py inventory.py` returning
the target source and Git context. The baseline trace contains neither.
Discovery was separately verified before model calls: the host copy was
disabled in both arms, and the repository copy was enabled only in implicit.
Plugins, hooks, apps, memories, web search, and multi-agent were disabled;
other installed local skill metadata remained discoverable in both arms.

The skill worked and reduced observed total tokens for this one task. It
did not reduce tool events or elapsed time. Uncached input increased, so this
does not establish a dollar-cost reduction. This single pair cannot establish
statistical significance, broad task performance, or the optimization's
incremental effect versus the previous helper version.

All five usage fields in the table were explicitly present in the CLI's raw
`turn.completed.usage` objects. The zero cache-write values are reported
values, not substitutes for missing data. Cached input and reasoning output
are subsets and are not added to total tokens again. Tool events count
completed command/file-change items, not subprocesses: baseline used three
commands plus one file-change event; implicit used four commands.

Evaluated helper SHA-256:
`76c6314d8574b1514b827c1d45c425dfd0182e3cab8aa7ee8097c9e182ffc54c`.
Evaluated SKILL.md SHA-256:
`f365978b6a24b55d5312dd551cfb7f0a5775595ffd6b8205162cb1df973f9ea1`.
The helper was staged after the final `rg --no-config` and Git literal-pathspec
flags, then discovery was refreshed before model calls. A subsequent `.pyi`
compatibility fix is outside the evaluated helper hash; no native model rerun
is claimed for that later patch. Its inventory context equivalence can be
verified separately without reusing or changing these measured traces.

Evidence: `manifest.json`, `audit.json`, the two `events.jsonl`, `result.json`,
and `changes.diff` files. Reproduce the audit with:

```sh
python3 -B evals/runs/optimization-native-20261006/audit.py
```

Discovery evidence and its source are in
`../optimization-20261006/native-discovery.json` and `probe_native.py`.
The frozen two-file bundle is in `../optimization-20261006/bundle/`.
