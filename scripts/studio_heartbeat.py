"""Read native OpenClaw heartbeat artifacts; never simulate a model response."""
import json
import math
from pathlib import Path
import re
import secrets
import threading
import time
from datetime import datetime, timezone

import tech_radar
import runtime_settings
import telegram_notifications


class RadarHeartbeat:
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
        toggle = getattr(self.studio.adapter, 'set_radar_heartbeat', None)
        if toggle:toggle(agent_id, False)

    def status(self, owner, profile):
        if 'radar' not in profile.get('skills', []):return None
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
            if 'radar' not in profile.get('skills', []):raise Problem('This agent does not have Tech Radar.')
            # Stop new native runs before committing Pause. A running turn may finish.
            if data['paused']:self.disable(profile['id'])
            db.execute('INSERT OR REPLACE INTO heartbeat_controls VALUES (?,?)', (owner, int(data['paused'])))
            self.statuses[owner]={**self.statuses.get(owner,{}),'state':'paused' if data['paused'] else 'resuming'}
        return self.status(owner, profile)

    def import_events(self, owner, participant, profile, deliveries):
        root = self.studio.workspace(owner).resolve()
        box = tech_radar.read(root, tech_radar.OUTBOX, {})
        if not isinstance(box, dict):raise ValueError('Invalid heartbeat output.')
        checked = box.get('checkedAt', 0)
        if isinstance(checked, (int,float)) and math.isfinite(checked):
            self.statuses[owner]['lastChecked'] = checked
        if box.get('status')=='source-unavailable':self.statuses[owner]['state']='source unavailable - check OpenShell Policy or connection'
        failed_at=box.get('checkedAt',0)
        reader=getattr(self.studio.adapter,'policy_events',None)
        if profile.get('protection')=='openshell' and box.get('failures') and callable(reader) and isinstance(failed_at,(float,int)) and failed_at>self.statuses[owner].get('policyCheckedAt',0):
            self.statuses[owner]['policyCheckedAt']=failed_at
            try:self.studio.protection_activity.observe(owner,None,profile['id'],reader(profile['id']),failed_at-25)
            except Exception:pass
        events = box.get('events', [])
        if not isinstance(events, list) or len(events)>50:raise ValueError('Invalid heartbeat output.')

        for event in events:
            if not isinstance(event,dict):continue
            token, answer, url, created = (event.get(k) for k in ('id','answer','url','created'))
            if not isinstance(token,str) or not re.fullmatch('[0-9a-f]{64}',token):continue
            if not isinstance(answer,str) or not answer.strip() or len(answer)>1800:continue
            if not tech_radar.article_url(url):continue
            if type(created) not in (int,float) or not math.isfinite(created) or not 0<created<=time.time()+60:continue
            published=event.get('published')
            title=event.get('title')
            if type(published) not in (int,float) or not math.isfinite(published) or not 0<published<=time.time()+300:continue
            if not isinstance(title,str) or not 0<len(title)<=240:continue
            source={'url':url,'title':title,'published':datetime.fromtimestamp(published,timezone.utc).strftime('%Y-%m-%d'),'initial':event.get('initial') is True}
            job = secrets.token_hex(12)
            result = {'answer':answer, 'heartbeat':True, 'sources':[url], 'source':source, 'telegram':'pending'}
            with self.studio.db() as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT deleting,reset_at FROM agents WHERE id=?', (owner,)).fetchone()
                if not row or row['deleting'] or created < row['reset_at']:continue
                if db.execute('SELECT 1 FROM heartbeat_receipts WHERE owner=? AND event=?', (owner,token)).fetchone():continue
                db.execute('INSERT INTO heartbeat_receipts VALUES (?,?,?)', (owner,token,job))
                db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (job,owner,'heartbeat','done',json.dumps({'source':'OpenClaw heartbeat'}),json.dumps(result),'[]',created,time.time(),created))
            # Publish every agent's chat before external delivery. Never hold the
            # Pause/Resume lock during Telegram I/O, which can take many seconds.
            message = profile['name']+' · Tech Radar\n\n'+answer+'\n\n'+title+'\nPublished '+source['published']+' · Feed excerpt\n'+url
            deliveries.append((owner, participant, job, result, message, created))

    def deliver_events(self, deliveries):
        for owner, participant, job, result, message, created in deliveries:
            with self.studio.db() as db:
                # Deletion/reset can happen while an earlier send is waiting.
                active = db.execute('''SELECT 1 FROM jobs JOIN agents ON agents.id=jobs.owner
                    WHERE jobs.id=? AND jobs.owner=? AND agents.deleting=0
                    AND jobs.created>=agents.reset_at''', (job, owner)).fetchone()
            if not active:continue
            # The durable receipt precedes sending. Never retry an uncertain send.
            try:delivery=telegram_notifications.send(participant, message, created)
            except RuntimeError:delivery='failed'
            result['telegram']=delivery
            with self.studio.db() as db:db.execute('UPDATE jobs SET result=? WHERE id=?', (json.dumps(result),job))

    def tick(self):
        from studio import job_participants
        studio = self.studio
        toggle = getattr(studio.adapter, 'set_radar_heartbeat', None)
        if not toggle:return
        with studio.db() as db:
            agents = [dict(r) for r in db.execute('SELECT id,participant,profile,deleting FROM agents WHERE profile IS NOT NULL')]
        ready = runtime_settings.model_available() if any('radar' in json.loads(r['profile']).get('skills',[]) for r in agents) else False
        deliveries = []
        for row in agents:
            owner=row['id']; profile=json.loads(row['profile'])
            if 'radar' not in profile.get('skills',[]):continue
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
                        self.import_events(owner,row['participant'],profile,deliveries)
                    last_check=max(since,self.statuses[owner].get('lastChecked',0))
                    if state=='watching' and time.time()-last_check>100:
                        self.statuses[owner]['state']='check delayed - verify the model connection'
            except Exception:
                self.statuses[owner]={'state':'check failed'}
                try:self.disable(profile['id'])
                except Exception:pass
        self.deliver_events(deliveries)

    def work(self):
        try:
            while not self.studio.stop.is_set():
                try:self.tick()
                except Exception:pass  # Do not take down chat when a heartbeat artifact is malformed.
                self.studio.stop.wait(3)
        finally:
            with self.studio.db() as db:
                profiles=[json.loads(r['profile']) for r in db.execute('SELECT profile FROM agents WHERE profile IS NOT NULL')]
            for profile in profiles:
                if 'radar' in profile.get('skills',[]):
                    try:self.disable(profile['id'])
                    except Exception:pass
