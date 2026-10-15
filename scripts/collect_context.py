#!/usr/bin/env python3
"""Collect bounded source, local dependencies, textual references, and Git changes.

Read-only: project code, dependency managers, builds, and tests are never executed.
"""
import argparse
from collections import deque
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import threading

# A sibling module keeps language heuristics separate from traversal and budgets.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from context_languages import AnalysisCache, analyze, discover_manifests, language_for, SUPPORTED_SUFFIXES
from context_git import changed_files, prepare_git

VERSION = '5.0.0'

EXCLUDED_DIRS = ('.git', '.agents', '.claude', 'node_modules', 'vendor', '.venv', 'venv',
                 '__pycache__', '.next', '.nuxt', '.cache', 'dist', 'build', 'target',
                 'coverage', 'Pods', '.gradle', 'bin', 'obj')
GENERIC_NAMES = {'index', 'main', 'lib', 'mod', '__init__', 'package', 'config', 'test', 'tests'}


def bounded_command(command, cwd, timeout=5, cap=16000):
    """Drain both pipes concurrently with bounded memory, terminating on overflow."""
    proc = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    buffers = [bytearray(), bytearray()]
    overflow = threading.Event()

    def drain(stream, index, limit):
        try:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    break
                available = limit - len(buffers[index])
                buffers[index].extend(chunk[:max(0, available)])
                if len(chunk) > available:
                    overflow.set()
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass
                    break
        finally:
            stream.close()

    readers = [threading.Thread(target=drain, args=(proc.stdout, 0, cap), daemon=True),
               threading.Thread(target=drain, args=(proc.stderr, 1, 2000), daemon=True)]
    for thread in readers:
        thread.start()
    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        proc.wait()
    for thread in readers:
        thread.join(timeout=1)
    return proc.returncode, bytes(buffers[0]), bytes(buffers[1]), overflow.is_set(), timed_out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('targets', nargs='*', help='Repository-relative files, directories, or Python modules/functions')
    parser.add_argument('--version', action='version', version='SufficePatch ' + VERSION)
    parser.add_argument('--changed', choices=('all', 'staged', 'worktree'), help='Select changed tracked files; sources always reflect the working tree')
    parser.add_argument('--include-untracked', action='store_true', help='Also select untracked files with --changed all/worktree')
    parser.add_argument('--format', choices=('text', 'json'), default='text')
    parser.add_argument('--summary', action='store_true', help='Return paths, hashes and notices without source bodies or diffs')
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--max-files', type=int, default=16)
    parser.add_argument('--max-bytes', type=int, default=40000)
    parser.add_argument('--scope', action='append', default=[], help='Limit file discovery/reference search to this directory; repeatable')
    parser.add_argument('--symbol', action='append', default=[], help='Search an exact identifier instead of inferred target identifiers')
    parser.add_argument('--max-search-matches', type=int, default=200)
    parser.add_argument('--search-timeout', type=float, default=5)
    args = parser.parse_args()
    if not args.targets and not args.changed:
        parser.error('provide targets or --changed all/staged/worktree')
    if args.include_untracked and args.changed not in ('all', 'worktree'):
        parser.error('--include-untracked requires --changed all or worktree')
    root = args.root.resolve()
    if not root.is_dir():
        parser.error('root must be an existing directory')
    if not math.isfinite(args.search_timeout) or min(args.max_files, args.max_bytes, args.max_search_matches, args.search_timeout) <= 0:
        parser.error('limits must be positive')
    if any(not re.fullmatch(r'[\w$][\w$.-]{0,127}', s) for s in args.symbol):
        parser.error('symbols must be identifiers of at most 128 characters')
    loaded, pending, notices = {}, deque(), []
    seen_paths, seen_files, target_symbols = set(), set(), {}
    remaining = args.max_bytes
    analysis_cache = AnalysisCache(root)
    report = {'schema_version': 1, 'version': VERSION, 'root': str(root),
              'summary': args.summary, 'file_map': [], 'changes': [], 'sources': [],
              'git': {}, 'search': {}, 'notices': []}

    def inside(path):
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError):
            return None
        return resolved if resolved.is_relative_to(root) else None

    def relative(path):
        return str(path.relative_to(root))

    scopes = []
    for name in args.scope:
        path = inside(root / name)
        if path is None or not path.is_dir():
            parser.error('scope must be an existing directory inside root: ' + name)
        if path not in scopes:
            scopes.append(path)

    git = prepare_git(root, bounded_command, notices)
    if args.changed:
        try:
            report['changes'] = changed_files(git, root, scopes, args.changed, args.include_untracked,
                                               args.max_search_matches, args.search_timeout,
                                               bounded_command, notices)
        except ValueError as error:
            parser.error(str(error))
        notices.append('Changed-file selection uses Git status; source bodies are current working-tree files, including unstaged edits.')
        if not report['changes']:
            notices.append('No matching Git changes selected; no repository-wide source fallback.')

    def add(path, reason):
        if path in seen_paths:
            return
        seen_paths.add(path)
        resolved = inside(path)
        if resolved is None:
            notices.append(f'Outside root, not read: {path}')
        elif resolved not in seen_files and resolved.is_file():
            seen_files.add(resolved)
            pending.append((resolved, reason))

    def resolve_target(name):
        direct = inside(root / name)
        if direct and direct.exists():
            return direct
        parts = name.split('.')
        for size in range(len(parts), 0, -1):
            for base_dir in (root, root / 'src'):
                base = base_dir.joinpath(*parts[:size])
                for candidate in (base.with_suffix('.py'), base / '__init__.py'):
                    found = inside(candidate)
                    if found and found.is_file():
                        return found
        return None

    targets, directories = [], []
    for name in args.targets:
        target = resolve_target(name)
        if target is None:
            notices.append(f'Target not found inside root: {name}')
        elif target.is_dir():
            if target not in directories:
                directories.append(target)
        elif target not in targets:
            targets.append(target)
    explicit_targets = set(targets)
    changed_paths = []
    for change in report['changes']:
        for name in (change['path'], change['original_path']):
            if name is None:
                continue
            path = root / name
            changed_paths.append(name)
            if path.is_dir():
                notices.append('Changed directory/submodule not loaded: ' + name)
            elif path not in targets:
                targets.append(path)
                if not path.is_file():
                    notices.append('Deleted or missing changed source; inspect its diff and references: ' + name)
    if not targets and not directories and not args.changed:
        parser.error('; '.join(notices))

    def rg_base():
        command = ['rg', '--no-config', '--hidden']
        for directory in EXCLUDED_DIRS:
            command.extend(['--glob', '!' + directory + '/**', '--glob', '!**/' + directory + '/**'])
        command.extend(['--sort', 'path', '--glob', '!*.min.*', '--glob', '!*.map', '--glob', '!*.lock', '--glob', '!package-lock.json'])
        return command

    def search_paths(command, label):
        try:
            code, output, error, overflow, timed_out = bounded_command(
                command, root, args.search_timeout, min(131072, max(8192, args.max_search_matches * 512)))
        except OSError as error:
            notices.append(f'{label} unavailable: {type(error).__name__}')
            return []
        # Only complete NUL-terminated paths are usable after truncation/timeout.
        rows = output.split(b'\0')[:-1]
        paths, path_seen = [], set()
        for row in rows:
            path = inside(root / os.fsdecode(row))
            if path and path not in path_seen and path.is_file():
                path_seen.add(path)
                paths.append(path)
                if len(paths) > args.max_search_matches:
                    break
        if len(paths) > args.max_search_matches:
            overflow = True
        if overflow:
            notices.append(f'{label} limit reached; only up to {args.max_search_matches} candidates retained. Narrow --scope or --symbol.')
        if timed_out:
            notices.append(f'{label} timed out; results are incomplete. Narrow --scope.')
        if code not in (0, 1) and not (overflow or timed_out):
            notices.append(label + ' failed: ' + error.decode(errors='replace')[:300])
        return sorted(paths[:args.max_search_matches])

    if directories:
        map_roots = scopes or directories
        paths = search_paths([*rg_base(), '--files', '--null', '--', *[relative(p) for p in map_roots]], 'File discovery')
        # Keep directory maps useful without dumping generated or binary assets.
        for path in paths:
            report['file_map'].append(relative(path))
        notices.append('Directory target: choose specific files from the map and run again; no directory contents were loaded automatically.')

    # Explicit targets get priority; scoped discovery never silently expands them.
    for target in targets:
        add(target, 'requested target' if target in explicit_targets else 'Git changed target')
    for target in targets:
        for directory in [target.parent, *target.parent.parents]:
            if not directory.is_relative_to(root):
                break
            add(directory / 'AGENTS.md', 'project instructions')
        for manifest in discover_manifests(target, root):
            add(manifest, 'project manifest; inspect declared checks without executing it')

    def drain():
        nonlocal remaining
        while pending:
            if len(loaded) >= args.max_files:
                notices.append('File limit reached; additional context may exist.')
                return
            path, reason = pending.popleft()
            try:
                with path.open('rb') as stream:
                    raw = stream.read(remaining + 1)
            except OSError as error:
                notices.append(f'Source unavailable: {relative(path)} ({type(error).__name__})')
                continue
            if len(raw) > remaining:
                notices.append(f'Byte limit: source omitted, not truncated: {relative(path)}')
                continue
            if b'\0' in raw:
                notices.append(f'Binary source omitted: {relative(path)}')
                continue
            try:
                source = raw.decode('utf-8')
            except UnicodeDecodeError:
                notices.append(f'Non-UTF-8 source omitted: {relative(path)}')
                continue
            remaining -= len(raw)
            loaded[path] = (source, reason, hashlib.sha256(raw).hexdigest())
            symbols, imports, warnings = analyze(path, source, root, cache=analysis_cache)
            if path in targets:
                target_symbols[path] = symbols
            notices.extend(warnings)
            for dependency in imports:
                add(dependency, 'local import')

    drain()
    if targets:
        symbols = set(args.symbol)
        if not symbols:
            for path in targets:
                if path.stem not in GENERIC_NAMES:
                    symbols.add(path.stem)
                symbols.update(target_symbols.get(path, ()))
        symbols = {s for s in symbols if s and len(s) <= 128}
        if len(symbols) > 32:
            notices.append('Symbol limit reached; searching 32 identifiers. Use --symbol for a specific operation.')
        symbols = sorted(symbols)[:32]
        if len(loaded) >= args.max_files or remaining == 0:
            notices.append('File limit reached; caller/test search skipped. Additional context may exist.')
        elif symbols:
            pattern = r'(^|[^\w$])(?:' + '|'.join(re.escape(s) for s in symbols) + r')([^\w$]|$)'
            command = ['rg', '--no-config', '--hidden', '-l', '--null']
            for suffix in sorted(SUPPORTED_SUFFIXES):
                command += ['--glob', '*' + suffix]
            command += ['--glob', 'Dockerfile', '--glob', 'Makefile', *rg_base()[3:], '--', pattern,
                        *[relative(p) for p in (scopes or [root])]]
            matches = search_paths(command, 'Caller/test search')
            for path in matches:
                add(path, 'matching caller or test; textual match')
            report['search']['matching_files'] = len(matches)
        else:
            notices.append('No specific target symbols found; use --symbol or inspect references directly.')
        drain()
    report['source_count'] = len(loaded)
    report['source_bytes'] = args.max_bytes - remaining
    report['languages'] = sorted({language_for(p) for p in targets})
    report['limits'] = {'max_files': args.max_files, 'max_bytes': args.max_bytes,
                        'max_search_matches': args.max_search_matches, 'search_timeout': args.search_timeout}
    for path, (source, reason, digest) in loaded.items():
        item = {'path': relative(path), 'reason': reason, 'sha256': digest,
                'language': language_for(path), 'bytes': len(source.encode('utf-8'))}
        if not args.summary:
            item['content'] = source
        report['sources'].append(item)

    git_paths = list(dict.fromkeys([*[relative(p) for p in loaded], *changed_paths]))
    if git is not None and git_paths:
        commands = [('GIT STATUS', [*git, 'status', '--short', '--ignore-submodules=all', '--', '.'])]
        if args.summary:
            notices.append('Summary mode: source bodies and Git diffs omitted; request full context before editing.')
        else:
            commands += [('GIT DIFF', [*git, 'diff', '--no-ext-diff', '--no-textconv', '--ignore-submodules=all', '--', *git_paths]),
                         ('GIT STAGED DIFF', [*git, 'diff', '--no-ext-diff', '--no-textconv', '--ignore-submodules=all', '--cached', '--', *git_paths])]
        for title, command in commands:
            try:
                code, output, error, overflow, timed_out = bounded_command(command, root, cap=12000)
                report['git'][title] = {'output': output.decode(errors='replace'), 'returncode': code,
                                         'truncated': overflow, 'timed_out': timed_out}
                if code and not (overflow or timed_out):
                    notices.append(title + ' unavailable: ' + error.decode(errors='replace')[:300])
                if overflow or timed_out:
                    notices.append(title + ' truncated or timed out; read the relevant full diff before editing.')
            except OSError as error:
                notices.append(title + ' unavailable: ' + type(error).__name__)
    elif not git_paths:
        notices.append('Git inspection skipped: no source loaded; no repository-wide fallback.')
    notices.append('References are textual candidates, not a complete call graph. Dynamic imports, aliases, generated code, and external packages may need targeted follow-up.')
    notice_budget = 6000
    for notice in dict.fromkeys(notices):
        text = notice[:500]
        if len(text) + 1 > notice_budget:
            report['notices'].append('Further notices omitted; narrow the targets or scope.')
            break
        report['notices'].append(text)
        notice_budget -= len(text) + 1
    if args.format == 'json':
        # ASCII escaping also round-trips filesystem names containing surrogate bytes.
        print(json.dumps(report, ensure_ascii=True, separators=(',', ':')))
        return
    if directories:
        print('FILE MAP (bounded paths; contents are not loaded):')
        for path in report['file_map']:
            print('PATH: ' + path[:400])
    for change in report['changes']:
        print('CHANGE: ' + change['status'] + ' ' + json.dumps(change['path'], ensure_ascii=True))
    if 'matching_files' in report['search']:
        print(f"Caller/test search: {report['search']['matching_files']} matching files (textual, not a complete call graph).")
    print(f"ROOT: {root}\nSources returned: {len(loaded)}; source bytes: {report['source_bytes']}")
    if targets:
        print('Languages: ' + ', '.join(report['languages']))
    for item in report['sources']:
        print(f"\nFILE: {item['path']} | {item['reason']} | SHA256: {item['sha256']}")
        if 'content' in item:
            print(item['content'])
    for title, item in report['git'].items():
        print(f"\n{title}:\n{item['output']}")
    print('\nLIMITS / FOLLOW-UP:')
    for notice in report['notices']:
        print(notice)


if __name__ == '__main__':
    main()
