"""Read and explicitly edit the selected agent's workspace Markdown files."""
import hashlib
from pathlib import Path

CORE_DOCUMENTS=(('SOUL.md','Personality & role'),('IDENTITY.md','Identity'),
                ('AGENTS.md','Working instructions'),('USER.md','User preferences'),
                ('MEMORY.md','Saved memory'))
OPTIONAL_DOCUMENTS=(('TOOLS.md','Tool notes'),('HEARTBEAT.md','Periodic instructions'))
MAX_BYTES=128000


def read_documents(studio, owner, role=None):
    from studio import Problem, ROLES, ROLE_SKILLS, safe_file
    from agent_runtime import SKILLS
    if role is not None and (type(role) is not int or not 0 <= role < len(ROLES)):
        raise Problem('Choose a valid crew member.')
    with studio.db() as db:
        row=db.execute('SELECT deleting FROM agents WHERE id=?',(owner,)).fetchone()
    if not row:raise Problem('Agent not found.',404)
    if row['deleting']:raise Problem('This agent is being deleted.',409)
    if role is None:
        profile=studio.profile(owner)
        if not profile:raise Problem('Choose a hired agent.',404)
        name=profile['name'];description=profile.get('purpose') or 'Personal agent';skills=profile['skills']
    else:
        from studio import CREW_CATALOG
        from scenarios import crew_member
        member = crew_member(CREW_CATALOG[role], studio.crew_scenario(owner))
        name,description = member['name'],member['collaboration']['description']
        skills=ROLE_SKILLS[role]
    workspace=studio.workspace(owner,role)
    requested=[(name,title,'agent') for name,title in CORE_DOCUMENTS]
    requested += [(name,title,'agent') for name,title in OPTIONAL_DOCUMENTS if (workspace/name).exists()]
    requested += [('skills/bac-'+key+'/SKILL.md',SKILLS[key][0],'skill') for key in skills if key in SKILLS]
    documents=[]
    for relative,title,group in requested:
        document={'path':relative,'filename':Path(relative).name,'title':title,'group':group}
        try:
            if workspace.is_symlink():raise ValueError('Linked workspace')
            target=safe_file(workspace,relative)
            if not target.exists():
                document.update(status='missing', revision='missing')
            else:
                target=safe_file(workspace,relative,True)
                with target.open('rb') as handle:raw=handle.read(MAX_BYTES+1)
                if len(raw)>MAX_BYTES:raise ValueError('Large document')
                document.update(status='ready',content=raw.decode('utf-8'),updated=target.stat().st_mtime,
                                revision=hashlib.sha256(raw).hexdigest())
        except (OSError,ValueError,Problem):
            document.update(status='unavailable')
        documents.append(document)
    return {'name':name,'description':description,'role':role,'documents':documents}


def save_documents(studio, owner, data, role=None):
    from studio import Problem, safe_file
    from document_edits import atomic_write, edited_paths, mark_edited, MARKER
    changes = data.get('documents')
    if not isinstance(changes, list) or not 1 <= len(changes) <= 32:
        raise Problem('Choose the documents to save.')
    paths = []
    for change in changes:
        if not isinstance(change, dict) or not isinstance(change.get('path'), str):
            raise Problem('Choose a valid document.')
        content = change.get('content')
        if not isinstance(content, str) or '\x00' in content or len(content.encode('utf-8')) > MAX_BYTES:
            raise Problem('Each document must be UTF-8 text up to 128 KB.')
        if not isinstance(change.get('revision'), str):
            raise Problem('Reload the file before saving it.', 409)
        paths.append(change['path'])
    if len(set(paths)) != len(paths):
        raise Problem('Choose each document only once.')
    with studio.heartbeat.lock:
        # Preflight before native I/O, then repeat under the job/deletion fence.
        read_documents(studio, owner, role)
        with studio.db() as db:
            studio.require_idle(db, owner)
            studio.require_bac_not_resetting(db, owner)
        profile = studio.profile(owner) if role is None else None
        if profile and 'radar' in profile.get('skills', []):
            studio.heartbeat.disable(profile['id'])
        with studio.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if role is None:
                studio.require_available(db, owner)
            elif db.execute('SELECT 1 FROM agent_policies WHERE owner=? AND updating=1', (owner,)).fetchone():
                raise Problem('Wait for the policy update to finish.', 409)
            studio.require_idle(db, owner)
            studio.require_bac_not_resetting(db, owner)
            snapshot = read_documents(studio, owner, role)
            allowed = {doc['path']: doc for doc in snapshot['documents']}
            workspace = studio.workspace(owner, role)
            if workspace.is_symlink():
                raise Problem('Linked workspaces cannot be edited.')
            edited_paths(workspace)
            writes = []
            for change in changes:
                doc = allowed.get(change['path'])
                if not doc or doc['status'] not in ('ready', 'missing'):
                    raise Problem('Only the Markdown files shown for this agent can be edited.')
                if change['revision'] != doc['revision']:
                    raise Problem(doc['filename'] + ' changed elsewhere. Your draft is still here; discard its changes to load the latest file.', 409)
                target = safe_file(workspace, change['path'])
                writes.append((target, target.read_bytes() if target.exists() else None, change['content'].encode('utf-8')))
            workspace.mkdir(parents=True, exist_ok=True)
            marker = workspace / MARKER
            previous_marker = marker.read_bytes() if marker.exists() else None
            try:
                mark_edited(workspace, paths)
                for target, _, content in writes:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    atomic_write(target, content)
                native_id = profile['id'] if profile else studio.crew_native_id(owner, role)
                studio.provisioned.discard(native_id)
                if profile:
                    db.execute("DELETE FROM jobs WHERE owner=? AND kind='prepare-agent' AND status='queued'", (owner,))
                    studio.queue_agent_preparation(db, owner, profile)
            except Exception:
                for target, previous, _ in writes:
                    if previous is None:
                        target.unlink(missing_ok=True)
                    else:
                        atomic_write(target, previous)
                if previous_marker is None:
                    marker.unlink(missing_ok=True)
                else:
                    atomic_write(marker, previous_marker)
                raise
    studio.signal.set()
    return read_documents(studio, owner, role)
