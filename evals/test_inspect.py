from collections import Counter
from contextlib import redirect_stdout
import io
import os
import runpy
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/collect_context.py'


class InspectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='suffice-inspect-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'repo'
        self.root.mkdir()
        subprocess.run(['git', 'init', '-q'], cwd=self.root, check=True)
        self.write('AGENTS.md', 'Preserve user changes.\n')
        self.write('api.py', 'from labels import display_name\ndef customer_label(x):\n    return display_name(x)\n')
        self.write('labels.py', 'def display_name(x):\n    return x.strip()\n')
        self.write('web.py', 'from labels import display_name\n')
        self.write('test_api.py', 'from api import customer_label\nassert customer_label(" x ")=="x"\n')
        self.write('unrelated.py', 'raise RuntimeError("MUST_NOT_EXECUTE_OR_RETURN")\n')

    def write(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def run_inspector(self, *args, env=None):
        return subprocess.run([sys.executable, '-B', str(SCRIPT), '--root', str(self.root), *args],
                              cwd=self.root, capture_output=True, text=True, timeout=10, env=env)

    def inspect_with_read_counts(self, *args):
        reads = Counter()
        original_open = Path.open

        def counted_open(path, mode='r', *positional, **keywords):
            if mode == 'rb' and path.is_relative_to(self.root):
                reads[path.relative_to(self.root).as_posix()] += 1
            return original_open(path, mode, *positional, **keywords)

        output = io.StringIO()
        command = [str(SCRIPT), '--root', str(self.root), *args]
        with mock.patch.object(sys, 'argv', command), mock.patch.object(Path, 'open', counted_open), redirect_stdout(output):
            runpy.run_path(str(SCRIPT), run_name='__main__')
        return output.getvalue(), reads

    def test_sources_imports_callers_instructions_and_preservation(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*')
                  if p.is_file() and '.git' not in p.parts}
        result = self.run_inspector('api.customer_label', 'web')
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ['api.py', 'labels.py', 'web.py', 'test_api.py', 'AGENTS.md']:
            self.assertIn('FILE: ' + name + ' |', result.stdout)
        self.assertNotIn('MUST_NOT_EXECUTE_OR_RETURN', result.stdout)
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*')
                 if p.is_file() and '.git' not in p.parts}
        self.assertEqual(before, after)

    def test_outside_and_symlink_targets_are_rejected(self):
        secret = self.base / 'secret.py'
        secret.write_text('PRIVATE_SENTINEL')
        (self.root / 'escape.py').symlink_to(secret)
        for target in [str(secret), '../secret.py', 'escape.py']:
            result = self.run_inspector(target)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Target not found inside root', result.stderr)
            self.assertNotIn('PRIVATE_SENTINEL', result.stdout + result.stderr)

    def test_relative_imports_and_nested_instructions(self):
        self.write('pkg/api.py', 'from .labels import normalize\n')
        self.write('pkg/labels.py', 'def normalize(x):\n    return x\n')
        self.write('pkg/AGENTS.md', 'Nested instructions.\n')
        result = self.run_inspector('pkg.api')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('FILE: pkg/labels.py |', result.stdout)
        self.assertIn('Nested instructions.', result.stdout)

    def test_repeated_imports_and_cycles_read_each_source_once(self):
        self.write('cycle_a.py', 'import cycle_b\nfrom cycle_b import shared\nimport cycle_c\n')
        self.write('cycle_b.py', 'import cycle_a\nfrom cycle_c import shared\nshared = 1\n')
        self.write('cycle_c.py', 'import cycle_a\nimport cycle_b\nshared = 2\n')
        output, reads = self.inspect_with_read_counts('cycle_a', 'cycle_a.py', 'cycle_b')
        for name in ['cycle_a.py', 'cycle_b.py', 'cycle_c.py', 'AGENTS.md']:
            self.assertEqual(reads[name], 1, (name, reads))
            self.assertEqual(output.count('\nFILE: ' + name + ' |'), 1)

    def test_stub_target_keeps_symbol_based_caller_search(self):
        self.write('interface.pyi', 'import unrelated\ndef stub_label(value: str) -> str: ...\n')
        self.write('consumer.py', 'def render(value):\n    return stub_label(value)\n')
        result = self.run_inspector('interface.pyi')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('FILE: interface.pyi | requested target', result.stdout)
        self.assertIn('FILE: consumer.py | matching caller or test;', result.stdout)
        self.assertNotIn('FILE: unrelated.py |', result.stdout)

    def test_omitted_sources_are_not_reread_as_callers(self):
        self.write('scan_target.py', 'import oversized\nimport non_utf8\n\ndef needle():\n    return 1\n')
        self.write('oversized.py', '# needle\n' * 500)
        (self.root / 'non_utf8.py').write_bytes(b'# needle\n\xff\n')
        output, reads = self.inspect_with_read_counts('--max-bytes', '300', 'scan_target')
        for name, notice in [
            ('oversized.py', 'Byte limit: source omitted, not truncated: oversized.py'),
            ('non_utf8.py', 'Non-UTF-8 source omitted: non_utf8.py'),
        ]:
            self.assertEqual(reads[name], 1, (name, reads))
            self.assertEqual(output.count(notice), 1)
            self.assertNotIn('\nFILE: ' + name + ' |', output)
        self.assertIn('Caller/test search:', output)

    def test_full_file_budget_skips_caller_search_subprocess(self):
        marker = self.base / 'rg-executed'
        bindir = self.base / 'bin'
        bindir.mkdir()
        rg = bindir / 'rg'
        rg.write_text('#!/bin/sh\n: > ' + shlex.quote(str(marker)) + '\nexit 1\n')
        rg.chmod(0o700)
        env = os.environ.copy()
        env['PATH'] = str(bindir) + os.pathsep + env.get('PATH', '')
        result = self.run_inspector('--max-files', '1', 'api.py', env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('FILE: api.py |', result.stdout)
        self.assertIn('File limit reached', result.stdout)
        self.assertFalse(marker.exists(), 'Caller search ran after the file budget was exhausted')

    def test_ripgrep_config_cannot_execute_preprocessor(self):
        marker = self.base / 'rg-preprocessor-executed'
        helper = self.base / 'rg-preprocessor.sh'
        helper.write_text('#!/bin/sh\n: > ' + shlex.quote(str(marker)) + '\ncat "$1"\n')
        helper.chmod(0o700)
        config = self.base / 'ripgrep.conf'
        config.write_text('--pre\n' + str(helper) + '\n')
        env = os.environ.copy()
        env['RIPGREP_CONFIG_PATH'] = str(config)
        result = self.run_inspector('api.py', env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(marker.exists(), 'Caller search executed a configured ripgrep preprocessor')
        self.assertIn('FILE: test_api.py | matching caller or test;', result.stdout)

    def test_git_diff_treats_requested_wildcard_filename_literally(self):
        self.write('api*.py', 'VALUE = 1\n')
        self.write('api-other.py', 'UNRELATED = 1\n')
        for args in [['add', '.'], ['-c', 'user.name=Fixture', '-c', 'user.email=fixture@invalid.local',
                                   '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'fixture']]:
            subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True)
        self.write('api*.py', 'VALUE = 1\n# requested literal change\n')
        self.write('api-other.py', 'UNRELATED = 1\n# DO_NOT_RETURN_UNRELATED_STAGED\n')
        subprocess.run(['git', 'add', '--', 'api-other.py'], cwd=self.root, check=True, capture_output=True)
        self.write('api-other.py', (self.root / 'api-other.py').read_text() +
                   '# DO_NOT_RETURN_UNRELATED_UNSTAGED\n')
        result = self.run_inspector('api*.py')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('FILE: api*.py |', result.stdout)
        self.assertIn('+# requested literal change', result.stdout)
        self.assertNotIn('DO_NOT_RETURN_UNRELATED_STAGED', result.stdout)
        self.assertNotIn('DO_NOT_RETURN_UNRELATED_UNSTAGED', result.stdout)

    def test_git_external_diff_and_textconv_are_not_executed(self):
        marker = self.base / 'executed'
        helper = self.base / 'git-helper.sh'
        helper.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\ncat "$1"\n')
        helper.chmod(0o700)
        self.write('.gitattributes', '*.py diff=probe\n')
        for args in [['add', '.'], ['-c', 'user.name=Fixture', '-c', 'user.email=fixture@invalid.local',
                                   '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'fixture'],
                     ['config', 'diff.probe.textconv', str(helper)],
                     ['config', 'diff.external', str(helper)],
                     ['config', 'core.fsmonitor', str(helper)]]:
            subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True)
        self.write('api.py', (self.root / 'api.py').read_text() + '\n# user change\n')
        result = self.run_inspector('api.py')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('# user change', result.stdout)
        self.assertFalse(marker.exists(), 'Inspector executed a configured Git helper')

    def test_git_clean_and_process_filters_are_not_executed(self):
        self.write('.gitattributes', '*.py filter=probe\n')
        for args in [['add', '.'], ['-c', 'user.name=Fixture', '-c', 'user.email=fixture@invalid.local',
                                   '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'fixture']]:
            subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True)
        self.write('api.py', (self.root / 'api.py').read_text() + '\n# dirty tracked source\n')
        for kind in ['clean', 'process']:
            with self.subTest(filter=kind):
                marker = self.base / (kind + '-executed')
                helper = self.base / (kind + '-filter.sh')
                helper.write_text('#!/bin/sh\n: > ' + shlex.quote(str(marker)) + '\n' +
                                  ('cat\n' if kind == 'clean' else 'exit 1\n'))
                helper.chmod(0o700)
                subprocess.run(['git', 'config', 'filter.probe.' + kind, str(helper)],
                               cwd=self.root, check=True, capture_output=True)
                subprocess.run(['git', 'config', 'filter.probe.required', 'true'],
                               cwd=self.root, check=True, capture_output=True)
                try:
                    result = self.run_inspector('api.py')
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertFalse(marker.exists(), 'Inspector executed the Git ' + kind + ' filter')
                    self.assertIn('FILE: api.py |', result.stdout)
                    diff = result.stdout.split('\nGIT DIFF:\n', 1)[1].split('\nGIT STAGED DIFF:', 1)[0]
                    self.assertIn('+# dirty tracked source', diff)
                    self.assertNotIn('GIT DIFF unavailable:', result.stdout)
                finally:
                    subprocess.run(['git', 'config', '--unset', 'filter.probe.' + kind],
                                   cwd=self.root, check=True, capture_output=True)

    def test_file_and_byte_limits_are_explicit(self):
        result = self.run_inspector('--max-files', '1', 'api.py')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.count('\nFILE: '), 1)
        self.assertIn('File limit reached', result.stdout)
        result = self.run_inspector('--max-bytes', '1', 'api.py')
        self.assertEqual(result.returncode, 0)
        self.assertNotIn('\nFILE: ', result.stdout)
        self.assertIn('source omitted, not truncated', result.stdout)
        self.assertIn('no repository-wide fallback', result.stdout)


if __name__ == '__main__':
    unittest.main()
