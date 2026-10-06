#!/usr/bin/env python3
"""Reproduce isolated bundle checks without changing host skill installations."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


EXPECTED = {
    "SKILL.md": "f365978b6a24b55d5312dd551cfb7f0a5775595ffd6b8205162cb1df973f9ea1",
    "scripts/collect_context.py": "a2968d41be8c1fb5954d0399777ef122ab99bc201c67bc5d33cb9bf4ff91347e",
}

RUN_TESTS = r'''
import importlib.util
import json
import sys
import unittest
from pathlib import Path
spec = importlib.util.spec_from_file_location("external_inspector_tests", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.SCRIPT = Path(sys.argv[2]).resolve()
suite = unittest.defaultTestLoader.loadTestsFromModule(module)
class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed_ids = []
    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed_ids.append(test.id())
result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(suite)
print(json.dumps({
    "tests_run": result.testsRun,
    "passed": result.passed_ids,
    "failures": [{"test": test.id(), "details": detail} for test, detail in result.failures],
    "errors": [{"test": test.id(), "details": detail} for test, detail in result.errors],
    "skipped": [{"test": test.id(), "reason": reason} for test, reason in result.skipped],
    "successful": result.wasSuccessful(),
}))
raise SystemExit(not result.wasSuccessful())
'''


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(directory):
    return {
        path.relative_to(directory).as_posix(): sha256(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def run(command, cwd, env=None):
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=120)
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--python312", default=shutil.which("python3.12"))
    parser.add_argument("--python-default", default=shutil.which("python3"))
    args = parser.parse_args()
    repo = args.repo.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    assert args.python312 and args.python_default, "Both requested interpreters are required"
    actual = {relative: sha256(repo / relative) for relative in EXPECTED}
    assert actual == EXPECTED, "Refusing to validate a bundle different from the frozen candidate"
    test_file = repo / "evals/test_inspect.py"
    test_hash_before = sha256(test_file)
    result = {
        "verification_date_kst": "2026-10-06",
        "host": {"platform": platform.platform(), "machine": platform.machine()},
        "candidate_hashes": actual,
        "test_file": {"path": str(test_file), "sha256": test_hash_before},
        "scope": "Isolated installation and helper portability, not model effectiveness",
        "global_skill_installations_modified": False,
        "linux": {
            "tested": False,
            "reason": "Docker daemon unavailable; infrastructure was not started for this check",
            "docker_socket_exists": Path("/var/run/docker.sock").exists(),
        },
        "interpreters": [],
    }
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    for name, interpreter, expected_minor in [
        ("python312", args.python312, "3.12"),
        ("python_default", args.python_default, "3.14"),
    ]:
        with tempfile.TemporaryDirectory(prefix="suffice-install-") as temporary:
            temporary = Path(temporary).resolve()
            assert not temporary.is_relative_to(repo)
            skill_dir = temporary / "clean-install/suffice-patch"
            fixture = temporary / "separate-project"
            fixture.mkdir()
            for relative in EXPECTED:
                destination = skill_dir / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(repo / relative, destination)
            copied = snapshot(skill_dir)
            assert copied == EXPECTED
            version = run([interpreter, "--version"], fixture, env)
            assert version["returncode"] == 0 and expected_minor in version["stdout"]
            (fixture / "AGENTS.md").write_text("Preserve all user changes.\n")
            (fixture / "service.py").write_text("from labels import normalize\ndef lookup(value):\n    return normalize(value)\n")
            (fixture / "labels.py").write_text("def normalize(value):\n    return value.strip()\n")
            (fixture / "test_service.py").write_text("from service import lookup\nassert lookup(' x ') == 'x'\n")
            (fixture / "unrelated.py").write_text("raise RuntimeError('SHOULD_NOT_BE_RUN_OR_READ')\n")
            init = run(["git", "init", "-q"], fixture, env)
            assert init["returncode"] == 0, init
            fixture_before = snapshot(fixture)
            smoke = run([interpreter, "-B", str(skill_dir / "scripts/collect_context.py"), "service.lookup"], fixture, env)
            smoke["expected_context_present"] = all(
                "FILE: " + name + " |" in smoke["stdout"]
                for name in ["service.py", "labels.py", "test_service.py", "AGENTS.md"]
            )
            smoke["unrelated_source_omitted"] = "SHOULD_NOT_BE_RUN_OR_READ" not in smoke["stdout"]
            smoke["fixture_preserved"] = fixture_before == snapshot(fixture)
            assert smoke["returncode"] == 0 and all(smoke[key] for key in ["expected_context_present", "unrelated_source_omitted", "fixture_preserved"])
            tests = run([interpreter, "-B", "-c", RUN_TESTS, str(test_file), str(skill_dir / "scripts/collect_context.py")], fixture, env)
            tests["summary"] = json.loads(tests["stdout"])
            assert tests["returncode"] == 0 and tests["summary"]["tests_run"] == 12
            assert tests["summary"]["successful"] and not tests["summary"]["skipped"]
            bundle_preserved = snapshot(skill_dir) == EXPECTED
            assert bundle_preserved
            item = {
                "name": name,
                "executable": interpreter,
                "version": version["stdout"].strip(),
                "temporary_install_dir": str(skill_dir),
                "temporary_fixture_dir": str(fixture),
                "temporary_directories_removed_after_check": True,
                "installed_bundle_hashes": copied,
                "installed_bundle_preserved": bundle_preserved,
                "smoke": smoke,
                "tests": tests,
            }
            (output / (name + ".json")).write_text(json.dumps(item, indent=2) + "\n")
            result["interpreters"].append(item)

    license_files = [name for name in ["LICENSE", "LICENSE.md", "LICENSE.txt"] if (repo / name).is_file()]
    distribution_files = list(EXPECTED) + license_files
    archive = repo / "dist/suffice-patch.zip"
    archive.parent.mkdir(exist_ok=True)
    # Stable timestamps, mode, order, and bytes allow independent hash reproduction.
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for relative in distribution_files:
            info = zipfile.ZipInfo("suffice-patch/" + relative, date_time=(2026, 10, 6, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, (repo / relative).read_bytes())
    with zipfile.ZipFile(archive) as bundle:
        entries = bundle.namelist()
        assert entries == ["suffice-patch/" + name for name in distribution_files]
        archive_hashes = {
            name: hashlib.sha256(bundle.read("suffice-patch/" + name)).hexdigest()
            for name in distribution_files
        }
        assert all(archive_hashes[name] == EXPECTED[name] for name in EXPECTED)
    assert actual == {relative: sha256(repo / relative) for relative in EXPECTED}
    assert test_hash_before == sha256(test_file)
    result["archive"] = {
        "path": str(archive),
        "sha256": sha256(archive),
        "bytes": archive.stat().st_size,
        "entries": entries,
        "entry_sha256": archive_hashes,
        "license_files_included": license_files,
        "license_note": "No repository LICENSE file exists; no license was created" if not license_files else "Existing repository license preserved",
    }
    result["original_bundle_and_tests_unchanged"] = True
    result["all_requested_checks_passed"] = True
    (output / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "checks": [{"python": item["version"], "tests_passed": item["tests"]["summary"]["tests_run"], "smoke_passed": item["smoke"]["returncode"] == 0} for item in result["interpreters"]],
        "archive": result["archive"],
        "linux_tested": False,
        "evidence": str(output / "verification.json"),
    }, indent=2))


if __name__ == "__main__":
    main()
