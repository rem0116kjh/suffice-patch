"""Bounded Git inspection without configured filters, diff helpers or hooks."""
import os
from pathlib import Path


def prepare_git(root, run, notices):
    git = ['git', '--no-optional-locks', '--no-pager', '--literal-pathspecs',
           '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=/dev/null',
           '-c', 'color.ui=false', '-c', 'diff.ignoreSubmodules=all']
    try:
        code, output, _, overflow, timed_out = run(
            [*git, 'config', '--null', '--name-only', '--get-regexp',
             r'^filter\..*\.(clean|process|required)$'], root)
    except OSError as error:
        notices.append('Git inspection skipped: ' + type(error).__name__)
        return None
    if code not in (0, 1) or overflow or timed_out:
        notices.append('Git inspection skipped: filter configuration unavailable.')
        return None
    drivers = {key.rsplit('.', 1)[0] for key in output.decode(errors='replace').split('\0') if key}
    for driver in sorted(drivers):
        git += ['-c', driver + '.clean=', '-c', driver + '.process=', '-c', driver + '.required=false']
    if drivers:
        notices.append('Git clean/process filters disabled; diffs use raw working-tree content.')
    return git


def changed_files(git, root, scopes, mode, untracked, limit, timeout, run, notices):
    """Return complete porcelain records only; failure is not a clean worktree."""
    if git is None:
        raise ValueError('Git change selection unavailable; specify explicit targets instead.')
    try:
        code, output, _, overflow, timed_out = run([*git, 'rev-parse', '--show-toplevel'], root,
                                                   timeout=timeout)
        if code or overflow or timed_out:
            raise ValueError('--changed requires a Git working tree')
        # Porcelain v1 paths are relative to the Git top level, even with a nested --root.
        git_root = Path(os.fsdecode(output[:-1] if output.endswith(b'\n') else output)).resolve()
        command = [*git, 'status', '--porcelain=v1', '-z', '--ignore-submodules=all',
                   '--untracked-files=' + ('all' if untracked else 'no'), '--',
                   *[str(p) for p in (scopes or [root])]]
        code, output, _, overflow, timed_out = run(command, root, timeout=timeout,
                                                   cap=min(131072, max(8192, limit * 512)))
    except OSError as error:
        raise ValueError('Git change selection unavailable: ' + type(error).__name__) from error
    if code and not (overflow or timed_out):
        raise ValueError('Git change selection failed; specify explicit targets instead.')
    if overflow or timed_out:
        notices.append('Git change selection truncated or timed out; selected changes are incomplete.')
    rows = iter(output.split(b'\0')[:-1])
    changes = []
    for row in rows:
        if len(row) < 4 or row[2:3] != b' ':
            notices.append('Incomplete Git status record omitted.')
            continue
        status = row[:2].decode('ascii', errors='replace')
        name = os.fsdecode(row[3:])
        original = None
        if 'R' in status or 'C' in status:
            previous = next(rows, None)
            if previous is None:
                notices.append('Incomplete Git rename record omitted.')
                break
            original = os.fsdecode(previous)
        if status == '??':
            selected = untracked and mode != 'staged'
        else:
            selected = (mode == 'all' or (mode == 'staged' and status[0] != ' ')
                        or (mode == 'worktree' and status[1] != ' '))
        if not selected:
            continue
        paths = []
        for value in (name, original):
            if value is None:
                continue
            try:
                path = git_root / value
                resolved = path.resolve()
                if (path.is_relative_to(root) and resolved.is_relative_to(root)
                        and (not scopes or any(path.is_relative_to(p) and resolved.is_relative_to(p) for p in scopes))):
                    paths.append(str(path.relative_to(root)))
                else:
                    paths.append(None)
            except (OSError, RuntimeError):
                paths.append(None)
        if not paths or paths[0] is None:
            notices.append('Changed path outside root/scope or unresolved; not read: ' + name)
            continue
        if len(changes) >= limit:
            notices.append(f'Git change selection limit reached; only {limit} records retained.')
            break
        changes.append({'path': paths[0], 'status': status,
                        'original_path': paths[1] if len(paths) > 1 else None})
    return changes
