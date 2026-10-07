"""Durable participant workspaces and bounded OpenClaw task queues.

This is a trusted workshop LAN application, not a public multi-tenant service.
Every browser gets an opaque, HttpOnly session; no gateway credentials reach it.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import threading
import time

import agent_runtime as runtime
import ops_common as c
from studio_policy import PolicyControls
from crew_roundtable import RoundtableControls, participants as job_participants
from crew_ownership import CrewOwnership
from collaboration_plan import CollaborationPlans, is_plan, plan_task
from event_scenario import EventScenario
from webpage_artifacts import DEMO_CODING_INSTRUCTIONS, PAGE_INSTRUCTIONS, html_files, collect_pages

CREW_CATALOG = json.loads((Path(__file__).resolve().parents[1] / 'src/crew-catalog.json').read_text())
ROLES = [(member['name'], member['role'], member['persona']) for member in CREW_CATALOG]
EVENT_ROLE_COUNT = sum(not member.get('planOnly', False) for member in CREW_CATALOG)
ACTIVE = ('queued', 'running', 'waiting', 'stopping')
ROLE_SKILLS = [list(member['skills']) for member in CREW_CATALOG]
MAX_AGENTS = 12
ROLE_AVATARS = [dict(body=b, color=c, accessory=a) for b, c, a in (
    ('classic', 'green', 'antenna'), ('round', 'cyan', 'headset'), ('rover', 'amber', 'cap'),
    ('round', 'coral', 'antenna'), ('classic', 'violet', 'glasses'), ('claw', 'ice', 'headset'), ('classic', 'cyan', 'glasses'), ('round', 'violet', 'cap'), ('rover', 'cyan', 'glasses'))]
AVATAR_OPTIONS = {'body': ('classic', 'round', 'rover', 'cat', 'operative', 'claw', 'crab'),
                  'color': ('green', 'cyan', 'amber', 'coral', 'violet', 'ice'),
                  'accessory': ('none', 'antenna', 'headset', 'glasses', 'cap')}
LEGACY_AVATAR_DEFAULTS = {'body': ('classic', 'round', 'rover', 'cat', 'claw', 'crab'),
                          'color': AVATAR_OPTIONS['color'],
                          'accessory': ('antenna', 'headset', 'glasses', 'cap')}


def personal_agent_activity(jobs, owner):
    """Display actual personal work separately from reservations for a BaC run."""
    activities = []
    for job in jobs:
        payload, kind = job['payload'], job['kind']
        # Background readiness keeps its reservation but is not personal work.
        if kind in ('prepare', 'prepare-agent') or (kind == 'crew-chat' and not payload.get('roundtable')):
            continue
        roster_member = any(m.get('key') == owner for m in payload.get('roster', []))
        guest = any(m.get('key') == owner for m in payload.get('roundtable', {}).get('members', []))
        if kind in ('crew','crew-chat') and not roster_member:
            reply = payload.get('roundtable', {}).get('replies', {}).get(owner, {})
            if not guest or reply.get('status') in ('done', 'error', 'cancelled'):
                continue
            category, label = 'roundtable', 'Sharing opinion' if reply.get('status') == 'running' else 'Waiting for task results' if payload.get('collaboration') else 'Waiting for event results'
        elif job['owner'] == owner or roster_member:
            category = 'mission'
            label = {'queued':'Request queued', 'running':'Working on your request',
                     'waiting':'Awaiting your decision', 'stopping':'Stopping request'}[job['status']]
            if kind == 'reminder' and job['status'] == 'queued' and job['due'] > time.time():
                label = 'Follow-up scheduled'
        else:
            continue
        activities.append({'kind':category, 'label':label, 'job':job['id'], 'status':job['status']})
    return min(activities, key=lambda a: {'mission':0, 'roundtable':1}[a['kind']]) if activities else None


def avatar_for(owner, avatar=None):
    """Stable defaults also give legacy agents a persistent visual identity."""
    seed = int(hashlib.sha256(owner.encode()).hexdigest()[:8], 16)
    defaults = {key: values[(seed // (7 ** i)) % len(values)]
                for i, (key, values) in enumerate(LEGACY_AVATAR_DEFAULTS.items())}
    if avatar is None:
        return defaults
    if not isinstance(avatar, dict) or set(avatar) != set(AVATAR_OPTIONS):
        raise Problem('Choose a body, color and accessory for your agent.')
    if avatar.get('body') == 'fox':
        avatar = {**avatar, 'body': 'claw'}
    if any(not isinstance(avatar[key], str) or avatar[key] not in options for key, options in AVATAR_OPTIONS.items()):
        raise Problem('Choose an available agent appearance.')
    return dict(avatar)


class Problem(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def text(value, limit=6000, name='Text'):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or '\x00' in value:
        raise Problem(name + ' is missing or too long.')
    return value.strip()


def safe_file(directory, relative, exists=False):
    if not isinstance(relative, str) or not re.fullmatch(r'[\w. ()/-]{1,160}', relative):
        raise Problem('Invalid file name.')
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or path.suffix.lower() not in ('.md', '.txt', '.csv', '.html', '.json', '.xlsx', '.eml', '.pdf', '.pptx', '.png', '.jpg', '.webp', '.py', '.js', '.css'):
        raise Problem('Use a supported document, spreadsheet or email draft in this workspace.')
    result = directory / path
    if directory.resolve() not in result.resolve().parents:
        raise Problem('File is outside this workspace.')
    for part in (result, *result.parents):
        if part == directory:
            break
        if part.is_symlink():
            raise Problem('Symbolic links are not accepted.')
    from document_upload import MAX_FILE
    if exists and (not result.is_file() or result.stat().st_size > MAX_FILE):
        raise Problem('File is unavailable or exceeds 10 MB.', 404)
    return result


class Studio(CollaborationPlans, EventScenario, CrewOwnership, PolicyControls, RoundtableControls):
    def __init__(self, directory=None, adapter=runtime, start_worker=True, recover=False):
        self.directory = Path(directory) if directory else c.initialize() / 'studio'
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.instance_lock = None
        if start_worker:
            self.instance_lock = (self.directory / '.server.lock').open('a')
            try:
                fcntl.flock(self.instance_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                self.instance_lock.close()
                raise RuntimeError('Another BaC app is already using this data directory. Stop it before starting a second server.')
        self.db_path = self.directory / 'studio.sqlite'
        self.adapter = adapter
        self.stop = threading.Event()
        self.signal = threading.Event()
        self.status_cache = (0, {})
        self.status_lock = threading.Lock()
        from runtime_health import RuntimeHealth
        self.runtime_health = RuntimeHealth()
        self.provisioned = set()
        self.boot_id = secrets.token_hex(8)
        self.delete_lock = threading.Lock()
        self.deletion_signal = threading.Event()
        self.deletion_worker = None
        self.execution_lock = threading.RLock()
        self.executing_jobs = {}
        self.agent_locks = {}
        self.executing_owners = set()
        self.executing_bac_owners = set()
        from protection_activity import ProtectionActivity
        self.protection_activity = ProtectionActivity()
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS participants (
                  id TEXT PRIMARY KEY, token TEXT UNIQUE, csrf TEXT, profile TEXT, created REAL);
                CREATE TABLE IF NOT EXISTS jobs (
                  id TEXT PRIMARY KEY, owner TEXT, kind TEXT, status TEXT, payload TEXT,
                  result TEXT, events TEXT, created REAL, updated REAL, due REAL);
                CREATE TABLE IF NOT EXISTS agent_deletions (owner TEXT PRIMARY KEY, attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0);
                CREATE INDEX IF NOT EXISTS job_queue ON jobs(status,due,created);
                CREATE INDEX IF NOT EXISTS job_owner_created ON jobs(owner,created DESC);
                CREATE INDEX IF NOT EXISTS job_crew_chat ON jobs(owner,json_extract(payload,'$.crewRole'),created DESC) WHERE kind='crew-chat';
                DROP TABLE IF EXISTS pairs;
                DROP TABLE IF EXISTS phones;
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT);
                DELETE FROM metadata WHERE key='telegram-offset';
                CREATE TABLE IF NOT EXISTS agent_policies (owner TEXT NOT NULL, role INTEGER NOT NULL DEFAULT -1,
                    approved TEXT NOT NULL DEFAULT '[]', events TEXT NOT NULL DEFAULT '[]',
                    updating INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(owner,role));
                CREATE TABLE IF NOT EXISTS event_surveys (token TEXT PRIMARY KEY, owner TEXT, job TEXT UNIQUE, definition TEXT, created REAL);
                CREATE TABLE IF NOT EXISTS survey_responses (token TEXT, visitor TEXT, topic TEXT, experience TEXT, rating INTEGER, created REAL, PRIMARY KEY(token,visitor));
            ''')
            if 'role' not in {r['name'] for r in db.execute('PRAGMA table_info(agent_policies)')}:
                db.executescript("""
                    BEGIN IMMEDIATE;
                    ALTER TABLE agent_policies RENAME TO agent_policies_legacy;
                    CREATE TABLE agent_policies (owner TEXT NOT NULL, role INTEGER NOT NULL DEFAULT -1,
                        approved TEXT NOT NULL DEFAULT '[]', events TEXT NOT NULL DEFAULT '[]',
                        updating INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(owner,role));
                    INSERT INTO agent_policies(owner,approved,events,updating)
                        SELECT owner,approved,events,updating FROM agent_policies_legacy;
                    DROP TABLE agent_policies_legacy;
                    COMMIT;
                """)
            if 'denials' not in {r['name'] for r in db.execute('PRAGMA table_info(agent_policies)')}:
                db.execute("ALTER TABLE agent_policies ADD COLUMN denials TEXT NOT NULL DEFAULT '[]'")
            if 'reset_at' not in {r['name'] for r in db.execute('PRAGMA table_info(participants)')}:
                db.execute('ALTER TABLE participants ADD COLUMN reset_at REAL NOT NULL DEFAULT 0')
            db.execute('''CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY, participant TEXT NOT NULL, profile TEXT,
                created REAL, reset_at REAL NOT NULL DEFAULT 0)''')
            # The original agent keeps its ID, native identity, jobs and files.
            if not db.execute("SELECT 1 FROM metadata WHERE key='agent-collection-migrated'").fetchone():
                db.execute('''INSERT OR IGNORE INTO agents (id,participant,profile,created,reset_at)
                    SELECT id,id,profile,created,reset_at FROM participants''')
                db.execute("INSERT INTO metadata VALUES ('agent-collection-migrated','1')")
            if 'deleting' not in {r['name'] for r in db.execute('PRAGMA table_info(agents)')}:
                db.execute('ALTER TABLE agents ADD COLUMN deleting INTEGER NOT NULL DEFAULT 0')
            if 'progress' not in {r['name'] for r in db.execute('PRAGMA table_info(agent_deletions)')}:
                db.execute("ALTER TABLE agent_deletions ADD COLUMN progress TEXT NOT NULL DEFAULT 'Queued for cleanup'")
            db.execute('CREATE INDEX IF NOT EXISTS agents_participant ON agents(participant)')
            db.execute("UPDATE jobs SET status='cancelled',updated=? WHERE kind IN ('crew','prepare') AND status IN ('queued','running','waiting','stopping')", (time.time(),))
            # Never silently replay a potentially completed side effect after a crash.
            if start_worker or recover:
                db.execute('UPDATE agent_policies SET updating=0')
                db.execute("UPDATE jobs SET status='error',result=?,updated=? WHERE status IN ('running','stopping')",
                           (json.dumps({'error': 'The app restarted during this task. Inspect saved files before retrying.'}), time.time()))
        self.initialize_crew_ownership()
        from studio_heartbeat import RadarHeartbeat
        self.heartbeat = RadarHeartbeat(self)
        self.retire_host_file_grants()
        os.chmod(self.db_path, 0o600)
        with self.db() as db:
            owners = [row['id'] for row in db.execute("SELECT id FROM agents WHERE deleting=0 AND kind='personal'")]
        import user_location
        from personal_voice import PRESET_UPDATES
        for owner in owners:
            profile = self.profile(owner)
            if profile:
                if 'notes' in profile.get('skills', []):
                    profile['skills'] = list(dict.fromkeys('radar' if key=='notes' else key for key in profile['skills']))
                    if profile.get('purpose','').startswith('Watch my uploaded meeting notes every 30 seconds.'):
                        profile['purpose'] = 'Every 30 seconds, summarize one technical article or announcement not yet shared. Share useful discoveries in my chosen tone; skip politics, stocks and company earnings.'
                    with self.db() as db:
                        db.execute('UPDATE agents SET profile=? WHERE id=?', (json.dumps(profile), owner))
                        db.execute('UPDATE participants SET profile=? WHERE id=?', (json.dumps(profile), owner))
                if profile.get('purpose') in PRESET_UPDATES:
                    profile['purpose'] = PRESET_UPDATES[profile['purpose']]
                    with self.db() as db:
                        db.execute('UPDATE agents SET profile=? WHERE id=?', (json.dumps(profile), owner))
                        db.execute('UPDATE participants SET profile=? WHERE id=?', (json.dumps(profile), owner))
                runtime.write_workspace(self.workspace(owner), profile)
            user_location.sync(self.workspace(owner))
        with self.db() as db:
            teams = [r['owner'] for r in db.execute('SELECT owner FROM crew_contexts')]
        for team in teams:
            self.initialize_workspace(team)
            self.initialize_crew_workspaces(team)
        if start_worker:
            with self.db() as db:
                for owner in owners:
                    profile=self.profile(owner)
                    if profile and 'radar' in profile.get('skills',[]):
                        try:self.heartbeat.disable(profile['id'])
                        except RuntimeError:
                            # One unavailable identity must not prevent startup.
                            # Its queued preparation and tick retry independently.
                            self.heartbeat.statuses[owner]={'state':'preparing'}
                        # A browser lease is required before restoring autonomous work.
                        # RadarHeartbeat.tick queues preparation only for connected owners.
            self.worker = threading.Thread(target=self.work, daemon=True, name='bac-agent-queue')
            self.deletion_worker = threading.Thread(target=self.clean_deletions, daemon=True, name='bac-cleanup-queue')
            self.chat_worker = threading.Thread(target=self.work, args=('chat',), daemon=True, name='bac-chat-queue')
            self.worker.start()
            self.chat_worker.start()
            self.deletion_worker.start()
            self.heartbeat_worker = threading.Thread(target=self.heartbeat.work, daemon=True, name='radar-heartbeat-relay')
            self.heartbeat_worker.start()

    def retire_host_file_grants(self):
        """Retire the removed file bridge without touching original host files.

        OpenClaw mirror mode replaces remote workspace contents before the next
        protected run, so removed transfer copies are not reintroduced remotely.
        """
        with self.db() as db:
            if db.execute("SELECT 1 FROM metadata WHERE key='host-file-grants-retired'").fetchone():
                return
            for row in db.execute('SELECT owner,role,approved FROM agent_policies').fetchall():
                approved = json.loads(row['approved'])
                websites = [key for key in approved if not key.startswith('file:')]
                if websites != approved:
                    db.execute('UPDATE agent_policies SET approved=? WHERE owner=? AND role=?',
                               (json.dumps(websites), row['owner'], row['role']))
            workspaces = self.directory / 'workspaces'
            if workspaces.is_dir() and not workspaces.is_symlink():
                for workspace in workspaces.iterdir():
                    inbox = workspace / 'inbox'
                    if workspace.is_symlink() or inbox.is_symlink() or not inbox.is_dir():
                        continue
                    for path in inbox.iterdir():
                        if re.fullmatch(r'approved-[0-9a-f]{64}\.txt(?:\.invalid-directory-[^/]+)?', path.name):
                            if path.is_dir() and not path.is_symlink():
                                shutil.rmtree(path)
                            else:
                                path.unlink()
            db.execute("INSERT INTO metadata VALUES ('host-file-grants-retired','1')")

    @contextlib.contextmanager
    def db(self):
        db = sqlite3.connect(self.db_path, timeout=15)
        db.execute('PRAGMA secure_delete=ON')
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def session(self, token=None):
        with self.db() as db:
            row = db.execute('SELECT * FROM participants WHERE token=?', (token,)).fetchone() if token else None
            if row:
                return dict(row), False
            if db.execute('SELECT count(*) FROM participants').fetchone()[0] >= 500:
                raise Problem('This workshop is full. Ask the host to clear completed participants.', 503)
            row = {'id': secrets.token_hex(12), 'token': secrets.token_urlsafe(32),
                   'csrf': secrets.token_urlsafe(24), 'profile': None, 'created': time.time()}
            db.execute('INSERT INTO participants (id,token,csrf,profile,created) VALUES (:id,:token,:csrf,:profile,:created)', row)
            db.execute('INSERT INTO agents (id,participant,created) VALUES (?,?,?)', (row['id'], row['id'], row['created']))
            return row, True

    def resolve_agent(self, participant, agent=None):
        """Resolve an explicitly selected agent within the authenticated account."""
        with self.db() as db:
            row = (db.execute("SELECT id FROM agents WHERE id=? AND participant=? AND kind='personal'", (agent, participant)).fetchone()
                   if agent else db.execute("SELECT id FROM agents WHERE participant=? AND kind='personal' ORDER BY created,id LIMIT 1", (participant,)).fetchone())
        if not row:
            raise Problem('Agent not found in your collection.', 404)
        return row['id']

    @staticmethod
    def require_available(db, owner):
        row = db.execute('SELECT profile,deleting FROM agents WHERE id=?', (owner,)).fetchone()
        if not row or not row['profile']:
            raise Problem('Agent not found.', 404)
        if row['deleting']:
            raise Problem('Agent deletion is pending. Retry Delete agent to finish cleanup.', 409)
        if db.execute('SELECT 1 FROM agent_policies WHERE owner=? AND updating=1', (owner,)).fetchone():
            raise Problem('This agent’s policy is being updated. Please wait.', 409)
        return row

    @staticmethod
    def require_manual_chat(profile):
        if 'radar' in (profile or {}).get('skills', []):
            raise Problem('Tech Radar runs automatically. Manual chat is disabled.', 409)

    def require_idle(self, db, owner):
        if owner in self.executing_owners or db.execute("SELECT 1 FROM jobs WHERE owner=? AND status IN ('queued','running','waiting','stopping') AND NOT (kind='prepare-agent' AND status='queued')", (owner,)).fetchone():
            raise Problem('Finish or cancel this agent’s pending missions before changing it.', 409)
        crews = db.execute("SELECT payload FROM jobs WHERE kind IN ('crew','crew-chat','prepare') AND status IN ('queued','running','waiting','stopping') AND owner IN (SELECT id FROM agents WHERE participant=(SELECT participant FROM agents WHERE id=?))", (owner,)).fetchall()
        if any(any(m.get('key') == owner for m in job_participants(json.loads(j['payload']))) for j in crews):
            raise Problem('This agent is assigned to a pending crew mission. Finish or cancel it first.', 409)

    @staticmethod
    def agent_profile(owner, data):
        name = text(data.get('name'), 32, 'Agent name')
        persona, skills = data.get('persona', 'guide'), data.get('skills', [])
        purpose = data.get('purpose', '')
        if not isinstance(purpose, str) or len(purpose) > 240 or any(ord(c) < 32 and c not in '\n\t' for c in purpose):
            raise Problem('Describe your agent in one sentence, up to 240 characters.')
        purpose = purpose.strip()
        tone_prompt = data.get('tonePrompt', '')
        if not isinstance(tone_prompt, str) or len(tone_prompt) > 800 or any(ord(c) < 32 and c not in '\n\t' for c in tone_prompt):
            raise Problem('Describe the tone in up to 800 characters.')
        tone, verbosity = data.get('tone', 'kind'), data.get('verbosity', 'balanced')
        if not isinstance(tone, str) or tone not in runtime.TONES:
            raise Problem('Choose an available speaking tone.')
        if not isinstance(verbosity, str) or verbosity not in runtime.VERBOSITIES:
            raise Problem('Choose an available answer length.')
        protection = data.get('protection', 'standard')
        if protection not in ('standard', 'openshell'):
            raise Problem('Choose OpenShell on or off.')
        if any(x in name for x in '\r\n<>') or not isinstance(persona, str) or persona not in runtime.PERSONAS:
            raise Problem('Choose a valid name and persona.')
        if not isinstance(skills, list) or not skills or len(skills) > len(runtime.SKILLS) or any(not isinstance(x, str) or x not in runtime.SKILLS for x in skills):
            raise Problem('Choose a persona and at least one available skill.')
        return {'name': name, 'persona': persona, 'purpose': purpose, 'tonePrompt': tone_prompt.strip(), 'tone': tone, 'verbosity': verbosity, 'skills': sorted(set(skills)),
                'avatar': avatar_for(owner, data.get('avatar')), 'id': 'bac-' + owner, 'protection': protection}

    @staticmethod
    def unique_agent_name(db, participant, requested, exclude=None):
        used = {json.loads(row['profile'])['name'].strip().casefold()
                for row in db.execute('SELECT id,profile FROM agents WHERE participant=? AND profile IS NOT NULL', (participant,))
                if row['id'] != exclude}
        if requested.casefold() not in used:
            return requested
        match = re.fullmatch(r'(.*)_([2-9]|[1-9][0-9]+)', requested)
        base = match.group(1) if match else requested
        number = int(match.group(2)) + 1 if match else 2
        while True:
            suffix = '_' + str(number)
            candidate = base[:32-len(suffix)] + suffix
            if candidate.casefold() not in used:
                return candidate
            number += 1

    def initialize_crew_workspaces(self, owner):
        for role, member in enumerate(CREW_CATALOG):
            profile = {**member, 'skills':list(ROLE_SKILLS[role]), 'protection':member.get('protection','standard')}
            runtime.write_workspace(self.workspace(owner, role), profile, member['role'], overwrite=False)

    def initialize_workspace(self, owner):
        workspace = self.workspace(owner)
        workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
        (workspace / 'inbox').mkdir(exist_ok=True)
        (workspace / 'artifacts').mkdir(exist_ok=True)
        import user_location
        user_location.sync(workspace)
        memory = workspace / 'MEMORY.md'
        if not memory.exists():
            memory.write_text('# Saved preferences\n', encoding='utf-8')

    def add_agent(self, participant, data):
        owner = secrets.token_hex(12)
        profile = self.agent_profile(owner, data)
        with self.new_agent_workspace(owner), self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT id FROM agents WHERE participant=? AND profile IS NOT NULL', (participant,)).fetchone():
                raise Problem('Create your first agent before adding another.')
            if db.execute("SELECT count(*) FROM agents WHERE participant=? AND kind='personal'", (participant,)).fetchone()[0] >= MAX_AGENTS:
                raise Problem('This studio supports up to %d personal agents per attendee.' % MAX_AGENTS, 409)
            profile['name'] = self.unique_agent_name(db, participant, profile['name'])
            self.initialize_workspace(owner)
            runtime.write_workspace(self.workspace(owner), profile)
            db.execute('INSERT INTO agents (id,participant,profile,created) VALUES (?,?,?,?)',
                       (owner, participant, json.dumps(profile), time.time()))
            self.queue_agent_preparation(db, owner, profile)
        self.signal.set()
        return {'agentId': owner, 'profile': profile}

    @contextlib.contextmanager
    def new_agent_workspace(self, owner):
        """Roll back only the fresh directory allocated by this creation attempt."""
        path = self.workspace(owner)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.parent.is_symlink():raise RuntimeError('Agent workspace storage is redirected.')
        path.mkdir(mode=0o700)  # Never adopt or erase a pre-existing identity.
        identity = path.stat()
        try:
            yield
        except Exception:
            try:current = path.lstat()
            except FileNotFoundError:current = None
            if current and not path.is_symlink() and (current.st_dev,current.st_ino) == (identity.st_dev,identity.st_ino):
                shutil.rmtree(path)
            raise

    def workspace(self, owner, role=None):
        resource = self.crew_resources.get((owner,role)) if role is not None else None
        name = resource['workspace_name'] if resource else owner + ('-' + str(role) if role is not None else '')
        return self.directory / 'workspaces' / name

    def profile(self, owner):
        with self.db() as db:
            row = db.execute('SELECT profile FROM agents WHERE id=?', (owner,)).fetchone()
        if not row or not row['profile']:
            return None
        profile = json.loads(row['profile'])
        profile['avatar'] = avatar_for(owner, profile.get('avatar'))
        profile.setdefault('tone', 'kind')
        profile.setdefault('verbosity', 'balanced')
        return profile

    def onboard(self, owner, data):
        if self.profile(owner):
            raise Problem('Your agent already exists. Its identity and files are preserved.', 409)
        profile = self.agent_profile(owner, data)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            selected = db.execute("SELECT participant,profile,deleting FROM agents WHERE id=? AND kind='personal'", (owner,)).fetchone()
            if not selected:raise Problem('Agent not found. Refresh the studio before hiring.', 404)
            if selected['deleting']:raise Problem('Agent deletion is pending.', 409)
            if selected['profile']:raise Problem('Your agent was already created in another tab.', 409)
            participant = selected['participant']
            profile['name'] = self.unique_agent_name(db, participant, profile['name'], owner)
            self.initialize_workspace(owner)
            runtime.write_workspace(self.workspace(owner), profile)
            changed = db.execute("UPDATE agents SET profile=? WHERE id=? AND profile IS NULL AND kind='personal'", (json.dumps(profile), owner)).rowcount
            if changed:
                db.execute('UPDATE participants SET profile=? WHERE id=?', (json.dumps(profile), owner))
                self.queue_agent_preparation(db, owner, profile)
        if not changed:
            raise Problem('Your agent was already created in another tab.', 409)
        self.signal.set()
        return profile

    @staticmethod
    def queue_agent_preparation(db, owner, profile):
        # Durable, model-free warmup shares the worker and deletion fence with chat.
        if profile.get('protection') != 'openshell' and 'radar' not in profile.get('skills', []):
            return
        now = time.time()
        db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (secrets.token_hex(12), owner, 'prepare-agent', 'queued', '{}', '{}', '[]', now, now, now))

    def configure(self, owner, data):
        profile = self.profile(owner)
        if not profile:
            raise Problem('Create your agent first.')
        if data.get('protection', profile.get('protection', 'standard')) != profile.get('protection', 'standard'):
            raise Problem('OpenShell protection is fixed when an agent is created.', 409)
        profile = self.agent_profile(owner, {**data, 'avatar': data.get('avatar', profile['avatar']),
                    'purpose': data.get('purpose', profile.get('purpose', '')),
                    'tonePrompt': data.get('tonePrompt', profile.get('tonePrompt', '')),
                    'tone': data.get('tone', profile['tone']), 'verbosity': data.get('verbosity', profile['verbosity']),
                    'protection': profile.get('protection', 'standard')})
        # Perform native I/O before publishing the edit; then recheck whether
        # deletion or a new task won meanwhile. Never enqueue a retired identity.
        with self.heartbeat.lock:
            with self.db() as db:
                self.require_available(db, owner)
                self.require_idle(db, owner)
            self.heartbeat.disable(profile['id'])
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                self.require_available(db, owner)
                self.require_idle(db, owner)
                participant = db.execute('SELECT participant FROM agents WHERE id=?', (owner,)).fetchone()['participant']
                profile['name'] = self.unique_agent_name(db, participant, profile['name'], owner)
                runtime.write_workspace(self.workspace(owner), profile)
                db.execute('UPDATE agents SET profile=? WHERE id=?', (json.dumps(profile), owner))
                db.execute('UPDATE participants SET profile=? WHERE id=?', (json.dumps(profile), owner))
                self.provisioned.discard(profile['id'])
                db.execute("DELETE FROM jobs WHERE owner=? AND kind='prepare-agent' AND status='queued'", (owner,))
                self.queue_agent_preparation(db, owner, profile)
        self.signal.set()
        return profile

    def delete_agent(self, owner, data, *, enqueue_only=False):
        """Fence the identity first; retryable native cleanup precedes collection removal."""
        acquired = not enqueue_only and self.delete_lock.acquire(blocking=False)
        try:
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT * FROM agents WHERE id=?', (owner,)).fetchone()
                if not row or not row['profile']:
                    raise Problem('Agent not found.', 404)
                if db.execute('SELECT 1 FROM agent_policies WHERE owner=? AND updating=1', (owner,)).fetchone():
                    raise Problem('Wait for this agent’s policy update before deleting it.', 409)
                profile = json.loads(row['profile'])
                if data.get('name') != profile['name']:
                    raise Problem('This agent changed. Reopen Delete agent to confirm its name.', 409)
                pending = db.execute("SELECT * FROM jobs WHERE status IN ('queued','running','waiting','stopping') AND owner IN (SELECT id FROM agents WHERE participant=?)", (row['participant'],)).fetchall()
                affected = [j for j in pending if j['owner'] == owner or any(m.get('key') == owner for m in job_participants(json.loads(j['payload'])))]
                waiting = owner in self.executing_owners or any(key == owner for key, _ in tuple(self.heartbeat.delivering))
                for job in affected:
                    running = job['status'] in ('running', 'stopping')
                    waiting = waiting or running
                    status = 'stopping' if running else 'cancelled'
                    events = json.loads(job['events'])
                    if job['status'] != 'stopping':
                        events.append({'time': time.time(), 'title': 'Agent deletion requested',
                                       'detail': profile['name'] + ' is being deleted. This task is stopping; no further steps will start.', 'role': 0})
                    db.execute('UPDATE jobs SET status=?,events=?,updated=? WHERE id=?',
                               (status, json.dumps(events[-40:]), time.time(), job['id']))
                # 2 waits for the worker to release all calls; 1 is native cleanup (retryable on failure).
                db.execute('UPDATE agents SET deleting=2 WHERE id=?', (owner,))
                db.execute('INSERT OR IGNORE INTO agent_deletions(owner) VALUES (?)',(owner,))
                if row['deleting']!=2:db.execute("UPDATE agent_deletions SET attempts=0,next_attempt=0,progress='Queued for cleanup' WHERE owner=?",(owner,))
            if not acquired:
                # Persist intent even when another agent owns the cleanup slot.
                # The worker drains this queue; callers only poll, never replay.
                if row['deleting'] != 2:self.signal.set()
                self.deletion_signal.set()
                return {'deleting': owner, 'agentId': owner}
            native_id = profile['id']
            try:
                if 'radar' in profile.get('skills',[]):self.heartbeat.disable(profile['id'])
                if waiting:
                    self.deletion_progress(owner, 'Waiting for current work to stop')
                    self.signal.set()
                    return {'deleting': owner, 'agentId': owner}
                # A hired identity owns one personal runtime. Shared team
                # resources have their own owner and never enter this plan.
                plan = [(profile['id'], self.workspace(owner))]
                inspect_unused = getattr(self.adapter, 'unregistered_deletion_targets', None)
                unused = inspect_unused(plan) if callable(inspect_unused) else set()
                self.deletion_progress(owner, 'Cleaning personal workspace')
                self.provisioned.discard(native_id)
                if native_id not in unused:
                    started = time.monotonic()
                    try:
                        self.adapter.remove(native_id, self.workspace(owner))
                    finally:
                        import logging
                        logging.info('Agent cleanup target %s took %.3fs', native_id, time.monotonic()-started)
                path = self.workspace(owner)
                if path.is_symlink():
                    path.unlink()
                elif path.exists():
                    shutil.rmtree(path)
                finalize = getattr(self.adapter, 'finalize_removal', None)
                if callable(finalize):
                    self.deletion_progress(owner, 'Removing remaining agent data')
                    finalize(native_id, path)
            except runtime.NativeCleanupPending as error:
                self.deletion_progress(owner, 'Waiting for runtime cleanup confirmation')
                # Only an acknowledged partial cleanup/confirmed draining run is
                # resumable. Never blindly replay unknown transport failures.
                with self.db() as db:
                    attempt=db.execute('SELECT attempts FROM agent_deletions WHERE owner=?',(owner,)).fetchone()['attempts']+1
                    db.execute('UPDATE agent_deletions SET attempts=?,next_attempt=? WHERE owner=?',
                               (attempt,time.time()+min(30,2**attempt),owner))
                    if attempt>=5:db.execute('UPDATE agents SET deleting=1 WHERE id=?',(owner,))
                if attempt>=5:raise Problem('Cleanup could not finish after recovery attempts. The agent remains paused; retry deletion after checking the runtime.',503) from None
                self.signal.set()
                return {'deleting':owner,'agentId':owner}
            except runtime.CleanupPrerequisiteError as error:
                self.deletion_progress(owner, 'Restart the agent runtime, then retry deletion.')
                with self.db() as db:
                    db.execute('UPDATE agents SET deleting=1 WHERE id=?', (owner,))
                raise Problem(str(error), 503) from None
            except Exception as error:
                import logging
                logging.exception('Native cleanup failed for %s', native_id)
                self.deletion_progress(owner, 'Cleanup paused. Retry deletion.')
                with self.db() as db:
                    db.execute('UPDATE agents SET deleting=1 WHERE id=?', (owner,))
                # Keep the fence through errors/restarts; a partially removed identity must not run again.
                raise Problem('Deletion paused while cleaning ' + profile['name'] + ' (personal workspace). Native cleanup did not finish (' + type(error).__name__ + '). Retry deletion; completed cleanup is preserved.', 503) from None
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('DELETE FROM survey_responses WHERE token IN (SELECT token FROM event_surveys WHERE owner=?)', (owner,))
                db.execute('DELETE FROM event_surveys WHERE owner=?', (owner,))
                for table in ('jobs', 'agent_policies', 'heartbeat_controls', 'heartbeat_receipts', 'agent_deletions'):
                    db.execute('DELETE FROM ' + table + ' WHERE owner=?', (owner,))
                db.execute('DELETE FROM agents WHERE id=?', (owner,))
                db.execute('UPDATE participants SET profile=NULL WHERE id=?', (owner,))
                next_agent = db.execute("SELECT id FROM agents WHERE participant=? AND kind='personal' ORDER BY created,id LIMIT 1", (row['participant'],)).fetchone()
                next_id = next_agent['id'] if next_agent else secrets.token_hex(12)
                if not next_agent:
                    # A fresh placeholder keeps the account usable without reusing deleted native identity.
                    db.execute('INSERT INTO agents (id,participant,created) VALUES (?,?,?)', (next_id, row['participant'], time.time()))
            with self.heartbeat.lock:
                self.heartbeat.statuses.pop(owner, None)
            self.protection_activity.forget(owner)
            return {'deleted': owner, 'agentId': next_id}
        finally:
            if acquired:self.delete_lock.release()

    def finish_pending_deletions(self):
        """Run between jobs, after every in-flight call and post-result write has returned."""
        if self.delete_lock.locked():
            return
        with self.db() as db:
            requests = db.execute('SELECT id,profile FROM agents LEFT JOIN agent_deletions ON owner=id WHERE deleting=2 AND coalesce(next_attempt,0)<=?',(time.time(),)).fetchall()
        for request in requests:
            try:
                self.delete_agent(request['id'], {'name': json.loads(request['profile'])['name']})
            except Problem:
                # Native failures keep deleting=1 for an explicit retry, not an endless cleanup loop.
                continue

    def deletion_progress(self, owner, message):
        with self.db() as db:
            db.execute('UPDATE agent_deletions SET progress=? WHERE owner=?', (message, owner))

    def clean_deletions(self):
        """Keep slow native cleanup off the HTTP handler and mission worker."""
        while not self.stop.is_set():
            self.deletion_signal.clear()
            self.finish_pending_deletions()
            self.deletion_signal.wait(1)

    def runtime_status(self, retry=False):
        # Manual retries share the probe lock and are rate limited across tabs.
        ttl = 2 if retry else 8
        if not self.status_cache[1] or time.monotonic() - self.status_cache[0] > ttl:
            with self.status_lock:
                if not self.status_cache[1] or time.monotonic() - self.status_cache[0] > ttl:
                    value = self.runtime_health.observe(self.adapter.status(), time.monotonic())
                    self.status_cache = (time.monotonic(), value)
        return {**self.status_cache[1], 'instance': self.boot_id}

    def files(self, owner, role=None, *, recursive=False):
        result = []
        base = self.workspace(owner, role)
        for category in ('inbox', 'artifacts'):
            folder = base / category
            if folder.is_symlink():
                continue
            for p in sorted(folder.rglob('*') if recursive else folder.glob('*')):
                try:
                    p = safe_file(base, str(p.relative_to(base)), True)
                    stat = p.stat()
                    result.append({'path': str(p.relative_to(base)), 'size': stat.st_size,
                                   'updated': stat.st_mtime, 'kind': category})
                except (Problem, OSError):
                    # Reset and native tool writes can remove a file mid-listing.
                    continue
        return result[:100]

    def state(self, owner, scenario='plan'):
        from scenarios import validate
        from plan_inputs import internal_team_input
        validate(scenario)
        team = self.existing_crew_owner(owner, scenario)
        with self.db() as db:
            jobs = [self.public_job(r) for r in db.execute("SELECT * FROM jobs WHERE owner=? AND kind NOT IN ('crew','crew-chat','prepare','prepare-agent') AND created >= (SELECT reset_at FROM agents WHERE id=?) ORDER BY created DESC LIMIT 30", (owner, owner))]
            crew_chats = [self.public_job(r) for role in range(len(ROLES)) for r in db.execute("SELECT * FROM jobs WHERE (owner=? OR owner=?) AND kind='crew-chat' AND json_extract(payload,'$.crewRole')=? ORDER BY created DESC LIMIT 30", (team, owner if scenario=='plan' else team, role))]
            if scenario == 'event-brief' and team:
                reset = self.crew_chat_reset_state(db, team)
                jobs += [self.public_job(r) for r in db.execute("SELECT * FROM jobs WHERE owner=? AND kind='crew' AND created>=? ORDER BY created DESC LIMIT 30",(team,reset['at']))]
            collection = db.execute('SELECT id,profile,deleting FROM agents WHERE participant=(SELECT participant FROM agents WHERE id=?) AND profile IS NOT NULL ORDER BY created,id', (owner,)).fetchall()
            active = [dict(j, payload=json.loads(j['payload'])) for j in db.execute("SELECT id,owner,status,payload,kind,due FROM jobs WHERE status IN ('queued','running','waiting','stopping') AND owner IN (SELECT id FROM agents WHERE participant=(SELECT participant FROM agents WHERE id=?)) ORDER BY created", (owner,))]
            agents = [{'key': r['id'], **json.loads(r['profile']), 'deleting': bool(r['deleting']), 'deletionWaiting': r['deleting'] == 2,
                       'pending': sum((j['owner'] == r['id'] and j['kind'] not in ('crew','prepare','prepare-agent')) or any(m.get('key') == r['id'] for m in job_participants(j['payload'])) for j in active if j['kind'] != 'crew-chat' or j['payload'].get('roundtable')),
                       'activity': personal_agent_activity(active, r['id'])} for r in collection]
            for agent in agents:
                deletion = db.execute('SELECT progress FROM agent_deletions WHERE owner=?', (agent['key'],)).fetchone()
                agent['deletionProgress'] = deletion['progress'] if deletion else None
                latest = db.execute("SELECT id,status,CASE WHEN status='done' THEN substr(json_extract(result,'$.answer'),1,1200) ELSE NULL END AS answerPreview FROM jobs WHERE owner=? AND kind NOT IN ('crew','crew-chat','prepare','prepare-agent') AND created >= (SELECT reset_at FROM agents WHERE id=?) ORDER BY created DESC,rowid DESC LIMIT 1", (agent['key'], agent['key'])).fetchone()
                warmup = db.execute("SELECT status FROM jobs WHERE owner=? AND kind='prepare-agent' ORDER BY created DESC LIMIT 1", (agent['key'],)).fetchone()
                agent['techRadar'] = self.heartbeat.status(agent['key'], agent)
                agent['workspacePreparation'] = warmup['status'] if warmup else None
                agent['latestMission'] = dict(latest) if latest else None
                agent['avatar'] = avatar_for(agent['key'], agent.get('avatar'))
                agent.setdefault('tone', 'kind')
                agent.setdefault('verbosity', 'balanced')
            bac_resetting = bool(db.execute("SELECT 1 FROM metadata m JOIN agents a ON (m.key='bac-reset-pending:'||a.participant OR m.key='bac-reset-pending:'||a.id) WHERE a.id=?",(team or owner,)).fetchone())
            crew_chat_reset = self.crew_chat_reset_state(db, team or owner)
            roundtable_turns = self.roundtable_history(db, owner)
            names = {a['key']: a['name'] for a in agents}
            assignments = [{'job': j['id'], 'lead': j['owner'], 'name': names.get(j['owner'], 'BaC Captain'), 'role': m['role'], 'status': j['status']}
                           for j in active if j['kind'] in ('crew','crew-chat') and j['owner'] != owner for m in job_participants(j['payload']) if m.get('key') == owner
                           and (m in j['payload'].get('roster', []) or j['payload'].get('roundtable', {}).get('replies', {}).get(owner, {}).get('status') not in ('done','error','cancelled'))]
        from live_plan_activity import snapshot as live_snapshot
        for job in crew_chats:
            plan = job['payload'].get('collaboration', {})
            observation = plan.pop('observation', None)
            if job['status'] == 'running' and observation and not plan.get('responseReady'):
                plan['liveActivity'] = live_snapshot(self.adapter, observation)
        memory = self.workspace(owner) / 'MEMORY.md'
        memory_text = ''
        try:
            memory_text = safe_file(self.workspace(owner), 'MEMORY.md', True).read_text(encoding='utf-8')
        except (Problem, UnicodeError):
            pass
        from team_models import selections
        from scenario_models import connection
        return {'scenario':scenario, 'scenarios':self.scenario_status(owner), 'preparation':self.demo_preparation(team) if team and scenario=='event-brief' else None,
                'teamConnection': connection(self, team),
                'crewDocuments': [f for f in self.files(team,0) if f['kind']=='inbox' and not internal_team_input(f['path'])] if team else [], 'teamSelections': selections(self,team), 'profile': self.profile(owner), 'jobs': jobs, 'crewChats': crew_chats, 'crewChatReset': crew_chat_reset, 'files': self.files(owner),
                'techRadar': self.heartbeat.status(owner, self.profile(owner) or {}),
                'memory': memory_text, 'agentId': owner, 'crewOwner': team, 'roundtableTurns': roundtable_turns,
                'agents': agents, 'agentLimit': MAX_AGENTS, 'assignments': assignments, 'bacResetting': bac_resetting,
                'deleting': any(a['key'] == owner and a['deleting'] for a in agents),
                'protectionEvents': self.protection_activity.snapshot({a['key'] for a in agents}, team)}

    def crew_roster(self, db, owner, members, preset=False, lead=None):
        """Freeze names/skills and assignments; no extra permissions for a crew role."""
        if not isinstance(members, dict) or any(k not in {str(i) for i in range(1, EVENT_ROLE_COUNT)} for k in members):
            raise Problem('Assign personal agents to the specialist roles.')
        account = db.execute('SELECT participant FROM agents WHERE id=?', (owner,)).fetchone()['participant']
        roster, used = [], {owner}
        for i, (name, role, persona) in enumerate(ROLES):
            key = None if preset else (lead or owner) if i == 0 else members.get(str(i))
            if key:
                if not isinstance(key, str) or (i and key in used):
                    raise Problem('Choose a different agent for each crew role.')
                row = db.execute('SELECT profile FROM agents WHERE id=? AND participant=?', (key, account)).fetchone()
                if not row or not row['profile']:
                    raise Problem('Assigned agent not found in your collection.', 404)
                self.require_available(db, key)
                profile = json.loads(row['profile'])
                used.add(key)
            else:
                profile = {'name': name, 'persona': persona, 'skills': list(ROLE_SKILLS[i]), 'id': self.crew_native_id(owner, i), 'avatar': ROLE_AVATARS[i], 'protection': CREW_CATALOG[i].get('protection','standard')}
            profile['avatar'] = avatar_for(key or profile['id'], profile.get('avatar'))
            profile.setdefault('tone', 'kind')
            profile.setdefault('verbosity', 'balanced')
            roster.append({**profile, 'key': key or None, 'role': role})
        return roster

    @staticmethod
    def public_job(row):
        return {key: json.loads(row[key]) if key in ('payload', 'result', 'events') else row[key]
                for key in ('id', 'kind', 'status', 'payload', 'result', 'events', 'created', 'due')}

    def upload(self, owner, data):
        role = data.get('crewRole')
        if 'crewRole' in data and (type(role) is not int or role != 0):
            raise Problem('Documents can be attached to Casey only.')
        if role is not None:
            owner = self.crew_owner(owner)
        if role is None and not self.profile(owner):
            raise Problem('Create your agent first.')
        name = text(data.get('name'), 100, 'File name')
        if role is not None:
            from plan_inputs import EVENT_INTERNAL_INPUTS
            if name in EVENT_INTERNAL_INPUTS:
                raise Problem('This filename is reserved for internal team work. Rename your document before uploading.')
        if '/' in name or '\\' in name:
            raise Problem('Use a file name without folders.')
        from document_upload import decode_document
        try:
            raw, extracted = decode_document(name, data)
        except ValueError as error:
            raise Problem(str(error)) from None
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if role is None:self.require_available(db, owner)
            else:self.require_bac_not_resetting(db, owner)
            # Native OpenShell mirrors the workspace around tool calls. Do not
            # let its download overwrite a document uploaded mid-execution.
            self.require_idle(db, owner)
            existing = {file['path'] for file in self.files(owner, role)}
            incoming = {'inbox/' + name}
            if extracted is not None:incoming.add('inbox/' + name + '.txt')
            if len(existing | incoming) > 80:
                raise Problem('Workspace file limit reached.')
            path = safe_file(self.workspace(owner, role), 'inbox/' + name)
            readable = safe_file(self.workspace(owner, role), 'inbox/' + name + '.txt') if extracted is not None else None
            # A binary document and its extracted text form one upload. Never
            # let a separate text upload silently replace that document's view.
            if name.lower().endswith(('.pdf.txt', '.pptx.txt', '.xlsx.txt')):
                original = safe_file(self.workspace(owner, role), 'inbox/' + name[:-4])
                if original.exists():
                    raise Problem('This name is reserved for text extracted from an existing document. Rename your text file before uploading.')
            if readable is not None and readable.exists() and not path.exists():
                raise Problem('A separate text document already uses the extracted-text file name. Rename this document before uploading.')
            path.write_bytes(raw)
            if readable is not None:
                readable.write_text(extracted, encoding='utf-8')
        return {'path': 'inbox/' + name, 'textPath': 'inbox/' + name + '.txt' if extracted is not None else 'inbox/' + name}

    def require_team_idle(self, db, owner):
        from studio import Problem
        self.require_bac_not_resetting(db, owner)
        if not db.execute('SELECT 1 FROM agents WHERE id=? AND deleting=0', (owner,)).fetchone():
            raise Problem('This workspace is unavailable or being deleted.', 409)
        if db.execute('SELECT 1 FROM agent_policies WHERE owner=? AND role>=0 AND updating=1', (owner,)).fetchone():
            raise Problem('This agent’s policy is being updated. Please wait.', 409)
        if db.execute("SELECT 1 FROM jobs WHERE owner=? AND kind IN ('crew','crew-chat','prepare') AND status IN ('queued','running','waiting','stopping')", (owner,)).fetchone():
            raise Problem('The team is busy. Finish or stop its current work first.', 409)

    def enqueue(self, owner, data, source='web', due=0, lead=None):
        if data.get('kind') == 'crew':
            return self.enqueue_event(owner, data, source, due, lead)
        if data.get('kind') == 'prepare':
            raise Problem('Use Event Brief preparation to prepare this team.')
        # Automatic Tech Radar heartbeats use their own delivery path.
        if data.get('kind', 'chat') in ('chat', 'reminder'):
            self.require_manual_chat(self.profile(owner))
        if data.get('kind', 'chat') in ('chat', 'reminder') and is_plan(data.get('prompt')):
            raise Problem('Send /goal to Casey in Open Task. Lounge agents accept direct messages only.')
        collaborative = data.get('kind') == 'crew-chat' and is_plan(data.get('prompt'))
        event_scenario = self.crew_scenario(owner) == 'event-brief'
        if collaborative and event_scenario:
            raise Problem('Use Plan an event for Event Brief, or send /goal to Casey in Open Task.')
        if collaborative:
            origin_role = data.get('crewRole')
            if type(origin_role) is not int or not 0 <= origin_role < len(ROLES):
                raise Problem('Choose a crew member.')
            if origin_role != 0:
                raise Problem('Send /goal to Casey in Open Task. Specialists accept direct messages only.')
            origin = {'owner': owner, 'role': origin_role}
            task = text(plan_task(data['prompt']), 5995, 'Task after /goal')
            owner = self.crew_owner(owner)
            data = {**data, 'kind':'crew-chat', 'crewRole':0, 'skill':None}
            lead = None
        profile = self.profile(lead or owner)
        preset = data.get('kind') == 'crew-chat'
        if not profile and not preset:
            raise Problem('Create your agent first.')
        kind = data.get('kind', 'chat')
        if kind not in ('chat', 'reminder', 'crew-chat'):
            raise Problem('Unknown mission.')
        from chat_images import validate_images
        try:
            images = validate_images(data.get('images', []))
        except ValueError as error:
            raise Problem(str(error)) from None
        if images and kind not in ('chat', 'crew-chat'):
            raise Problem('Images are supported in chat messages.')
        prompt = text(data.get('prompt') or ('Describe the attached image.' if images else ''), 6000, 'Mission')
        skill = data.get('skill')
        if kind == 'crew-chat':
            role = data.get('crewRole')
            if type(role) is not int or not 0 <= role < len(ROLES):
                raise Problem('Choose a crew member.')
            if (event_scenario and role not in range(4)) or (not event_scenario and CREW_CATALOG[role].get('planEligible') is False):
                raise Problem('This specialist is no longer available. Ask Casey to assign the current team.')
            if skill:
                raise Problem('Crew skills are managed by the role.')
        if skill and skill not in profile['skills']:
            raise Problem('This agent has not equipped that skill.')
        payload = {'prompt': prompt, 'skill': skill, 'source': source}
        if kind == 'crew-chat':
            payload['crewRole'] = role
            if collaborative:
                payload['collaboration'] = {'task':task, 'origin':origin, 'activeRole':0, 'outputs':{}, 'handoffs':{}}
        if kind == 'reminder':
            delay = data.get('delay', 60)
            if type(delay) is not int or not 30 <= delay <= 86400:
                raise Problem('Schedule between 30 seconds and 24 hours from now.')
            due = time.time() + delay
        # A schedule may be created while offline, but immediate requests must fail visibly.
        team_request = kind == 'crew-chat'
        from scenario_models import readiness as team_readiness
        readiness = team_readiness(self, owner) if team_request else self.runtime_status()
        ready = readiness.get('teamReady', readiness.get('ready')) if team_request else readiness.get('ready')
        if kind != 'reminder' and not ready:
            if team_request:raise Problem('Check this scenario’s model connection and OpenClaw on the host.', 503)
            raise Problem('Your agent is saved. Start the shared LLM and OpenClaw on the host to run this mission.', 503)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if profile or not preset:
                available = self.require_available(db, lead or owner)
                if kind in ('chat', 'reminder'):
                    self.require_manual_chat(json.loads(available['profile']))
            elif not db.execute('SELECT 1 FROM agents WHERE id=? AND deleting=0', (owner,)).fetchone():
                raise Problem('Open a new studio session.', 404)
            if db.execute('SELECT 1 FROM agent_policies WHERE owner=? AND (CASE WHEN ? THEN role>=0 ELSE role=-1 END) AND updating=1', (owner, preset)).fetchone():
                raise Problem('This agent’s policy is being updated. Please wait.', 409)
            if kind in ('crew','crew-chat'):
                self.require_bac_not_resetting(db, owner)
            if kind == 'crew-chat' and event_scenario and db.execute("SELECT 1 FROM jobs WHERE owner=? AND kind IN ('crew','prepare') AND status IN ('queued','running','waiting','stopping')",(owner,)).fetchone():
                raise Problem('The event team is working. Wait for it to finish before messaging.',409)
            if kind == 'crew-chat' and role == 0 and db.execute(
                    "SELECT 1 FROM jobs WHERE owner=? AND kind='crew-chat' AND status IN ('queued','running','waiting','stopping') AND json_type(payload,'$.collaboration')='object' LIMIT 1", (owner,)).fetchone():
                raise Problem('Casey is coordinating the current plan. Wait for it to finish or stop it before sending a new message.', 409)
            if kind == 'crew-chat' and db.execute(
                    "SELECT 1 FROM jobs WHERE owner=? AND kind='crew-chat' AND status IN ('queued','running','waiting','stopping') AND (CASE WHEN json_type(payload,'$.collaboration')='object' THEN status IN ('running','stopping') AND json_extract(payload,'$.collaboration.activeRole')=? ELSE json_extract(payload,'$.crewRole')=? END) LIMIT 1", (owner, role, role)).fetchone():
                raise Problem('This agent is working. Wait for the current task to finish or stop it before sending a new message.', 409)
            if collaborative:
                if origin['role'] is None:
                    original = self.require_available(db, origin['owner'])
                    self.require_manual_chat(json.loads(original['profile']))
                self.require_team_idle(db, owner)
                payload['roundtable'] = self.capture_roundtable(db, owner)
            # An immediate personal request can do the same preparation itself.
            if kind == 'chat':
                db.execute("UPDATE jobs SET status='cancelled',updated=? WHERE owner=? AND kind='prepare-agent' AND status='queued'", (time.time(), owner))
            # Internal warmups retain deletion/policy fences, but do not spend the
            # attendee's three user-request slots while they open agent workspaces.
            pending = db.execute("SELECT count(*) FROM jobs WHERE kind NOT IN ('prepare-agent','prepare') AND owner IN (SELECT id FROM agents WHERE participant=(SELECT participant FROM agents WHERE id=?)) AND status IN ('queued','running','waiting','stopping')", (owner,)).fetchone()[0]
            if pending >= 3:
                raise Problem('Your collection has three pending missions. Finish or cancel one before adding another.', 429)
            self.initialize_workspace(owner)
            job = {'id': secrets.token_hex(12), 'owner': owner, 'kind': kind, 'status': 'queued',
                   'payload': json.dumps(payload), 'result': '{}', 'events': '[]',
                   'created': time.time(), 'updated': time.time(), 'due': due or time.time()}
            if images:
                import base64
                payload['images']=[]
                for index,(mime,raw) in enumerate(images):
                    extension={'image/png':'png','image/jpeg':'jpg','image/webp':'webp'}[mime]
                    relative='inbox/chat-'+job['id']+'-'+str(index)+'.'+extension
                    safe_file(self.workspace(owner),relative).write_bytes(raw)
                    payload['images'].append({'path':relative,'mime':mime})
                job['payload']=json.dumps(payload)
            db.execute('INSERT INTO jobs VALUES (:id,:owner,:kind,:status,:payload,:result,:events,:created,:updated,:due)', job)
        self.signal.set()
        return {'id': job['id'], **({'collaboration':True, 'crewRole':0} if collaborative else {})}

    def event(self, job_id, title, detail, role=0, **changes):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT events,status FROM jobs WHERE id=?', (job_id,)).fetchone()
            if not row or row['status'] == 'cancelled':return
            if row['status'] == 'stopping' and changes.get('status') in ('done', 'waiting', 'error'):
                changes['status'] = 'cancelled'
                title = 'Stopped at a safe boundary'
                detail = 'The active model call finished. Saved work remains; no next role will start.'
            events = json.loads(row['events'])
            events.append({'time': time.time(), 'title': title, 'detail': detail, 'role': role})
            values = {'events': json.dumps(events[-40:]), 'updated': time.time(), **changes}
            db.execute('UPDATE jobs SET ' + ','.join(key + '=?' for key in values) + ' WHERE id=?', [*values.values(), job_id])

    def decision(self, owner, job_id, action):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if self.profile(owner):
                self.require_available(db, owner)
            row = db.execute('SELECT * FROM jobs WHERE id=? AND owner=?', (job_id, owner)).fetchone()
            if not row:
                raise Problem('Mission not found.', 404)
            if action == 'cancel' and row['status'] in ACTIVE:
                status = 'stopping' if row['status'] in ('running', 'stopping') else 'cancelled'
                events = json.loads(row['events'])
                events.append({'time': time.time(), 'title': 'Stop requested' if status == 'stopping' else 'Mission cancelled',
                               'detail': 'An in-flight model call may finish and write files. Further roles will not start.' if status == 'stopping' else 'Removed from the queue; saved work is preserved.', 'role': 0})
                db.execute('UPDATE jobs SET status=?,events=?,updated=? WHERE id=?', (status, json.dumps(events[-40:]), time.time(), job_id))
                return {'status': status}
            if row['status'] != 'waiting' or row['kind'] != 'crew' or action != 'approve-equipment':
                raise Problem('This decision is not available.', 409)
            payload = json.loads(row['payload'])
            payload['equipmentDecision'] = 'Plan additional equipment, pending availability. Do not imply procurement is confirmed.'
            db.execute("UPDATE jobs SET status='queued',payload=?,due=? WHERE id=?", (json.dumps(payload), time.time(), job_id))
        self.event(job_id, 'You approved a planning assumption', 'Additional equipment remains to be confirmed.', 2)
        self.signal.set()
        return {'status': 'queued'}

    def stop_checkpoint(self, job_id):
        with self.db() as db:
            row = db.execute('SELECT status FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:return True
        status = row['status']
        if status == 'stopping':
            self.event(job_id, 'Stopped at a safe boundary', 'Saved work is preserved. No further model call or channel reply will start.', status='cancelled')
            return True
        return status == 'cancelled'

    @staticmethod
    def crew_chat_reset_state(db, owner):
        account = db.execute('SELECT participant FROM agents WHERE id=?', (owner,)).fetchone()
        if not account:
            raise Problem('Agent not found.', 404)
        saved = db.execute("SELECT value FROM metadata WHERE key IN (?,?) ORDER BY CAST(json_extract(value,'$.at') AS REAL) DESC LIMIT 1",
                           ('crew-chat-reset:'+owner,'crew-chat-reset:'+account['participant'])).fetchone()
        return json.loads(saved['value']) if saved else {'at': 0, 'epoch': ''}

    def reset_crew_chats(self, owner, reset_event=False, *, pending_only=False):
        """Clear the collection's crew chats and start fresh native conversations.

        Stage 3 reset removes team artifacts and attached documents after active work drains.
        Native transcripts remain stored but are not reused as conversation context.
        """
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            account = db.execute('SELECT participant FROM agents WHERE id=?', (owner,)).fetchone()
            if not account:
                raise Problem('Agent not found.', 404)
            scoped = bool(db.execute('SELECT 1 FROM crew_contexts WHERE owner=?',(owner,)).fetchone())
            owners = [owner] if scoped else [r['id'] for r in db.execute('SELECT id FROM agents WHERE participant=?', (account['participant'],))]
            slots = ','.join('?' for _ in owners)
            kinds = "('crew','crew-chat','prepare')" if reset_event else "('crew','crew-chat')"
            active = db.execute("SELECT id,status FROM jobs WHERE owner IN (" + slots + ") AND kind IN " + kinds + " AND status IN ('queued','running','waiting','stopping')", owners).fetchall()
            reset_scope = owner if scoped else account['participant']
            pending_key = 'bac-reset-pending:' + reset_scope
            if pending_only and not db.execute('SELECT 1 FROM metadata WHERE key=?',(pending_key,)).fetchone():
                return {'reset':True}
            if reset_event:
                for job in active:
                    status = 'stopping' if job['status'] in ('running','stopping') else 'cancelled'
                    db.execute('UPDATE jobs SET status=?,updated=? WHERE id=?', (status,time.time(),job['id']))
                # Keep a durable request until both native calls and post-processing
                # drain. Do not erase the rows that stop checkpoints depend on.
                if any(job['status'] in ('running','stopping') for job in active) or self.executing_bac_owners.intersection(owners):
                    db.execute('INSERT OR REPLACE INTO metadata(key,value) VALUES (?,?)', (pending_key,owner))
                    self.signal.set()
                    return {'reset':False,'resetting':True}
                db.execute('DELETE FROM metadata WHERE key=?',(pending_key,))
            elif active:
                raise Problem('Finish or stop the active BaC work before resetting. Nothing was reset.', 409)
            if reset_event:
                # Only explicitly owned team workspaces; personal artifacts and uploads survive.
                teams = [owner] if scoped else [r['owner'] for r in db.execute('SELECT owner FROM crew_contexts WHERE participant=?', (account['participant'],))]
                workspaces = {self.workspace(team) for team in teams}
                for team in teams:
                    workspaces.update(self.workspace(team, role) for role in range(len(ROLES)))
                # Reject redirected parents before deleting anything. Artifact symlinks
                # themselves are unlinked without following their targets.
                for workspace in workspaces:
                    if workspace.parent.is_symlink() or workspace.is_symlink():
                        raise Problem('Team workspace is redirected; files were not cleared.', 409)
                for workspace in workspaces:
                    for category in ('artifacts', 'inbox'):
                        folder = workspace / category
                        if folder.is_symlink():
                            folder.unlink()
                        elif folder.is_dir():
                            shutil.rmtree(folder)
                        elif folder.exists():
                            folder.unlink()
                        if workspace.is_dir():
                            folder.mkdir(exist_ok=True)
            # Rotate an account-scoped session epoch after artifact cleanup succeeds.
            # Native agent cleanup is independent; active crew calls are fenced above.
            reset = {'at': time.time(), 'epoch': secrets.token_hex(12)}
            removed = db.execute("DELETE FROM jobs WHERE owner IN (" + slots + ") AND kind='crew-chat'", owners).rowcount
            db.execute('INSERT OR REPLACE INTO metadata (key,value) VALUES (?,?)',
                       ('crew-chat-reset:' + reset_scope, json.dumps(reset)))
            if reset_event:
                db.execute('INSERT OR REPLACE INTO metadata (key,value) VALUES (?,?)',
                           ('event-board-reset:' + reset_scope, str(reset['at'])))
                db.execute("DELETE FROM jobs WHERE owner IN (" + slots + ") AND kind='prepare'", owners)
        return {'reset': True, 'removed': removed, 'crewChatReset': reset}

    def finish_pending_bac_resets(self):
        with self.db() as db:
            pending = db.execute("SELECT DISTINCT a.id FROM metadata m JOIN agents a ON m.value=a.id WHERE m.key LIKE 'bac-reset-pending:%'").fetchall()
        for row in pending:
            try:
                self.reset_crew_chats(row['id'], reset_event=True, pending_only=True)
            except Problem as error:
                if error.status != 404:raise

    def require_bac_not_resetting(self, db, owner):
        if db.execute("SELECT 1 FROM metadata m JOIN agents a ON (m.key='bac-reset-pending:'||a.participant OR m.key='bac-reset-pending:'||a.id) WHERE a.id=?",(owner,)).fetchone():
            raise Problem('BaC is stopping its current work and resetting. Please wait.',409)

    def reset_board(self, owner):
        """Archive this agent's board, preserving identity, memory and files."""
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute("SELECT 1 FROM jobs WHERE owner=? AND status IN ('running','stopping')", (owner,)).fetchone():
                raise Problem('Stop the active mission and wait for it to finish before resetting. Nothing was reset.', 409)
            for row in db.execute("SELECT id,events FROM jobs WHERE owner=? AND status IN ('queued','waiting')", (owner,)).fetchall():
                events = json.loads(row['events']) + [{'time': time.time(), 'title': 'Board reset', 'detail': 'Pending mission cancelled before archiving.', 'role': 0}]
                db.execute("UPDATE jobs SET status='cancelled',events=?,updated=? WHERE id=?", (json.dumps(events[-40:]), time.time(), row['id']))
            db.execute('UPDATE agents SET reset_at=? WHERE id=?', (time.time(), owner))
            db.execute('UPDATE participants SET reset_at=? WHERE id=?', (time.time(), owner))
        return {'reset': True, 'preserved': ['agent', 'memory', 'files', 'archived evidence']}

    def evidence(self, owner, job_id):
        with self.db() as db:
            row = db.execute('SELECT * FROM jobs WHERE id=? AND owner=?', (job_id, owner)).fetchone()
        if not row:
            raise Problem('Mission not found.', 404)
        # Explicit export by the participant. No cookie, credential or global log is included.
        return {'schema': 1, 'exported': time.time(), 'scope': 'This participant’s selected mission only',
                'runtime': {'version': runtime.VERSION, 'model': 'bac-local',
                            'events': 'App-observed lifecycle and handoffs; not native tool traces'},
                'mission': self.public_job(row)}

    def prepare_builtin_crew(self, owner, role, member):
        """Verify built-in protection before preparation, direct chat, and event work."""
        from studio_policy import ProtectionNotVerified
        # Saved jobs from an older build must not restore an unprotected Dylan.
        member['protection'] = CREW_CATALOG[role].get('protection', 'standard')
        agent_id = member['id']
        from team_models import selections
        member['_teamModel'] = selections(self,owner)[role]['id']
        from scenario_models import prepare
        prepare(self, owner, member)
        control = member.get('_planControl') if role == 0 else None
        if control not in (None, 'none', 'read'):
            raise ValueError('Invalid Captain tool mode')
        mode = 'research-brief' if role == 8 and member.get('_researchBrief') else control
        modes = self.__dict__.setdefault('_crew_tool_modes', {})
        if agent_id not in self.provisioned or modes.get(agent_id) != mode:
            self.initialize_workspace(owner)
            self.adapter.register(agent_id, self.workspace(owner, role), member, member['role'])
            self.provisioned.add(agent_id)
            modes[agent_id] = mode
        if member['protection'] != 'openshell':
            return None
        _, approvals = self.saved_policy(owner, role)
        report = self.adapter.policy_status(agent_id, 'openshell', approvals)
        if report['status'] == 'awaiting-first-mission':
            self.adapter.policy_prepare(agent_id)
        if report['status'] != 'applied':
            report = self.adapter.policy_apply(agent_id, approvals)
        if report['status'] != 'applied':
            raise ProtectionNotVerified(report['status'])
        return {key:report[key] for key in ('mode','status','checkedAt','rules','sandboxes') if key in report}

    def ensure_agent(self, owner, profile, role=None):
        role = None if role == 0 else role
        agent_id = profile['id'] if role is None else profile['id'] + '-r' + str(role)
        if role is not None:
            member = {'name':ROLES[role][0], 'persona':ROLES[role][2], 'skills':list(ROLE_SKILLS[role]), 'id':agent_id, 'role':ROLES[role][1]}
            self.prepare_builtin_crew(owner, role, member)
        elif agent_id not in self.provisioned:
            native = profile if role is None else {'name': ROLES[role][0], 'persona': ROLES[role][2], 'skills': list(ROLE_SKILLS[role])}
            self.adapter.register(agent_id, self.workspace(owner, role), native, ROLES[role][1] if role is not None else None)
            self.provisioned.add(agent_id)
        return agent_id

    def record_usage(self, job_id, payload, answer, agent_id, name, stage=0):
        metrics = getattr(answer, 'metrics', {})
        payload.setdefault('metrics', {})[str(stage)] = {**metrics, 'agent': agent_id, 'name': name}
        # Save immediately, including when a later artifact validation fails.
        with self.db() as db:
            db.execute('UPDATE jobs SET payload=? WHERE id=?', (json.dumps(payload), job_id))

    def agent_lock(self, agent_id):
        with self.execution_lock:
            return self.agent_locks.setdefault(agent_id, threading.RLock())

    def refresh_executing(self):
        self.executing_owners = set().union(*(owners for owners, _ in self.executing_jobs.values()))
        self.executing_bac_owners = set().union(*(owners for owners, bac in self.executing_jobs.values() if bac))

    def execute(self, row):
        payload = json.loads(row['payload'])
        owners = {row['owner']} | {m['key'] for m in job_participants(payload) if m.get('key')}
        with self.execution_lock:
            self.executing_jobs[row['id']] = (owners, row['kind'] in ('crew','crew-chat','prepare'))
            self.refresh_executing()
        try:
            # Cover preparation, model calls and artifact collection with the same
            # identity lock used by individual collaboration stages.
            if row['kind'] == 'crew-chat' and not payload.get('collaboration'):
                lock = self.agent_lock(self.crew_native_id(row['owner'], payload['crewRole']))
            else:
                lock = contextlib.nullcontext()
            with lock:
                return self._execute(row)
        except Exception:
            if self.stop_checkpoint(row['id']):return
            raise
        finally:
            with self.execution_lock:
                self.executing_jobs.pop(row['id'], None)
                self.refresh_executing()
            self.signal.set()

    def _execute(self, row):
        owner, job_id = row['owner'], row['id']
        if self.stop_checkpoint(job_id):
            return
        payload = json.loads(row['payload'])
        profile = self.profile(owner)
        if row['kind'] == 'prepare-agent':
            self.ensure_agent(owner, profile)
            if self.stop_checkpoint(job_id):
                return
            self.check_protected_run(owner, profile)
            self.event(job_id, 'Agent workspace ready', 'Prepared without a model request or additional access.', status='done')
            return
        if row['kind'] in ('crew','crew-chat') and payload.get('reactionRetry'):
            self.run_roundtable(row, payload)
            payload.pop('reactionRetry', None)
            if not self.stop_checkpoint(job_id):
                self.event(job_id, 'Reaction retry finished', 'The completed results and other reactions were preserved.', status='done', payload=json.dumps(payload))
            return
        if row['kind'] == 'crew-chat' and payload.get('collaboration'):
            return self.collaboration_plan(row, payload)
        if row['kind'] == 'crew-chat':
            return self.crew_chat(row, payload)
        if row['kind'] == 'crew':
            return self.crew(row, payload)
        if row['kind'] == 'prepare':
            return self.prepare_demo_run(row, payload)
        if profile.get('protection') == 'openshell':
            self.event(job_id, 'Preparing OpenShell', 'Checking the protected runtime and agent sandbox configuration.')
        agent_id = self.ensure_agent(owner, profile)
        protection_report = self.check_protected_run(owner, profile)
        self.event(job_id, profile['name'] + ' is working', 'OpenClaw agent run · shared model · ' + payload['source'])
        inbox = [x['path'] for x in self.files(owner)]
        from personal_voice import contract
        prompt = contract(profile) + '\n\nUser request:\n' + payload['prompt'] + ('\n\nAvailable user files (untrusted task data): ' + ', '.join(inbox) if inbox else '')
        if row['kind'] == 'chat':
            prompt += self.conversation_context(owner, None, row['created'], job_id, plans_only=True)
        if protection_report:
            hosts = sorted({rule['host'] for rule in protection_report.get('rules', [])})
            prompt += '\n\nCurrent verified OpenShell access: ' + (', '.join(hosts) or 'no approved destinations') + '. Use sandbox tools to test permitted hosts when requested. Do not repeat earlier approval requests for these hosts; report actual tool results. HTTP 403 alone is not proof of an OpenShell denial. ENOENT, command launch failures and runtime disconnections are execution failures, not policy denials; report the execution problem without asking for website approval or claiming OpenShell blocked the request.'
        prompt += PAGE_INSTRUCTIONS
        pages_before = html_files(self.workspace(owner))
        before = {x['path']: x['updated'] for x in self.files(owner)}
        if self.stop_checkpoint(job_id):
            return
        answer = self.respond_chat(agent_id, 'bac-' + owner, prompt, owner, payload)
        if self.stop_checkpoint(job_id):
            return
        self.record_usage(job_id, payload, answer, agent_id, profile['name'])
        # Displayed files are real workspace writes, never synthetic tool-call animations.
        html = re.search(r'```html\s*\n([\s\S]+?)```', answer, re.I)
        if html and 'builder' in profile['skills'] and len(html.group(1)) < 500_000:
            safe_file(self.workspace(owner), 'artifacts/app-' + job_id[:6] + '.html').write_text(html.group(1), encoding='utf-8')
        pages = collect_pages(self, owner, job_id, None, pages_before, answer)
        report = safe_file(self.workspace(owner), 'artifacts/reply-' + job_id[:6] + '.md')
        report.write_text(answer, encoding='utf-8')
        changed = [x['path'] for x in self.files(owner) if x['path'] not in before or x['updated'] > before[x['path']]]
        changed = [p for p in changed if not p.lower().endswith('.html')] + pages
        self.event(job_id, 'Result saved', ', '.join(changed) or 'Agent response received.',
                   result=json.dumps({'answer': answer, 'files': changed, 'activity':getattr(answer,'activity',None)}), status='done')
        if self.stop_checkpoint(job_id):
            return

    def respond_chat(self, agent_id, session, prompt, owner, payload):
        from artifact_references import relative_references
        prompt += ('\nWhen describing saved deliverables, use workspace-relative paths such as '
                   'artifacts/research-brief.md, not absolute host or container paths. '
                   'Keep supplied verified artifact download references unchanged. '
                   'This is a presentation rule, not permission to read other workspaces.')
        options = {'json_response': True} if payload.get('_captainDecision') and payload.get('crewRole') == 0 else {}
        if payload.get('_responseTimeout') is not None:
            options['timeout'] = payload['_responseTimeout']
        if payload.get('images'):
            import base64
            options['images'] = [{'mime': image['mime'], 'data': base64.b64encode(safe_file(self.workspace(owner), image['path'], True).read_bytes()).decode()} for image in payload['images']]
        answer = self.protected_response(agent_id, session, prompt, owner, payload.get('crewRole'), **options)
        return relative_references(answer, self.workspace(owner, payload.get('crewRole')),
                                   structured=options.get('json_response', False))

    def crew_chat(self, row, payload):
        owner, job_id, role = row['owner'], row['id'], payload['crewRole']
        with self.db() as db:
            member = self.crew_roster(db, owner, {}, preset=True)[role]
            reset = self.crew_chat_reset_state(db, owner)
            current_event = db.execute("SELECT 1 FROM jobs WHERE owner=? AND kind='crew' AND created>=?", (owner, reset['at'])).fetchone()
        event_scenario = self.crew_scenario(owner) == 'event-brief'
        member['purpose'] = CREW_CATALOG[role]['description'] if event_scenario else CREW_CATALOG[role]['collaboration']['description']
        agent_id = member['id']
        report = self.prepare_builtin_crew(owner, role, member)
        if report:
            payload['protection'] = report
            self.event(job_id, 'OpenShell verified', 'Saved OpenShell access verified. Unapproved destinations remain blocked.', role, payload=json.dumps(payload))
        self.event(job_id, member['name'] + ' is working', member['role'], role)
        if self.stop_checkpoint(job_id):
            return
        prompt = ('You are ' + member['name'] + ', the ' + CREW_CATALOG[role]['collaboration']['title'] + '. '
                  + member['purpose'] + '\nAnswer this direct message using your equipped skills. '
                  + ('The inbox may contain the latest event brief and handoffs; use them when relevant. ' if current_event else 'No event has been submitted in this conversation yet. Do not load earlier event briefs, handoffs or conversation transcripts. ') +
                  'This is a conversation, not a new crew mission. Do not claim other agents ran, '
                  'or send invitations or publish anything on the user’s behalf.\n\n' + payload['prompt'])
        if role == 0:
            prompt += '\nCommunication style: ' + CREW_CATALOG[0]['collaboration'].get('voice', '')
        prompt += self.conversation_context(owner, role, row['created'], job_id, plans_only=True)
        session = self.crew_chat_session(owner, role) + ('-' + reset['epoch'] if reset['epoch'] else '')
        prompt += PAGE_INSTRUCTIONS
        if role == 5:
            prompt += DEMO_CODING_INSTRUCTIONS
        pages_before = html_files(self.workspace(owner, role))
        answer = self.respond_chat(agent_id, session, prompt, owner, payload)
        pages = collect_pages(self, owner, job_id, role, pages_before, answer)
        self.record_usage(job_id, payload, answer, agent_id, member['name'], role)
        self.event(job_id, 'Reply ready', member['name'], role,
                   result=json.dumps({'answer': answer,'files':pages,'activity':getattr(answer,'activity',None)}), status='done')

    @staticmethod
    def chat_lane(row):
        payload = json.loads(row['payload'])
        return row['kind'] in ('chat', 'reminder') or (row['kind'] == 'crew-chat' and not payload.get('collaboration') and not payload.get('reactionRetry'))

    def next_job(self, lane=None):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            # Defense in depth for stale queued work after an interrupted edit.
            db.execute("DELETE FROM jobs WHERE status='queued' AND NOT EXISTS (SELECT 1 FROM agents WHERE agents.id=jobs.owner)")
            db.execute("UPDATE jobs SET status='cancelled',updated=? WHERE status='queued' AND owner IN (SELECT id FROM agents WHERE deleting!=0)", (time.time(),))
            candidates = db.execute("SELECT * FROM jobs WHERE status='queued' AND due<=? AND NOT (kind IN ('prepare-agent','prepare') AND EXISTS (SELECT 1 FROM agent_policies WHERE owner=jobs.owner AND updating=1)) ORDER BY (kind='prepare-agent' OR (kind='prepare' AND coalesce(json_extract(payload,'$.background'),0)=1)),due,created", (time.time(),)).fetchall()
            active = db.execute("SELECT * FROM jobs WHERE status IN ('running','stopping')").fetchall()
            with self.execution_lock:
                finishing = set(self.executing_jobs)
            if finishing:
                active += [r for r in db.execute("SELECT * FROM jobs WHERE id IN (" + ','.join('?' for _ in finishing) + ")", tuple(finishing)) if r['status'] not in ('running','stopping')]
            row = None
            for candidate in candidates:
                if lane is not None and self.chat_lane(candidate) != (lane == 'chat'):
                    continue
                cp = json.loads(candidate['payload'])
                blocked = False
                for busy in active:
                    bp = json.loads(busy['payload'])
                    related = {busy['owner']} | {m['key'] for m in job_participants(bp) if m.get('key')}
                    candidate_owners = {candidate['owner']} | {m['key'] for m in job_participants(cp) if m.get('key')}
                    if not candidate_owners.intersection(related):
                        continue
                    if candidate['kind'] == busy['kind'] == 'crew-chat' and candidate['owner'] == busy['owner']:
                        cr = cp.get('crewRole')
                        br = bp.get('collaboration', {}).get('activeRole', bp.get('crewRole'))
                        if not cp.get('collaboration') and not bp.get('reactionRetry') and cr != br:
                            continue
                    blocked = True
                    break
                if not blocked:
                    row = candidate
                    break
            if row:
                db.execute("UPDATE jobs SET status='running',updated=? WHERE id=?", (time.time(), row['id']))
        return row

    def work(self, lane='background'):
        while not self.stop.is_set():
            if lane == 'background':
                self.finish_pending_bac_resets()
                if self.deletion_worker is None:self.finish_pending_deletions()
            row = self.next_job(lane)
            if row:
                try:
                    self.execute(row)
                except Exception as error:
                    import logging
                    logging.exception('Mission %s failed', row['id'])
                    message = str(error) if isinstance(error, (RuntimeError, Problem)) else 'Task failed. Check the host application logs and saved files before retrying.'
                    self.event(row['id'], 'Mission needs attention', message, status='error', result=json.dumps({'error': message}))
            else:
                self.signal.wait(1)
                self.signal.clear()
