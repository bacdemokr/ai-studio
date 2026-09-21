"""Explicit host-file grants, transferred through a protected agent's workspace.

OpenShell never mounts the host home directory. A read grant imports a snapshot;
a write grant also permits checked write-back to that exact file after a turn.
"""
import hashlib
import os
from pathlib import Path
import re
import stat

LIMIT = 10 * 1024 * 1024


def file_rule(key):
    parts = key.split(':', 2)
    if len(parts) != 3 or parts[0] != 'file' or parts[1] not in ('read', 'write'):
        raise ValueError('Choose a file read or read/write permission.')
    access, value = parts[1:]
    path = Path(value)
    if (not path.is_absolute() or str(path) != value or '..' in path.parts
            or any(ord(c) < 32 for c in value) or len(value) > 4096 or value == '/'):
        raise ValueError('Choose an exact absolute file path, without traversal.')
    return {'title': value, 'description': 'Read a protected copy' if access == 'read' else 'Read and save changes to this file',
            'hosts': [], 'path': value, 'access': access, 'kind': 'file'}


def requested_files(prompt):
    # Paths must originate in the user's request, never in model output.
    matches = re.findall(r'''`(/[^`\n]+)`|"(/[^"\n]+)"|'(/[^'\n]+)'|(?<![\w:/])(/[^\s<>`"?]+)''', prompt)
    result = set()
    for match in matches:
        # Quoted paths are exact; punctuation stripping only applies to prose.
        value = next(x for x in match if x)
        if match[-1]:
            value = value.rstrip('.,;!?)')
        try:
            file_rule('file:read:' + value)
            result.add(value)
        except ValueError:
            pass
    return sorted(result)


def proposed_files(prompt, answer):
    """Untrusted model suggestions, requiring an explicit exact-path confirmation.

    Only accept a filename actually mentioned by the user and a permission request;
    never promote arbitrary paths in retrieved/model text into approvals.
    """
    if not re.search(r'permission|approval|approve|권한|승인', answer, re.I):
        return []
    return [path for path in requested_files(answer)
            if re.search(r'(?<![\w./])' + re.escape(Path(path).name) + r'(?![\w./])', prompt)
            and Path(path).suffix]


def requested_directories(prompt):
    """Only unambiguous single-path folder creation requests, plus existing folders."""
    paths = requested_files(prompt)
    explicit = re.search(r'\b(?:folder|directory|mkdir)\b|폴더|디렉토리', prompt, re.I)
    create = re.search(r'\b(?:create|creaet|make|mkdir)\b|만들|생성', prompt, re.I)
    return [p for p in paths if Path(p).is_dir() or (len(paths) == 1 and explicit and create)]


def checked_path(value, allow_missing=False):
    file_rule('file:read:' + value)
    path = Path(value)
    for item in [*reversed(path.parents), path]:
        if item.is_symlink():
            raise ValueError('Symbolic links are not supported for host-file grants: '
                             + str(item) + '. Enter the real file path on the host.')
    if not path.parent.is_dir():
        raise ValueError('The file’s parent directory must exist.')
    if not path.exists():
        if allow_missing:
            return path
        raise ValueError('The requested file does not exist on this host.')
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        raise ValueError('Approve a regular file, not a directory, device or linked file.')
    if st.st_size > LIMIT:
        raise ValueError('Host-file transfers are limited to 10 MB per file.')
    return path


def request_issue(path, prompt):
    """Validate host metadata only; a permission cannot repair an invalid path."""
    creation = bool(re.search(r'\b(create|write|save|make|generate)\b|만들|생성|저장|작성|써\s*줘', prompt, re.I))
    try:
        checked_path(path, allow_missing=creation)
    except (ValueError, OSError) as error:
        return {'path': path, 'reason': str(error)}
    return None


