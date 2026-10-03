import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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

    def run_inspector(self, *args):
        return subprocess.run([sys.executable, '-B', str(SCRIPT), '--root', str(self.root), *args],
                              cwd=self.root, capture_output=True, text=True, timeout=10)

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
