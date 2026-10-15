"""Observable v5 CLI, change selection, bounded output and read-only checks."""
import hashlib
import io
import json
from pathlib import Path
import shlex
import runpy
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/collect_context.py'


class V5Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='suffice-v5-')
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.root = self.base / 'repo'
        self.root.mkdir()
        self.git('init', '-q')
        self.write('AGENTS.md', 'Preserve user work.\n')

    def git(self, *args):
        return subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', *args], cwd=self.root,
                              check=True, capture_output=True)

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def commit(self):
        self.git('add', '.')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@invalid.local',
                 'commit', '-qm', 'fixture')

    def run_cli(self, *args, root=None):
        return subprocess.run([sys.executable, '-B', str(SCRIPT), '--root', str(root or self.root),
                               *args], capture_output=True, text=True, timeout=15)

    def report(self, *args, root=None):
        result = self.run_cli(*args, '--format', 'json', root=root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        return json.loads(result.stdout)

    def test_version_and_invalid_combinations(self):
        self.assertEqual(self.run_cli('--version').stdout.strip(), 'SufficePatch 5.0.0')
        for args in [(), ('--include-untracked', 'AGENTS.md'),
                     ('--changed', 'staged', '--include-untracked')]:
            self.assertEqual(self.run_cli(*args).returncode, 2)

    def test_json_contents_hashes_and_summary_equivalence(self):
        self.write('quote.py', 'def quote():\n    return "한글"\n' + '# body sentinel\n' * 300)
        self.commit()
        self.write('quote.py', (self.root / 'quote.py').read_text() + '# DIFF_SENTINEL\n')
        full = self.report('quote.py')
        short = self.report('quote.py', '--summary')
        self.assertEqual(full['schema_version'], 1)
        self.assertEqual(full['source_count'], len(full['sources']))
        self.assertEqual(full['source_bytes'], sum(s['bytes'] for s in full['sources']))
        for source in full['sources']:
            raw = (self.root / source['path']).read_bytes()
            self.assertEqual(source['content'].encode(), raw)
            self.assertEqual(source['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual([{k: v for k, v in s.items() if k != 'content'} for s in full['sources']], short['sources'])
        self.assertEqual(set(short['git']), {'GIT STATUS'})
        self.assertNotIn('body sentinel', json.dumps(short))
        self.assertNotIn('DIFF_SENTINEL', json.dumps(short))
        self.assertLess(len(json.dumps(short)), len(json.dumps(full)) / 2)

    def test_changed_modes_and_current_worktree_source(self):
        for name in ('first.txt', 'second.txt', 'third.txt'):
            self.write(name, 'initial\n')
        self.commit()
        self.write('first.txt', 'staged version\n')
        self.git('add', 'first.txt')
        self.write('first.txt', 'current unstaged version\n')
        self.write('second.txt', 'worktree only\n')
        self.write('new.txt', 'untracked sentinel\n')
        staged = self.report('--changed', 'staged')
        worktree = self.report('--changed', 'worktree')
        both = self.report('--changed', 'all')
        self.assertEqual([c['path'] for c in staged['changes']], ['first.txt'])
        self.assertEqual({c['path'] for c in worktree['changes']}, {'first.txt', 'second.txt'})
        self.assertEqual(both['changes'], worktree['changes'])
        first = next(s for s in staged['sources'] if s['path'] == 'first.txt')
        self.assertEqual(first['content'], 'current unstaged version\n')
        self.assertIn('+staged version', staged['git']['GIT STAGED DIFF']['output'])
        self.assertNotIn('untracked sentinel', json.dumps(both))
        all_files = self.report('--changed', 'all', '--include-untracked')
        self.assertIn('new.txt', [c['path'] for c in all_files['changes']])

    def test_clean_repository_has_no_fallback(self):
        self.write('private.txt', 'SHOULD_NOT_LOAD\n')
        self.commit()
        report = self.report('--changed', 'all')
        self.assertEqual(report['changes'], [])
        self.assertEqual(report['sources'], [])
        self.assertEqual(report['git'], {})
        self.assertNotIn('SHOULD_NOT_LOAD', json.dumps(report))

    def test_scopes_and_nested_root(self):
        for name in ('apps/a/item.txt', 'apps/b/item.txt'):
            self.write(name, 'initial\n')
        self.commit()
        self.write('apps/a/item.txt', 'in scope\n')
        self.write('apps/b/item.txt', 'OUTSIDE_SCOPE_SENTINEL\n')
        report = self.report('--changed', 'all', '--scope', 'apps/a')
        self.assertEqual([c['path'] for c in report['changes']], ['apps/a/item.txt'])
        self.assertNotIn('OUTSIDE_SCOPE_SENTINEL', json.dumps(report))
        nested = self.report('--changed', 'all', root=self.root / 'apps/a')
        self.assertEqual([c['path'] for c in nested['changes']], ['item.txt'])
        self.assertIn('item.txt', [s['path'] for s in nested['sources']])

    def test_deleted_source_keeps_diff_and_references(self):
        self.write('removed.py', 'def removed():\n    return 7\n')
        self.write('consumer.py', 'from removed import removed\n')
        self.commit()
        (self.root / 'removed.py').unlink()
        report = self.report('--changed', 'all')
        self.assertEqual(report['changes'][0]['path'], 'removed.py')
        self.assertIn('consumer.py', [s['path'] for s in report['sources']])
        self.assertNotIn('removed.py', [s['path'] for s in report['sources']])
        self.assertIn('-def removed():', report['git']['GIT DIFF']['output'])

    def test_rename_with_spaces_unicode_and_newline(self):
        old, new = 'old file.txt', '새 파일\nrenamed.txt'
        self.write(old, 'rename content\n')
        self.commit()
        self.git('mv', old, new)
        report = self.report('--changed', 'staged')
        self.assertEqual(report['changes'], [{'path': new, 'original_path': old, 'status': 'R '}])
        self.assertIn(new, [s['path'] for s in report['sources']])
        self.assertIn('rename from', report['git']['GIT STAGED DIFF']['output'])

    def test_unborn_branch_and_explicit_targets(self):
        self.write('new.py', 'VALUE = 7\n')
        self.git('add', 'new.py')
        report = self.report('AGENTS.md', '--changed', 'staged')
        self.assertEqual(report['changes'][0]['status'], 'A ')
        self.assertEqual({s['path'] for s in report['sources']}, {'new.py', 'AGENTS.md'})

    def test_symlink_outside_root_never_read(self):
        outside = self.base / 'outside.txt'
        outside.write_text('OUTSIDE_BODY_SENTINEL\n')
        (self.root / 'escape.txt').symlink_to(outside)
        self.git('add', 'escape.txt')
        report = self.report('--changed', 'all')
        self.assertEqual(report['changes'], [])
        self.assertNotIn('OUTSIDE_BODY_SENTINEL', json.dumps(report))

    def test_changed_limits_and_json_directory_map(self):
        for index in range(8):
            self.write(f'files/{index}.txt', str(index) * 200)
        self.git('add', '.')
        report = self.report('--changed', 'staged', '--max-search-matches', '3', '--max-files', '2')
        self.assertEqual(len(report['changes']), 3)
        self.assertLessEqual(len(report['sources']), 2)
        self.assertTrue(any('limit' in n.lower() for n in report['notices']))
        mapped = self.report('files', '--max-search-matches', '2')
        self.assertEqual(len(mapped['file_map']), 2)
        self.assertEqual(mapped['sources'], [])

    def test_capped_file_map_is_repeatable_and_sorted(self):
        for index in reversed(range(40)):
            self.write(f'files/item_{index:02d}.txt', 'example\n')
        maps = [self.report('files', '--max-search-matches', '3')['file_map'] for _ in range(3)]
        self.assertEqual(maps, [['files/item_00.txt', 'files/item_01.txt', 'files/item_02.txt']] * 3)

    def test_no_git_is_an_error_for_change_selection_only(self):
        plain = self.base / 'plain'
        plain.mkdir()
        (plain / 'file.txt').write_text('readable\n')
        self.assertEqual(self.run_cli('--changed', 'all', root=plain).returncode, 2)
        self.assertEqual(self.report('file.txt', root=plain)['sources'][0]['content'], 'readable\n')

    def test_change_selection_disables_filters_and_preserves_index(self):
        self.write('file.py', 'VALUE = 1\n')
        self.write('.gitattributes', '*.py filter=probe diff=probe\n')
        self.commit()
        self.write('file.py', 'VALUE = 2\n')
        marker = self.base / 'executed'
        helper = self.base / 'helper.sh'
        helper.write_text('#!/bin/sh\ntouch ' + shlex.quote(str(marker)) + '\ncat\n')
        helper.chmod(0o700)
        for name in ('filter.probe.clean', 'filter.probe.process', 'diff.probe.textconv',
                     'diff.external', 'core.fsmonitor'):
            self.git('config', name, str(helper))
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        report = self.report('--changed', 'all')
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse(marker.exists())
        self.assertIn('file.py', [c['path'] for c in report['changes']])

    def test_cache_is_fresh_between_invocations(self):
        self.write('go.mod', 'module example.test/one\n')
        self.write('main.go', 'package main\nimport "example.test/one/shared"\n')
        self.write('shared/value.go', 'package shared\nconst Value = 1\n')
        first = self.report('main.go')
        self.write('shared/value.go', 'package shared\nconst Value = 9\n')
        second = self.report('main.go')
        body = lambda r: next(s['content'] for s in r['sources'] if s['path'] == 'shared/value.go')
        self.assertIn('Value = 1', body(first))
        self.assertIn('Value = 9', body(second))

    def test_shared_package_manifest_is_not_reread_for_every_source(self):
        self.write('go.mod', 'module example.test/one\n')
        for index in range(10):
            self.write(f'pkg/file{index}.go', f'package pkg\nfunc Value{index}() int {{ return {index} }}\n')
        reads = []
        original = Path.open

        def counted(path, mode='r', *args, **kwargs):
            if mode == 'rb' and path == self.root / 'go.mod':
                reads.append(path)
            return original(path, mode, *args, **kwargs)

        output = io.StringIO()
        with mock.patch.object(Path, 'open', counted), redirect_stdout(output), mock.patch.object(
                sys, 'argv', [str(SCRIPT), '--root', str(self.root), 'pkg/file0.go', '--format', 'json']):
            runpy.run_path(str(SCRIPT), run_name='__main__')
        report = json.loads(output.getvalue())
        self.assertEqual(len([s for s in report['sources'] if s['path'].endswith('.go')]), 10)
        self.assertLessEqual(len(reads), 2, 'Manifest should be read for source output and once for import hints')


if __name__ == '__main__':
    unittest.main()