def parent_fd(path):
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in Path(path).parent.parts[1:]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_snapshot(path):
    checked_path(str(path))
    parent = parent_fd(path)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
    finally:
        os.close(parent)
    with os.fdopen(fd, 'rb') as stream:
        st = os.fstat(stream.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            raise ValueError('File type changed; request access again.')
        content = stream.read(LIMIT + 1)
    if len(content) > LIMIT:
        raise ValueError('Host-file transfer exceeds 10 MB.')
    return content


def relative_path(value):
    return 'inbox/approved-' + hashlib.sha256(value.encode()).hexdigest() + '.txt'


def prepare(workspace, approved):
    grants = {}
    for key in approved:
        if key.startswith('file:'):
            rule = file_rule(key)
            grants[rule['path']] = 'write' if rule['access'] == 'write' or grants.get(rule['path']) == 'write' else 'read'
    inbox = Path(workspace) / 'inbox'
    if inbox.is_symlink():
        raise ValueError('The workspace inbox must not be a symbolic link.')
    inbox.mkdir(exist_ok=True)
    # Expire copies that are no longer approved before the next sandbox sync.
    keep = {Path(relative_path(value)).name for value in grants}
    for old in inbox.glob('approved-*.txt'):
        if old.name not in keep:
            old.unlink()
    records = []
    for value, access in grants.items():
        path = checked_path(value, allow_missing=access == 'write')
        content = read_snapshot(path) if path.exists() else None
        target = Path(workspace) / relative_path(value)
        if target.exists() and target.is_dir():
            # A model may mistakenly mkdir the transfer path. Preserve its contents,
            # then restore the app-owned regular-file transfer slot.
            import uuid
            target.rename(target.with_name(target.name + '.invalid-directory-' + uuid.uuid4().hex[:8]))
        if target.is_symlink():
            raise ValueError('The protected file copy must not be a symbolic link.')
        target.parent.mkdir(parents=True, exist_ok=True)
        parent = parent_fd(target)
        try:
            fd = os.open(target.name, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            with os.fdopen(fd, 'wb') as stream:
                st = os.fstat(stream.fileno())
                if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
                    raise ValueError('Unsafe protected copy.')
                stream.write(content or b'')
                stream.truncate()
        finally:
            os.close(parent)
        records.append({'path': value, 'access': access, 'relative': relative_path(value), 'original': content})
    return records


def instructions(records):
    lines = ['Current host-file grants: use ONLY the protected workspace copies below. The host paths are not mounted. Read-only copies never write back. Approved read/write copies are saved back after this turn if the host file has not changed. Use sandbox exec for these copies. These grants support regular FILES ONLY, never directories. Never mkdir a protected copy or promise that a file grant can create or list a host folder. For folder requests explain that folder access is not supported by these controls. Basic file reading and editing needs no extra skill. If the user gives only a filename, ask for its full host path; do not invent an example path and imply it is already awaiting approval. For any other exact host path ask for its read or read/write permission in OpenShell Policy.']
    lines += [f"{r['path']} -> {r['relative']} ({'read/write' if r['access']=='write' else 'read only'})" for r in records]
    return '\n'.join(lines)


def finish(workspace, records):
    for record in records:
        if record['access'] != 'write':
            continue
        copy = Path(workspace) / record['relative']
        if copy.is_dir():
            raise RuntimeError('The agent created a folder where a protected file copy was expected. Host folders are not supported by file approvals; the host path was not changed: ' + record['path'])
        content = read_snapshot(copy)
        if content == (record['original'] or b''):
            continue
        path = checked_path(record['path'], allow_missing=record['original'] is None)
        current = read_snapshot(path) if path.exists() else None
        if current != record['original']:
            raise RuntimeError('The host file changed during this turn; its contents were not overwritten: ' + str(path))
        # Pin the parent descriptor and reject a last-component symlink on write.
        parent = parent_fd(path)
        try:
            flags = os.O_RDWR | os.O_NOFOLLOW
            if current is None:
                flags |= os.O_CREAT | os.O_EXCL
            fd = os.open(path.name, flags, 0o600, dir_fd=parent)
            with os.fdopen(fd, 'r+b') as stream:
                st = os.fstat(stream.fileno())
                if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
                    raise RuntimeError('The host file changed; refusing to write it.')
                if current is not None and stream.read(LIMIT + 1) != current:
                    raise RuntimeError('The host file changed; refusing to overwrite it.')
                stream.seek(0)
                stream.write(content)
                stream.truncate()
        finally:
            os.close(parent)
