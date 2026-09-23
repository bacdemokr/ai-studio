"""Agent-executed, workspace-only upload change detection. Summaries come from the model."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

MANIFEST = '.notes-watch-inputs.json'
STATE = '.notes-watch-state.json'
OUTBOX = 'artifacts/heartbeat-notes.json'


def read(root, name, default=None):
    root=Path(root).resolve()
    path=root/name
    if path.is_symlink():raise ValueError('Invalid notes monitor file.')
    if not path.exists():return default
    if path.is_symlink() or root not in path.resolve().parents or path.stat().st_size>500000:
        raise ValueError('Invalid notes monitor file.')
    return json.loads(path.read_text())


def save(root,name,data):
    root=Path(root).resolve()
    path=root/name
    if path.is_symlink() or root not in path.parent.resolve().parents and path.parent.resolve()!=root:
        raise ValueError('Invalid notes monitor destination.')
    path.parent.mkdir(exist_ok=True)
    temporary=path.with_name(path.name+'.tmp')
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as out:json.dump(data,out,ensure_ascii=False)
    os.replace(temporary,path)


def changes(root,state):
    manifest=read(root,MANIFEST,[])
    if not isinstance(manifest,list) or len(manifest)>80:raise ValueError('Invalid upload list.')
    rows=[]
    for name in manifest:
        if not isinstance(name,str) or not name.startswith('inbox/') or len(Path(name).parts)!=2:
            raise ValueError('Expected an uploaded file in inbox/.')
        path=root/name
        if path.is_symlink() or not path.is_file() or root not in path.resolve().parents:continue
        if path.suffix.lower() not in ('.txt','.md','.csv'):continue
        if path.stat().st_size>2*1024*1024:continue
        raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
        if state.get('seen',{}).get(name)==digest:continue
        text=raw.decode('utf-8',errors='replace')
        rows.append({'path':name,'sha256':digest,'text':text[:6000],'excerpt':len(text)>6000})
        if len(rows)==3:break
    return rows


def run(root,action):
    root=Path(root).resolve();state=read(root,STATE,{'seen':{}})
    if not isinstance(state,dict) or not isinstance(state.get('seen'),dict):raise ValueError('Invalid notes monitor state.')
    rows=changes(root,state)
    token=hashlib.sha256(json.dumps([(r['path'],r['sha256']) for r in rows]).encode()).hexdigest()
    box=read(root,OUTBOX,{'events':[]})
    if not isinstance(box,dict) or not isinstance(box.get('events'),list):raise ValueError('Invalid notes monitor output.')
    if action=='poll':
        box.update(checkedAt=time.time(),status='new-notes' if rows else 'idle')
        save(root,OUTBOX,box)
        return {'status':box['status'],'token':token,'documents':rows}
    if action!='publish':raise ValueError('Unknown notes action.')
    draft=read(root,'artifacts/notes-draft.json',{})
    if not isinstance(draft,dict):raise ValueError('Invalid notes draft.')
    answer=draft.get('answer')
    if not rows:return {'status':'idle'}
    if draft.get('token')!=token:raise ValueError('Documents changed; wait for the next heartbeat.')
    if not isinstance(answer,str) or not answer.strip() or len(answer)>1800:raise ValueError('Write a concise summary of 1-1800 characters.')
    # Publish before acknowledgement: a crash can replay detection, but not the event.
    if not any(isinstance(e,dict) and e.get('id')==token for e in box['events']):
        box['events']=(box['events']+[{'id':token,'answer':answer.strip(),'files':[r['path'] for r in rows],'created':time.time()}])[-50:]
    box.update(status='updated',checkedAt=time.time());save(root,OUTBOX,box)
    state.setdefault('seen',{}).update({r['path']:r['sha256'] for r in rows});save(root,STATE,state)
    return {'status':'published','id':token}


if __name__=='__main__':
    import sys
    try:
        fd=os.open('.notes-watch.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            print(json.dumps(run(Path.cwd(),sys.argv[1]),ensure_ascii=False))
    except (ValueError,OSError,IndexError) as error:
        print(json.dumps({'error':str(error),'instruction':'Stop. Do not bypass restrictions.'}));sys.exit(1)
