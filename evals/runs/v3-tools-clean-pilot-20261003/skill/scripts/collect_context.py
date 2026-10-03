#!/usr/bin/env python3
"""Read bounded Python context and Git changes. Never import project code or write files."""
import argparse
import ast
import hashlib
import re
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('targets', nargs='+', help='Repository-relative files or Python modules/functions')
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--max-files', type=int, default=16)
    parser.add_argument('--max-bytes', type=int, default=40000)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.max_files < 1 or args.max_bytes < 1:
        parser.error('limits must be positive')
    loaded, pending, notices = {}, [], []
    remaining = args.max_bytes

    def inside(path):
        resolved = path.resolve()
        return resolved if resolved.is_relative_to(root) else None

    def add(path, reason):
        resolved = inside(path)
        if resolved is None:
            notices.append(f'Outside root, not read: {path}')
        elif resolved.is_file() and resolved not in loaded and all(p != resolved for p, _ in pending):
            pending.append((resolved, reason))

    def resolve_target(name):
        direct = inside(root / name)
        if direct and direct.is_file():
            return direct
        parts = name.split('.')
        for size in range(len(parts), 0, -1):
            base = root.joinpath(*parts[:size])
            for candidate in (base.with_suffix('.py'), base / '__init__.py'):
                found = inside(candidate)
                if found and found.is_file():
                    return found
        return None

    targets = []
    for name in args.targets:
        target = resolve_target(name)
        if target is None:
            notices.append(f'Target not found inside root: {name}')
        else:
            targets.append(target)
            add(target, 'requested target')
            for directory in [target.parent, *target.parent.parents]:
                if not directory.is_relative_to(root):
                    break
                add(directory / 'AGENTS.md', 'project instructions')
    if not targets:
        parser.error('; '.join(notices))

    def drain():
        nonlocal remaining
        while pending:
            path, reason = pending.pop(0)
            if len(loaded) >= args.max_files:
                notices.append('File limit reached; additional context may exist.')
                return
            with path.open('rb') as stream:
                raw = stream.read(remaining + 1)
            if len(raw) > remaining:
                notices.append(f'Byte limit: source omitted, not truncated: {path.relative_to(root)}')
                continue
            try:
                source = raw.decode('utf-8')
            except UnicodeDecodeError:
                notices.append(f'Non-UTF-8 source omitted: {path.relative_to(root)}')
                continue
            remaining -= len(raw)
            loaded[path] = (source, reason, hashlib.sha256(raw).hexdigest())
            if path.suffix != '.py':
                continue
            try:
                tree = ast.parse(source)
            except SyntaxError:
                notices.append(f'Import scan unavailable: {path.relative_to(root)} has a syntax error.')
                continue
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [(root, alias.name) for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    base = path.parent if node.level else root
                    for _ in range(max(0, node.level - 1)):
                        base = base.parent
                    modules = [(base, node.module or '')]
                    modules += [(base, '.'.join(filter(None, [node.module, alias.name]))) for alias in node.names]
                for base, module in modules:
                    candidate = base.joinpath(*module.split('.')) if module else base
                    if module:
                        add(candidate.with_suffix('.py'), 'local import')
                    add(candidate / '__init__.py', 'local import')

    drain()
    symbols = set()
    for path in targets:
        symbols.add(path.stem)
        if path in loaded:
            try:
                tree = ast.parse(loaded[path][0])
                symbols.update(n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
            except SyntaxError:
                pass
    pattern = r'\b(?:' + '|'.join(re.escape(s) for s in sorted(symbols)) + r')\b'
    search_args = ['rg', '-l', '--null', '--glob', '*.py', '--glob', '!.agents/**',
                   '--glob', '!node_modules/**', '--glob', '!.venv/**', '--', pattern, '.']
    try:
        found = subprocess.run(search_args, cwd=root, capture_output=True, timeout=10)
        if found.returncode in (0, 1):
            matches = [root / name.decode() for name in found.stdout.split(b'\0') if name]
            for path in sorted(matches):
                add(path, 'matching caller or test; textual match')
            print(f'Caller/test search: {len(matches)} matching Python files (textual, not a complete call graph).')
        else:
            notices.append('Caller/test search failed: ' + found.stderr.decode(errors='replace')[:500])
    except (OSError, subprocess.TimeoutExpired) as error:
        notices.append(f'Caller/test search unavailable: {type(error).__name__}')
    drain()
    print(f'ROOT: {root}\nSources returned: {len(loaded)}; source bytes: {args.max_bytes - remaining}')
    for path, (source, reason, digest) in loaded.items():
        print(f'\nFILE: {path.relative_to(root)} | {reason} | SHA256: {digest}\n{source}', end='\n')
    for title, command in [('GIT STATUS', ['git', '--no-optional-locks', 'status', '--short']),
                           ('GIT DIFF', ['git', '--no-optional-locks', 'diff', '--', *[str(p.relative_to(root)) for p in loaded]]),
                           ('GIT STAGED DIFF', ['git', '--no-optional-locks', 'diff', '--cached', '--', *[str(p.relative_to(root)) for p in loaded]])]:
        try:
            result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=10)
            print(f'\n{title}:\n{result.stdout[:12000]}')
            if result.returncode:
                notices.append(title + ' unavailable: ' + result.stderr[:300])
            if len(result.stdout) > 12000:
                notices.append(title + ' truncated; read the relevant full diff before editing.')
        except (OSError, subprocess.TimeoutExpired) as error:
            notices.append(title + ' unavailable: ' + type(error).__name__)
    if notices:
        print('\nLIMITS / FOLLOW-UP:\n' + '\n'.join(dict.fromkeys(notices)))
    else:
        print('\nNo context limit was reached. Dynamic callers and non-Python tests may still require inspection.')


if __name__ == '__main__':
    main()
