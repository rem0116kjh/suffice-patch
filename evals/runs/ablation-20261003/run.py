#!/usr/bin/env python3
"""Reproducible local Codex pilot, not a general agent framework. No packages."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

from tasks import DISTRACTORS, TASKS

ROOT = Path(__file__).resolve().parents[1]
COMMON = """Complete the coding task in this working directory. You may inspect,
edit and run local checks. Preserve unrelated work. Do not commit, push, install
dependencies, spawn agents, access other directories, or use the network.
Use the available Python standard library for Python checks. Report what changed
and what you actually verified. Do not read hidden evaluator files.
"""
COMPRESSED = """Use the smallest evidence, change, and verification sufficient to safely
satisfy the request, then stop. Reuse existing code. Follow project instructions
and preserve unrelated work. Never sacrifice authentication, authorization,
trust-boundary validation, data integrity, accessibility, required error handling,
or correctness tests. Report actual verification and unresolved limitations."""


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def seed(folder, task):
    for name, content in {**DISTRACTORS, **task["files"]}.items():
        (folder / name).write_text(content)


def grade(folder, task):
    """Run each independent assertion group in a fresh process; fail closed."""
    results = []
    for code in task["checks"]:
        try:
            p = subprocess.run([sys.executable, "-B", "-c", code], cwd=folder,
                               capture_output=True, text=True, timeout=10)
            results.append({"passed": p.returncode == 0, "error": p.stderr[-2000:]})
        except subprocess.TimeoutExpired:
            results.append({"passed": False, "error": "grader timeout"})
    return results


def selftest():
    for name, task in TASKS.items():
        with tempfile.TemporaryDirectory(prefix="suffice-grader-") as d:
            p = Path(d)
            seed(p, task)
            original = grade(p, task)
            assert all(x["passed"] for x in original) == (name == "noop"), name
            for file, content in task["good"].items():
                (p / file).write_text(content)
            good = grade(p, task)
            assert all(x["passed"] for x in good), (name, good)
            # Ensure a shorter broken implementation is never rewarded.
            target = next(iter(task["good"] or {"tags.py": ""}))
            (p / target).write_text("")
            assert not all(x["passed"] for x in grade(p, task)), name
    assert parse_events('{"type":"turn.completed","usage":{"input_tokens":9,"cached_input_tokens":3,"output_tokens":2}}')["input_tokens"] == 9
    assert parse_events('{"type":"turn.failed"}')["input_tokens"] is None
    print(f"PASS: {len(TASKS)} graders accept known-good, reject broken/empty code; missing usage is unknown.")


def parse_events(raw):
    events = []
    for line in raw.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    usages = [e["usage"] for e in events if e.get("type") == "turn.completed" and "usage" in e]
    items = [e["item"] for e in events if e.get("type") == "item.completed" and "item" in e]
    names = ["input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens", "reasoning_output_tokens"]
    result = {k: sum(u.get(k, 0) for u in usages) if usages else None for k in names}
    result["completed"] = bool(usages) and not any(e.get("type") == "turn.failed" for e in events)
    result["tool_calls"] = sum(i.get("type") not in {"agent_message", "reasoning", "error"} for i in items)
    result["commands"] = [i["command"] for i in items if i.get("type") == "command_execution"]
    result["tool_output_bytes"] = sum(len(i.get("aggregated_output", "").encode()) for i in items)
    return result


def snapshot(folder):
    return {str(p.relative_to(folder)): p.read_text(errors="replace") for p in folder.rglob("*")
            if p.is_file() and not any(x in {".git", "__pycache__", ".pytest_cache"} for x in p.relative_to(folder).parts)}


def diff_metrics(before, after):
    files = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    patches, counts = [], {"loc_added": 0, "loc_deleted": 0, "test_loc_added": 0, "test_loc_deleted": 0}
    for file in files:
        diff = list(difflib.unified_diff(before.get(file, "").splitlines(True), after.get(file, "").splitlines(True),
                                         fromfile="a/" + file, tofile="b/" + file))
        patches.extend(diff)
        test = file.startswith("tests/") or Path(file).name.startswith("test_") or Path(file).name.endswith("_test.py")
        for line in diff[2:]:
            key = "loc_added" if line.startswith("+") else "loc_deleted" if line.startswith("-") else None
            if key:
                counts[key] += 1
                if test:
                    counts["test_" + key] += 1
    return {**counts, "files_modified": len(files), "modified_paths": files}, "".join(patches)


def run_one(folder, task, instruction, args):
    folder.mkdir(parents=True)
    work = folder / "workspace"
    work.mkdir()
    seed(work, task)
    for git_args in [["init", "-q"], ["add", "."],
                     ["-c", "user.name=Eval Fixture", "-c", "user.email=eval@invalid.local",
                      "-c", "core.hooksPath=/dev/null", "commit", "-qm", "fixture"]]:
        subprocess.run(["git", *git_args], cwd=work, check=True, capture_output=True)
    before = snapshot(work)
    prompt = COMMON + "\n" + ("Task workflow:\n" + instruction + "\n" if instruction else "") + "\nTask:\n" + task["prompt"]
    command = ["codex", "exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check", "--json",
               "-s", "workspace-write", "-m", args.model, "-C", str(work)]
    config = {"model_reasoning_effort": args.effort, "approval_policy": "never", "web_search": "disabled",
              "project_doc_max_bytes": 0, "suppress_unstable_features_warning": True,
              "features.skip_host_skill_discovery": True, "features.plugins": False, "features.hooks": False,
              "features.apps": False, "features.multi_agent": False, "features.memories": False}
    for key, value in config.items():
        command += ["-c", key + "=" + json.dumps(value)]
    command += ["-"]
    start = time.monotonic()
    with (folder / "events.jsonl").open("w") as out, (folder / "stderr.log").open("w") as err:
        p = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out, stderr=err, text=True,
                             start_new_session=True)
        timed_out = False
        try:
            p.communicate(prompt, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(p.pid, signal.SIGTERM)
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
    duration = time.monotonic() - start
    after = snapshot(work)
    metrics, diff = diff_metrics(before, after)
    (folder / "changes.diff").write_text(diff)
    usage = parse_events((folder / "events.jsonl").read_text())
    checks = grade(work, task)
    protected = all(after.get(f) == content for f, content in DISTRACTORS.items())
    unchanged = task is not TASKS["noop"] or after == before
    completed = p.returncode == 0 and not timed_out and usage["completed"]
    result = {**usage, **metrics, "duration_seconds": round(duration, 3), "returncode": p.returncode,
              "timed_out": timed_out, "checks_passed": sum(c["passed"] for c in checks), "checks_total": len(checks),
              "checks": checks, "unrelated_preserved": protected, "noop_preserved": unchanged,
              "success": completed and all(c["passed"] for c in checks) and protected and unchanged,
              "files_read": None, "files_read_note": "Shell reads/searches are not fully observable; do not infer exact counts.",
              "dependencies_added": None, "dependencies_note": "Requires trace/manifest audit; not inferred from token count.",
              "prompt_sha256": digest(prompt), "workflow_bytes": len(instruction.encode()),
              "actual_usd": None, "usd_note": "Codex reports tokens, not billing dollars.", "command": command}
    (folder / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--skill", type=Path, default=ROOT / "SKILL.md")
    parser.add_argument("--v1", type=Path, default=ROOT / "evals/v1.md")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--model", default="gpt-6-astra")
    parser.add_argument("--effort", default="low")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--tasks", default=",".join(TASKS))
    parser.add_argument("--arms", default="baseline,suffice")
    parser.add_argument("--ecc", type=Path)
    parser.add_argument("--ponytail", type=Path)
    args = parser.parse_args()
    selftest()
    if args.selftest:
        return
    if not args.out:
        parser.error("--out is required; use a fresh directory to preserve previous evidence")
    if args.repeats < 1 or args.timeout < 1:
        parser.error("repeats and timeout must be positive")
    names, arms = args.tasks.split(","), args.arms.split(",")
    if any(n not in TASKS for n in names) or any(a not in {"baseline", "suffice", "combined", "v1", "compressed"} for a in arms):
        parser.error("unknown task or arm")
    instructions = {"baseline": "", "suffice": args.skill.read_text()}
    if "v1" in arms:
        instructions["v1"] = args.v1.read_text()
    if "compressed" in arms:
        instructions["compressed"] = COMPRESSED
    sources = []
    if "combined" in arms:
        if not args.ecc or not args.ponytail:
            parser.error("combined needs pinned --ecc and --ponytail checkouts")
        parts = []
        for checkout, file in [(args.ecc, "rules/common/development-workflow.md"),
                               (args.ecc, "skills/verification-loop/SKILL.md"),
                               (args.ponytail, "skills/ponytail/SKILL.md")]:
            body = (checkout / file).read_text()
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout, text=True).strip()
            sources.append({"commit": commit, "path": file, "sha256": digest(body), "bytes": len(body.encode())})
            parts.append(body)
        instructions["combined"] = "\n\n".join(parts)
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {"cli": subprocess.check_output(["codex", "--version"], text=True).strip(),
                "model": args.model, "effort": args.effort, "repeats": args.repeats,
                "arms": arms, "tasks": names, "sources": sources,
                "skill_sha256": digest(instructions["suffice"]),
                "workflow_bytes": {a: len(instructions[a].encode()) for a in arms},
                "workflows": {a: instructions[a] for a in arms},
                "combined_scope": "Three source instruction files, NOT the full installed plugins or their hooks.",
                "harness_sha256": digest(Path(__file__).read_text()),
                "tasks_sha256": digest((ROOT / "evals/tasks.py").read_text())}
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (args.out / "run.py").write_text(Path(__file__).read_text())
    (args.out / "tasks.py").write_text((ROOT / "evals/tasks.py").read_text())
    rows = []
    # Rotate order across tasks/repeats to reduce simple first-run/cache bias.
    for repeat in range(args.repeats):
        for index, name in enumerate(names):
            offset = (index + repeat) % len(arms)
            for arm in arms[offset:] + arms[:offset]:
                label = f"{repeat + 1}-{name}-{arm}"
                print("START", label, flush=True)
                row = {"run": label, "task": name, "arm": arm, "category": TASKS[name].get("category"),
                       **run_one(args.out / label, TASKS[name], instructions[arm], args)}
                rows.append(row)
                (args.out / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
                print("DONE", label, "success=" + str(row["success"]), "tokens=" + str(row["input_tokens"]),
                      "seconds=" + str(row["duration_seconds"]), flush=True)


if __name__ == "__main__":
    main()
