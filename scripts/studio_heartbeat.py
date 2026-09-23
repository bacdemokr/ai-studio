"""Read native OpenClaw heartbeat artifacts; never simulate a model response."""
import json
import math
from pathlib import Path
import re
import secrets
import threading
import time

import notes_watch
import runtime_settings
import telegram_notifications


class NotesHeartbeat:
    def __init__(self, studio):
        self.studio = studio
        self.lock = threading.RLock()
        self.statuses = {}
        with studio.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS heartbeat_controls(owner TEXT PRIMARY KEY, paused INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS heartbeat_receipts(owner TEXT, event TEXT, job TEXT, PRIMARY KEY(owner,event));
            ''')

    def disable(self, agent_id):
        toggle = getattr(self.studio.adapter, 'set_notes_heartbeat', None)
        if toggle:toggle(agent_id, False)

    def status(self, owner, profile):
        if 'notes' not in profile.get('skills', []):return None
        with self.studio.db() as db:
            row = db.execute('SELECT paused FROM heartbeat_controls WHERE owner=?', (owner,)).fetchone()
        return {'paused': bool(row and row['paused']), 'everySeconds': 30,
                **self.statuses.get(owner, {'state':'preparing'})}

    def control(self, owner, data):
        from studio import Problem
        if type(data.get('paused')) is not bool:raise Problem('Choose Pause or Resume.')
        with self.lock, self.studio.db() as db:
            self.studio.require_available(db, owner)
            profile = self.studio.profile(owner)
            if 'notes' not in profile.get('skills', []):raise Problem('This agent does not have Notes Watcher.')
            # Stop new native runs before committing Pause. A running turn may finish.
            if data['paused']:self.disable(profile['id'])
            db.execute('INSERT OR REPLACE INTO heartbeat_controls VALUES (?,?)', (owner, int(data['paused'])))
        return self.status(owner, profile)

    def add_upload(self, owner, path):
        if Path(path).suffix.lower() not in ('.txt','.md','.csv'):return
        with self.lock:
            root = self.studio.workspace(owner).resolve()
            paths = notes_watch.read(root, notes_watch.MANIFEST, [])
            if path not in paths:paths.append(path)
            notes_watch.save(root, notes_watch.MANIFEST, paths[-80:])

    def import_events(self, owner, participant, profile):
        root = self.studio.workspace(owner).resolve()
        box = notes_watch.read(root, notes_watch.OUTBOX, {})
        if not isinstance(box, dict):raise ValueError('Invalid heartbeat output.')
        checked = box.get('checkedAt', 0)
        if isinstance(checked, (int,float)) and math.isfinite(checked):
            self.statuses[owner]['lastChecked'] = checked
        events = box.get('events', [])
        if not isinstance(events, list) or len(events)>50:raise ValueError('Invalid heartbeat output.')
        manifest = notes_watch.read(root, notes_watch.MANIFEST, [])
        for event in events:
            if not isinstance(event,dict):continue
            token, answer, files, created = (event.get(k) for k in ('id','answer','files','created'))
            if not isinstance(token,str) or not re.fullmatch('[0-9a-f]{64}',token):continue
            if not isinstance(answer,str) or not answer.strip() or len(answer)>1800:continue
            if not isinstance(files,list) or not 1<=len(files)<=3 or any(not isinstance(f,str) or f not in manifest for f in files):continue
            if type(created) not in (int,float) or not math.isfinite(created) or not 0<created<=time.time()+60:continue
            job = secrets.token_hex(12)
            result = {'answer':answer, 'heartbeat':True, 'sources':files, 'telegram':'pending'}
            with self.studio.db() as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT deleting,reset_at FROM agents WHERE id=?', (owner,)).fetchone()
                if not row or row['deleting'] or created < row['reset_at']:continue
                if db.execute('SELECT 1 FROM heartbeat_receipts WHERE owner=? AND event=?', (owner,token)).fetchone():continue
                db.execute('INSERT INTO heartbeat_receipts VALUES (?,?,?)', (owner,token,job))
                db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (job,owner,'heartbeat','done',json.dumps({'source':'OpenClaw heartbeat'}),json.dumps(result),'[]',created,time.time(),created))
            # The durable receipt is committed before sending. An uncertain network result
            # is not retried automatically; the app's summary remains available.
            try:delivery=telegram_notifications.send(participant, profile['name']+' · Notes Watcher\n\n'+answer, created)
            except RuntimeError:delivery='failed'
            result['telegram']=delivery
            with self.studio.db() as db:db.execute('UPDATE jobs SET result=? WHERE id=?', (json.dumps(result),job))

    def tick(self):
        from studio import job_participants
        studio = self.studio
        toggle = getattr(studio.adapter, 'set_notes_heartbeat', None)
        if not toggle:return
        with studio.db() as db:
            agents = [dict(r) for r in db.execute('SELECT id,participant,profile,deleting FROM agents WHERE profile IS NOT NULL')]
        ready = runtime_settings.model_available() if any('notes' in json.loads(r['profile']).get('skills',[]) for r in agents) else False
        for row in agents:
            owner=row['id']; profile=json.loads(row['profile'])
            if 'notes' not in profile.get('skills',[]):continue
            try:
                # Re-read under the same lock as Pause; a stale tick cannot re-enable it.
                with self.lock:
                    with studio.db() as db:
                        current = db.execute('SELECT profile,deleting FROM agents WHERE id=?',(owner,)).fetchone()
                        paused = db.execute('SELECT paused FROM heartbeat_controls WHERE owner=?',(owner,)).fetchone()
                        pending = db.execute("SELECT owner,payload FROM jobs WHERE status IN ('queued','running','waiting','stopping')").fetchall()
                        busy = owner in studio.executing_owners or any(j['owner']==owner or any(m.get('key')==owner for m in job_participants(json.loads(j['payload']))) for j in pending)
                    if not current or current['profile'] != row['profile']:continue
                    paused = bool(paused and paused['paused'])
                    enabled = bool(ready and not current['deleting'] and not paused and not busy and profile['id'] in studio.provisioned)
                    registered = toggle(profile['id'],enabled)
                    state = 'paused' if paused else 'waiting for model' if not ready else 'waiting for task' if busy else 'watching' if enabled and registered else 'preparing'
                    previous=self.statuses.get(owner,{})
                    since=previous.get('watchingSince',time.time()) if enabled else time.time()
                    self.statuses[owner] = {**previous, 'state':state, 'watchingSince':since}
                    if not current['deleting'] and not paused:
                        self.import_events(owner,row['participant'],profile)
                    last_check=max(since,self.statuses[owner].get('lastChecked',0))
                    if state=='watching' and time.time()-last_check>100:
                        self.statuses[owner]['state']='check delayed - verify the model connection'
            except Exception:
                self.statuses[owner]={'state':'check failed'}
                try:self.disable(profile['id'])
                except Exception:pass

    def work(self):
        try:
            while not self.studio.stop.is_set():
                try:self.tick()
                except Exception:pass  # Do not take down chat when an upload is malformed.
                self.studio.stop.wait(3)
        finally:
            with self.studio.db() as db:
                profiles=[json.loads(r['profile']) for r in db.execute('SELECT profile FROM agents WHERE profile IS NOT NULL')]
            for profile in profiles:
                if 'notes' in profile.get('skills',[]):
                    try:self.disable(profile['id'])
                    except Exception:pass
