"""Bounded, verified text handoffs from the current collaboration only."""
import hashlib
import os
from pathlib import Path

TEXT_TYPES = {'.txt', '.md', '.json', '.csv', '.py', '.js', '.css'}
MAX_BYTES = 1024 * 1024
MAX_FILES = 12


def snapshot_files(workspace):
    from studio import safe_file, Problem
    folder = workspace / 'artifacts'
    if folder.is_symlink() or not folder.is_dir():
        return {}
    found = {}
    for root, dirs, files in os.walk(folder, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not (Path(root) / d).is_symlink())
        for name in sorted(files):
            if Path(name).suffix.lower() not in TEXT_TYPES:
                continue
            relative = str((Path(root) / name).relative_to(workspace))
            try:
                path = safe_file(workspace, relative, True)
                if path.stat().st_size > MAX_BYTES:
                    continue
                raw = path.read_bytes()
                if not raw.decode('utf-8').strip():
                    continue
                found[relative] = (hashlib.sha256(raw).hexdigest(), path.stat().st_mtime_ns)
            except (Problem, OSError, UnicodeError):
                continue
    return found


def collect_files(studio, owner, job_id, role, before, source_map=None):
    from studio import safe_file, Problem
    workspace = studio.workspace(owner, role)
    paths, total = [], 0
    for relative, signature in snapshot_files(workspace).items():
        if before.get(relative) == signature:
            continue
        try:
            raw = safe_file(workspace, relative, True).read_bytes()
            if hashlib.sha256(raw).hexdigest() != signature[0]:
                continue
            if len(paths) >= MAX_FILES or total + len(raw) > MAX_BYTES:
                raise RuntimeError('The contribution exceeds the handoff limit (12 text files / 1 MB). Split the task and retry.')
            target = ('artifacts/shared-' + job_id + '-r' + str(role) + '-' + signature[0][:12]
                      + '-' + str(len(paths)) + Path(relative).suffix.lower())
            safe_file(studio.workspace(owner), target).write_bytes(raw)
            if source_map is not None:
                source_map[target] = relative
            paths.append(target)
            total += len(raw)
        except (Problem, OSError):
            continue
    return paths
