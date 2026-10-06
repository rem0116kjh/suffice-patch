"""Offline preservation and event-accounting regressions for external_run."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("external_run", Path(__file__).with_name("external_run.py"))
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def file_row(body=b"original\n", mode=0o644):
    return ("file", mode, body)


def task(**options):
    return {"allowed_source_paths": ["src/library.py"], "allow_new_tests": True, **options}


def event(command, output="", exit_code=0):
    return {"type": "item.completed", "item": {
        "type": "command_execution", "command": command,
        "aggregated_output": output, "exit_code": exit_code,
    }}


def parsed(*events):
    return runner.parse_events("\n".join(json.dumps(value) for value in events))


class PreservationTests(unittest.TestCase):
    def test_protected_files_reject_edit_delete_and_mode_change(self):
        names = ("tests/test_existing.py", ".agents/skills/suffice-patch/SKILL.md",
                 ".agents/skills/suffice-patch/scripts/collect_context.py", "LOCAL_NOTES.md")
        for name in names:
            before = {name: file_row()}
            variants = ({name: file_row(b"changed\n")}, {}, {name: file_row(mode=0o755)})
            for after in variants:
                with self.subTest(name=name, after=after):
                    metrics, _ = runner.compare(before, after, task())
                    self.assertEqual(metrics["forbidden_changes"], [name])

    def test_localized_source_edit_remains_allowed(self):
        before = {"src/library.py": file_row(), "LOCAL_NOTES.md": file_row()}
        after = {**before, "src/library.py": file_row(b"fixed\n")}
        metrics, patch_text = runner.compare(before, after, task())
        self.assertEqual(metrics["forbidden_changes"], [])
        self.assertEqual(metrics["modified_paths"], ["src/library.py"])
        self.assertIn("+fixed", patch_text)

    def test_noop_rejects_source_edit_new_test_deletion_and_mode_change(self):
        before = {"src/library.py": file_row()}
        variants = ({"src/library.py": file_row(b"changed\n")},
                    {**before, "tests/test_new.py": file_row()}, {},
                    {"src/library.py": file_row(mode=0o755)})
        for after in variants:
            with self.subTest(after=after):
                metrics, _ = runner.compare(before, after, task(expected_noop=True))
                self.assertTrue(metrics["forbidden_changes"])
        metrics, _ = runner.compare(before, before.copy(), task(expected_noop=True))
        self.assertEqual(metrics["modified_paths"], [])

    def test_new_test_requires_permitted_location_type_and_task_policy(self):
        cases = [
            ("tests/test_new.py", file_row(), True, False),
            ("tests/test_new.py", file_row(), False, True),
            ("tests/readme.md", file_row(), True, True),
            ("test_new.py", file_row(), True, True),
            ("src/test_new.py", file_row(), True, True),
            ("tests/test_new.py", ("link", 0o777, b"../outside.py"), True, True),
        ]
        for name, row, allowed, forbidden in cases:
            with self.subTest(name=name, row=row, allowed=allowed):
                metrics, _ = runner.compare({}, {name: row}, task(allow_new_tests=allowed))
                self.assertEqual(bool(metrics["forbidden_changes"]), forbidden)

    def test_raw_binary_change_cannot_hide_behind_replacement_decoding(self):
        metrics, _ = runner.compare({"LOCAL_NOTES.md": file_row(b"\xff")},
                                    {"LOCAL_NOTES.md": file_row(b"\xfe")}, task())
        self.assertEqual(metrics["forbidden_changes"], ["LOCAL_NOTES.md"])

    def test_snapshot_records_link_targets_file_types_modes_and_raw_bytes(self):
        with tempfile.TemporaryDirectory(prefix="external-run-unit-") as name:
            root = Path(name)
            original = root / "protected.bin"
            original.write_bytes(b"\x00\xff\xfe\n")
            original.chmod(0o640)
            link = root / "alias"
            link.symlink_to("protected.bin")
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "ignored.pyc").write_bytes(b"cache")
            before = runner.snapshot(root)
            self.assertEqual(before["protected.bin"], ("file", 0o640, b"\x00\xff\xfe\n"))
            self.assertEqual(before["alias"][0], "link")
            self.assertEqual(before["alias"][2], b"protected.bin")
            self.assertFalse(any("__pycache__" in key for key in before))
            link.unlink()
            link.write_bytes(b"protected.bin")
            original.chmod(0o600)
            after = runner.snapshot(root)
            metrics, _ = runner.compare(before, after, task())
            self.assertEqual(metrics["forbidden_changes"], ["alias", "protected.bin"])
            self.assertNotEqual(runner.snapshot_hashes(before), runner.snapshot_hashes(after))


class EventAccountingTests(unittest.TestCase):
    def test_missing_usage_stays_unknown(self):
        for raw in ("", "not-json", '{"type":"turn.failed"}', '{"type":"turn.completed"}'):
            with self.subTest(raw=raw):
                value = runner.parse_events(raw)
                for key in ("input_tokens", "cached_input_tokens", "output_tokens"):
                    self.assertIsNone(value[key])

    def test_absent_cache_key_does_not_become_zero(self):
        value = parsed({"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 2}})
        self.assertEqual(value["input_tokens"], 10)
        self.assertEqual(value["output_tokens"], 2)
        self.assertIsNone(value["cached_input_tokens"])
        self.assertTrue(value["completed"])

    def test_usage_sums_only_fully_observed_fields(self):
        value = parsed(
            {"type": "turn.completed", "usage": {"input_tokens": 10, "cached_input_tokens": 0, "output_tokens": 2}},
            {"type": "turn.completed", "usage": {"input_tokens": 5, "output_tokens": 3}},
        )
        self.assertEqual(value["input_tokens"], 15)
        self.assertEqual(value["output_tokens"], 5)
        self.assertIsNone(value["cached_input_tokens"])
        self.assertEqual(len(value["raw_usage"]), 2)

    def test_skill_read_and_helper_are_exposed_for_baseline_contamination(self):
        value = parsed(event("cat .agents/skills/suffice-patch/SKILL.md", "# SufficePatch\n"),
                       event("python3 scripts/collect_context.py src/library.py", "ROOT: /work\nFILE: src/library.py\n"))
        self.assertTrue(value["skill_read"])
        self.assertTrue(value["helper_invoked"])
        self.assertTrue(value["helper_success"])
        self.assertEqual(value["tool_calls"], 2)

    def test_failed_or_incomplete_helper_is_not_successful(self):
        for output, code in (("ROOT: /work\nFILE: src/library.py\n", 1),
                             ("ROOT: /work\n", 0), ("FILE: src/library.py\n", 0)):
            with self.subTest(output=output, code=code):
                value = parsed(event("python3 scripts/collect_context.py src/library.py", output, code))
                self.assertTrue(value["helper_invoked"])
                self.assertFalse(value["helper_success"])

    def test_reading_helper_source_is_not_successful_helper_execution(self):
        body = (Path(__file__).resolve().parents[1] / "scripts/collect_context.py").read_text()
        value = parsed(event("cat .agents/skills/suffice-patch/scripts/collect_context.py", body))
        self.assertFalse(value["helper_success"])

    def test_turn_failure_overrides_prior_completion(self):
        value = parsed({"type": "turn.completed", "usage": {"input_tokens": 5}}, {"type": "turn.failed"})
        self.assertFalse(value["completed"])
        self.assertEqual(value["input_tokens"], 5)

    def test_grader_environment_enables_assertions_and_targets_checkout(self):
        with patch.dict(os.environ, {"PYTHONOPTIMIZE": "2", "PYTHONPATH": "/wrong/src", "PATH": "/bin"}):
            value = runner.environment({"source_subdir": "src", "python_executable": "/venv/bin/python"}, Path("/work"))
        self.assertNotIn("PYTHONOPTIMIZE", value)
        self.assertEqual(value["PYTHONPATH"], "/work/src")
        self.assertTrue(value["PATH"].startswith("/venv/bin" + os.pathsep))


if __name__ == "__main__":
    unittest.main()
