"""Black-box context checks on independently constructed mixed-language fixtures.

These tests inspect observable source selection, boundaries, budgets, and file
preservation. They do not import the helper implementation or compile projects.
Runtime smoke tests of independently runnable JS/Go/C projects are a separate
validation layer; success here does not transfer the old Python efficiency data.
"""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/collect_context.py"


class MultilanguageContextTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="suffice-multilang-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "repo"
        self.root.mkdir()
        subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "init", "-q"], cwd=self.root, check=True)
        self.write("AGENTS.md", "Preserve all project and user files.\n")

    def write(self, relative, body):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    def run_helper(self, *arguments, env=None):
        environment = os.environ.copy()
        for name in ("PYTHONPATH", "PYTHONHOME", "PYTHONOPTIMIZE"):
            environment.pop(name, None)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        if env:
            environment.update(env)
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--root", str(self.root), *arguments],
            cwd=self.root, capture_output=True, text=True, timeout=15, env=environment,
        )

    def files(self, result):
        return re.findall(r"^FILE: (.*?) \|", result.stdout, flags=re.MULTILINE)

    def assert_context(self, result, required):
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout[-2000:])
        selected = self.files(result)
        self.assertEqual(len(selected), len(set(selected)), "A source was printed more than once")
        self.assertTrue(set(required).issubset(selected), (required, selected, result.stdout))
        return set(selected)

    def assert_budget(self, result, max_files=16, max_bytes=40000):
        summary = re.search(r"Sources returned: (\d+); source bytes: (\d+)", result.stdout)
        self.assertIsNotNone(summary, result.stdout)
        count, size = map(int, summary.groups())
        selected = self.files(result)
        self.assertEqual(count, len(selected))
        # Check actual UTF-8 file bytes, not the helper's declaration alone.
        self.assertEqual(size, sum((self.root / relative).stat().st_size for relative in selected))
        self.assertLessEqual(count, max_files)
        self.assertLessEqual(size, max_bytes)

    def snapshot(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file() and ".git" not in path.parts}

    def test_scoped_context_still_reports_unrelated_user_git_changes(self):
        self.write("apps/cart/src/quote.js", "export function quote() { return 500; }\n")
        self.write("LOCAL_NOTES.md", "Original note.\n")
        subprocess.run(["git", "add", "."], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@invalid.local",
                        "-c", "core.hooksPath=/dev/null", "commit", "-qm", "fixture"],
                       cwd=self.root, check=True, capture_output=True)
        self.write("LOCAL_NOTES.md", "DO_NOT_LOAD_USER_NOTE_CONTENT\n")
        self.write("DRAFT.txt", "DO_NOT_LOAD_USER_DRAFT_CONTENT\n")
        before = self.snapshot()
        result = self.run_helper("apps/cart/src/quote.js", "--scope", "apps/cart")
        self.assert_context(result, ["apps/cart/src/quote.js"])
        status = result.stdout.split("GIT STATUS:\n", 1)[1].split("GIT DIFF:", 1)[0]
        self.assertIn(" M LOCAL_NOTES.md", status)
        self.assertIn("?? DRAFT.txt", status)
        self.assertNotIn("DO_NOT_LOAD_USER_NOTE_CONTENT", result.stdout)
        self.assertNotIn("DO_NOT_LOAD_USER_DRAFT_CONTENT", result.stdout)
        self.assertEqual(before, self.snapshot())

    def test_whitespace_heavy_document_finishes_within_search_budget(self):
        # A previous multiline regex consumed newlines quadratically even when
        # search itself had a timeout. Exercise a near-budget text file end to end.
        self.write("notes/probe.md", "\n" * 39900 + "?\n")
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--root", str(self.root), "notes/probe.md"],
            cwd=self.root, capture_output=True, text=True, timeout=5,
        )
        self.assert_context(result, ["notes/probe.md"])
        self.assert_budget(result)

    def test_python_src_package_keeps_import_test_and_manifest(self):
        self.write("packages/python/pyproject.toml", '[project]\nname="fixture-python"\nversion="0.1.0"\n')
        self.write("packages/python/src/app/__init__.py", "")
        self.write("packages/python/src/app/service.py", "from .labels import normalize\ndef make_label(value):\n    return normalize(value)\n")
        self.write("packages/python/src/app/labels.py", "def normalize(value):\n    return value.strip()\n")
        self.write("packages/python/tests/test_service.py", "from app.service import make_label\nassert make_label(' x ') == 'x'\n")
        result = self.run_helper("packages/python/src/app/service.py")
        self.assert_context(result, ["packages/python/src/app/service.py", "packages/python/src/app/labels.py",
                                     "packages/python/tests/test_service.py", "packages/python/pyproject.toml", "AGENTS.md"])
        self.assert_budget(result)

    def test_typescript_relative_js_extension_and_directory_index(self):
        self.write("packages/web/package.json", '{"name":"web","type":"module"}\n')
        self.write("packages/web/tsconfig.json", '{"compilerOptions":{"module":"ESNext","moduleResolution":"Bundler"}}\n')
        self.write("packages/web/src/format.ts", 'import {trim} from "./trim.js";\nimport {prefix} from "./tokens";\nexport function formatName(v: string) { return prefix + trim(v); }\n')
        self.write("packages/web/src/trim.ts", "export function trim(v: string) { return v.trim(); }\n")
        self.write("packages/web/src/tokens/index.ts", 'export const prefix = "name:";\n')
        self.write("packages/web/tests/format.spec.ts", 'import {formatName} from "../src/format.js";\nif (formatName(" x ") !== "name:x") throw Error("bad");\n')
        result = self.run_helper("packages/web/src/format.ts")
        self.assert_context(result, ["packages/web/src/format.ts", "packages/web/src/trim.ts", "packages/web/src/tokens/index.ts",
                                     "packages/web/tests/format.spec.ts", "packages/web/package.json", "packages/web/tsconfig.json"])
        self.assert_budget(result)

    def test_javascript_require_dynamic_import_and_reexport(self):
        self.write("apps/node/package.json", '{"name":"node-fixture","type":"module"}\n')
        self.write("apps/node/src/entry.js", 'export {name} from "./name.mjs";\nexport async function load() { return import("./lazy.mjs"); }\n')
        self.write("apps/node/src/name.mjs", 'export const name = "fixture";\n')
        self.write("apps/node/src/lazy.mjs", "export const value = 4;\n")
        self.write("apps/node/src/common.cjs", 'const {label} = require("./label.cjs");\nmodule.exports = label;\n')
        self.write("apps/node/src/label.cjs", 'exports.label = "ok";\n')
        result = self.run_helper("apps/node/src/entry.js", "apps/node/src/common.cjs")
        self.assert_context(result, ["apps/node/src/entry.js", "apps/node/src/name.mjs", "apps/node/src/lazy.mjs",
                                     "apps/node/src/common.cjs", "apps/node/src/label.cjs", "apps/node/package.json"])

    def test_vue_and_svelte_script_imports_remain_local(self):
        self.write("packages/ui/package.json", '{"name":"ui-fixture"}\n')
        self.write("packages/ui/src/labels.ts", 'export const label = "hello";\n')
        components = {
            "UserCard.vue": '<script setup lang="ts">\nimport {label} from "./labels";\n</script>\n<template>{{ label }}</template>\n',
            "UserPanel.svelte": '<script lang="ts">\nimport {label} from "./labels";\n</script>\n<p>{label}</p>\n',
        }
        for name, body in components.items():
            with self.subTest(component=name):
                self.write("packages/ui/src/" + name, body)
                self.write("packages/ui/tests/" + name + ".spec.ts", f'import Component from "../src/{name}";\nvoid Component;\n')
                result = self.run_helper("packages/ui/src/" + name)
                self.assert_context(result, ["packages/ui/src/" + name, "packages/ui/src/labels.ts",
                                             "packages/ui/tests/" + name + ".spec.ts", "packages/ui/package.json"])

    def test_go_same_module_import_loads_package_sources_and_test(self):
        self.write("services/api/go.mod", "module example.test/api\n\ngo 1.20\n")
        self.write("services/api/internal/service/service.go", 'package service\nimport "example.test/api/internal/text"\nfunc DisplayName(v string) string { return text.Clean(v) }\n')
        self.write("services/api/internal/text/clean.go", 'package text\nimport "strings"\nfunc Clean(v string) string { return prefix + strings.TrimSpace(v) }\n')
        self.write("services/api/internal/text/prefix.go", 'package text\nconst prefix = "name:"\n')
        self.write("services/api/internal/service/service_test.go", 'package service\nimport "testing"\nfunc TestDisplayName(t *testing.T) { if DisplayName(" x ") != "name:x" { t.Fatal("bad") } }\n')
        self.write("services/unrelated/go.mod", "module example.test/unrelated\n\ngo 1.20\n")
        self.write("services/unrelated/service.go", 'package unrelated\nconst DisplayName = "UNRELATED_GO_SOURCE"\n')
        result = self.run_helper("services/api/internal/service/service.go", "--scope", "services/api")
        self.assert_context(result, ["services/api/internal/service/service.go", "services/api/internal/text/clean.go",
                                     "services/api/internal/text/prefix.go", "services/api/internal/service/service_test.go", "services/api/go.mod"])
        self.assertNotIn("UNRELATED_GO_SOURCE", result.stdout)

    def test_rust_mod_and_crate_self_super_resolve_local_modules(self):
        self.write("crates/tiny/Cargo.toml", '[package]\nname="tiny"\nversion="0.1.0"\nedition="2021"\n')
        self.write("crates/tiny/src/lib.rs", "pub mod alpha;\npub mod shared;\n")
        self.write("crates/tiny/src/alpha/mod.rs", 'mod inner;\nuse crate::shared::suffix;\nuse self::inner::prefix;\npub fn decorate(value: &str) -> String { format!("{}{}{}", prefix(), value, suffix()) }\n')
        self.write("crates/tiny/src/alpha/inner.rs", 'use super::super::shared::suffix;\npub fn prefix() -> String { format!("name{}", suffix()) }\n')
        self.write("crates/tiny/src/shared.rs", 'pub fn suffix() -> &\'static str { ":" }\n')
        self.write("crates/tiny/tests/decorate.rs", 'use tiny::alpha::decorate;\n#[test] fn label() { assert_eq!(decorate("x"), "name:x:"); }\n')
        result = self.run_helper("crates/tiny/src/alpha/mod.rs")
        self.assert_context(result, ["crates/tiny/src/alpha/mod.rs", "crates/tiny/src/alpha/inner.rs",
                                     "crates/tiny/src/shared.rs", "crates/tiny/tests/decorate.rs", "crates/tiny/Cargo.toml"])

    def test_c_and_cpp_quoted_nested_headers_and_build_manifest(self):
        self.write("native/label/CMakeLists.txt", "cmake_minimum_required(VERSION 3.16)\nproject(label C CXX)\n")
        self.write("native/label/include/label.h", '#include "detail/limits.h"\nint format_label(int value);\n')
        self.write("native/label/include/detail/limits.h", "#define LABEL_LIMIT 9\n")
        for suffix in ("c", "cpp"):
            with self.subTest(language=suffix):
                target = "native/label/src/label." + suffix
                self.write(target, '#include "../include/label.h"\nint format_label(int value) { return value < LABEL_LIMIT ? value : LABEL_LIMIT; }\n')
                self.write("native/label/tests/test_label." + suffix, '#include "../include/label.h"\nint main(void) { return format_label(20) != LABEL_LIMIT; }\n')
                result = self.run_helper(target)
                self.assert_context(result, [target, "native/label/include/label.h", "native/label/include/detail/limits.h",
                                             "native/label/tests/test_label." + suffix, "native/label/CMakeLists.txt"])

    def test_other_language_configuration_and_docs_are_readable_with_manifest(self):
        self.write("services/java/pom.xml", '<project><modelVersion>4.0.0</modelVersion><artifactId>fixture</artifactId></project>\n')
        self.write("services/java/src/Task.java", "public class Task { public String name() { return \"ok\"; } }\n")
        self.write("services/java/tests/TaskTest.java", 'class TaskTest { String value = new Task().name(); }\n')
        self.write("services/java/config/service.yaml", "display_name: sample\n")
        self.write("services/java/README.md", "# Fixture service\nThe configuration is config/service.yaml.\n")
        for target in ("src/Task.java", "config/service.yaml", "README.md"):
            with self.subTest(target=target):
                result = self.run_helper("services/java/" + target)
                required = ["services/java/" + target, "services/java/pom.xml"]
                if target.endswith("Task.java"):
                    required.append("services/java/tests/TaskTest.java")
                self.assert_context(result, required)
                self.assert_budget(result)

    def test_scope_excludes_siblings_dependencies_and_generated_sources(self):
        self.write("package.json", '{"private":true,"workspaces":["packages/*"]}\n')
        self.write("packages/app/package.json", '{"name":"app"}\n')
        self.write("packages/app/src/focus.ts", "export function focusedValue() { return 1; }\n")
        self.write("packages/app/tests/focus.spec.ts", 'import {focusedValue} from "../src/focus";\nvoid focusedValue();\n')
        excluded = ["packages/sibling/src/focus.ts", "packages/app/node_modules/copied/focus.ts", "packages/app/dist/focus.js",
                    "packages/app/build/focus.js", "packages/app/coverage/focus.js", "packages/app/.next/focus.js"]
        for index, path in enumerate(excluded):
            self.write(path, f'// focusedValue\nconst marker = "EXCLUDED_BODY_{index}";\n')
        result = self.run_helper("packages/app/src/focus.ts", "--scope", "packages/app")
        selected = self.assert_context(result, ["packages/app/src/focus.ts", "packages/app/tests/focus.spec.ts", "packages/app/package.json"])
        self.assertFalse(selected.intersection(excluded), selected)
        self.assertNotIn("EXCLUDED_BODY_", result.stdout)

    def test_repeated_scopes_keep_consumers_and_connected_shared_import(self):
        self.write("package.json", '{"private":true,"workspaces":["packages/*"]}\n')
        self.write("packages/app/package.json", '{"name":"app"}\n')
        self.write("packages/app/src/focus.ts", 'import {trim} from "../../shared/trim";\nexport function focusedValue(v: string) { return trim(v); }\n')
        self.write("packages/shared/trim.ts", "export function trim(v: string) { return v.trim(); }\n")
        self.write("packages/consumer/package.json", '{"name":"consumer"}\n')
        self.write("packages/consumer/tests/focus.spec.ts", 'import {focusedValue} from "../../app/src/focus";\nvoid focusedValue(" x ");\n')
        self.write("packages/other/tests/focus.spec.ts", '// focusedValue\nconst marker = "OUTSIDE_SEARCH_SCOPES";\n')
        result = self.run_helper("packages/app/src/focus.ts", "--scope", "packages/app", "--scope", "packages/consumer")
        self.assert_context(result, ["packages/app/src/focus.ts", "packages/shared/trim.ts", "packages/consumer/tests/focus.spec.ts"])
        self.assertNotIn("OUTSIDE_SEARCH_SCOPES", result.stdout)

    def test_scope_escape_and_external_symlink_targets_or_imports_are_rejected(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "secret.ts").write_text('export const secret = "EXTERNAL_SECRET_SENTINEL";\n')
        self.write("packages/app/package.json", '{"name":"app"}\n')
        self.write("packages/app/src/focus.ts", 'import {secret} from "./external/secret";\nexport const value = secret;\n')
        (self.root / "packages/app/src/external").symlink_to(outside, target_is_directory=True)
        for scope in (str(outside), "../outside", "packages/app/src/external"):
            with self.subTest(scope=scope):
                result = self.run_helper("packages/app/src/focus.ts", "--scope", scope)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("EXTERNAL_SECRET_SENTINEL", result.stdout + result.stderr)
        for target in (str(outside / "secret.ts"), "../outside/secret.ts", "packages/app/src/external/secret.ts"):
            with self.subTest(target=target):
                result = self.run_helper(target)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("EXTERNAL_SECRET_SENTINEL", result.stdout + result.stderr)
        result = self.run_helper("packages/app/src/focus.ts")
        self.assert_context(result, ["packages/app/src/focus.ts"])
        self.assertNotIn("EXTERNAL_SECRET_SENTINEL", result.stdout + result.stderr)
        self.assertNotIn("packages/app/src/external/secret.ts", self.files(result))

    def test_source_count_and_utf8_byte_budgets_are_observed(self):
        for index in range(25):
            following = f'import "./item{index + 1}.js";\n' if index < 24 else ""
            self.write(f"bounded/item{index}.js", following + f'export const item{index} = "한글";\n')
        result = self.run_helper("bounded/item0.js", "--max-files", "4", "--max-bytes", "250")
        self.assert_context(result, ["bounded/item0.js"])
        self.assert_budget(result, max_files=4, max_bytes=250)
        huge = self.write("bounded/huge.ts", '// LARGE_SOURCE_SENTINEL\n' + "한" * 1000)
        result = self.run_helper("bounded/huge.ts", "--max-files", "16", "--max-bytes", "120")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_budget(result, max_bytes=120)
        self.assertNotIn("bounded/huge.ts", self.files(result))
        self.assertNotIn("LARGE_SOURCE_SENTINEL", result.stdout)
        self.assertEqual(huge.stat().st_size, len(huge.read_text().encode("utf-8")))

    def test_project_code_and_package_scripts_are_not_executed_or_modified(self):
        marker = self.base / "project-executed"
        self.write("project/danger.py", f'from pathlib import Path\nPath({str(marker)!r}).write_text("executed")\ndef guarded():\n    return 1\n')
        self.write("project/danger.js", 'import fs from "node:fs";\nfs.writeFileSync(' + json.dumps(str(marker)) + ', "executed");\nexport const guarded = 1;\n')
        self.write("project/package.json", json.dumps({"name": "fixture", "scripts": {"prepare": "touch " + str(marker)}}) + "\n")
        self.write("project/test_guarded.py", "from danger import guarded\nassert guarded() == 1\n")
        before = self.snapshot()
        result = self.run_helper("project/danger.py", "project/danger.js")
        self.assert_context(result, ["project/danger.py", "project/danger.js", "project/package.json", "project/test_guarded.py"])
        self.assertFalse(marker.exists(), "Inspecting context executed a project side effect")
        self.assertEqual(self.snapshot(), before)

    def test_large_monorepo_and_directory_map_keep_bounded_scope(self):
        self.write("package.json", '{"private":true,"workspaces":["packages/*"]}\n')
        self.write("packages/active/package.json", '{"name":"active"}\n')
        self.write("packages/active/src/focus.ts", 'import {label} from "./label";\nexport function focusedValue() { return label; }\n')
        self.write("packages/active/src/label.ts", 'export const label = "active";\n')
        self.write("packages/active/tests/focus.spec.ts", 'import {focusedValue} from "../src/focus";\nvoid focusedValue();\n')
        for index in range(2000):
            self.write(f"packages/unrelated/src/file{index:04d}.ts", f'// focusedValue\nexport const unrelated{index} = "UNRELATED_LARGE_SOURCE";\n')
        for index in range(250):
            self.write(f"packages/active/maps/entry{index:03d}.ts", f'export const entry{index} = "MAP_BODY_MUST_NOT_BE_DUMPED";\n')
        result = self.run_helper("packages/active/src/focus.ts", "--scope", "packages/active")
        selected = self.assert_context(result, ["packages/active/src/focus.ts", "packages/active/src/label.ts", "packages/active/tests/focus.spec.ts"])
        self.assert_budget(result)
        self.assertTrue(all(path.startswith("packages/active/") or path in {"AGENTS.md", "package.json"} for path in selected), selected)
        self.assertNotIn("UNRELATED_LARGE_SOURCE", result.stdout)
        result = self.run_helper("packages/active", "--scope", "packages/active", "--max-files", "4", "--max-bytes", "1000")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.files(result), [])
        self.assertRegex(result.stdout, r"Sources returned: 0; source bytes: 0")
        self.assertRegex(result.stdout.lower(), r"(?:choose|select|specific).{0,100}file")
        self.assertNotIn("MAP_BODY_MUST_NOT_BE_DUMPED", result.stdout)
        self.assertNotIn("packages/unrelated", result.stdout)
        self.assertLess(len(result.stdout.encode("utf-8")), 24000)

    def test_reference_search_match_cap_and_timeout_are_explicit(self):
        self.write("bounded/focus.py", "def uniquely_focused():\n    return 1\n")
        for index in range(100):
            self.write(f"bounded/refs/use{index:03d}.py", f"# uniquely_focused\nVALUE = {index}\n")
        result = self.run_helper("bounded/focus.py", "--scope", "bounded", "--max-search-matches", "3")
        selected = self.assert_context(result, ["bounded/focus.py"])
        self.assertLessEqual(sum(path.startswith("bounded/refs/") for path in selected), 3)
        self.assert_budget(result)
        self.assertLess(len(result.stdout.encode("utf-8")), 24000)
        self.assertRegex(result.stdout.lower(), r"(?:limit|truncat|cap)")
        tools = self.base / "tools"
        tools.mkdir()
        rg = tools / "rg"
        rg.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(3)\n")
        rg.chmod(0o700)
        started = time.monotonic()
        result = self.run_helper("bounded/focus.py", "--scope", "bounded", "--search-timeout", "0.05",
                                 env={"PATH": str(tools) + os.pathsep + os.environ.get("PATH", "")})
        elapsed = time.monotonic() - started
        self.assert_context(result, ["bounded/focus.py"])
        self.assertLess(elapsed, 2.0, "The search timeout did not bound the blocked search")
        self.assertRegex(result.stdout.lower(), r"(?:timeout|timed.?out|unavailable)")


if __name__ == "__main__":
    unittest.main()
