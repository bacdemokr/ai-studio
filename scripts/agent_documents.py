"""Read the selected agent's actual workspace definitions without provisioning it."""
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
                document.update(status='missing')
            else:
                target=safe_file(workspace,relative,True)
                with target.open('rb') as handle:raw=handle.read(MAX_BYTES+1)
                if len(raw)>MAX_BYTES:raise ValueError('Large document')
                document.update(status='ready',content=raw.decode('utf-8'),updated=target.stat().st_mtime)
        except (OSError,ValueError,Problem):
            document.update(status='unavailable')
        documents.append(document)
    return {'name':name,'description':description,'role':role,'documents':documents}
