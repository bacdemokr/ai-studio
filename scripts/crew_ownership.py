"""Account-owned BaC teams, independent of the hired-agent deletion lifecycle.

Crew contexts use the existing owner foreign keys, but are never selectable or
counted as personal agents. Each team explicitly owns its native role identities, workspace names and chat
sessions. Personal deletion never traverses these resources.
"""
import secrets
import time


class CrewOwnership:
    def existing_crew_owner(self, owner):
        """Reading session/settings state must not create a team or workspaces."""
        with self.db() as db:
            row=db.execute('''SELECT c.owner FROM crew_contexts c JOIN agents a
                ON a.participant=c.participant WHERE a.id=?''',(owner,)).fetchone()
        return row['owner'] if row else None

    def initialize_crew_ownership(self):
        from studio import ROLES
        with self.db() as db:
            if 'kind' not in {r['name'] for r in db.execute('PRAGMA table_info(agents)')}:
                db.execute("ALTER TABLE agents ADD COLUMN kind TEXT NOT NULL DEFAULT 'personal'")
            db.execute('CREATE TABLE IF NOT EXISTS crew_contexts (owner TEXT PRIMARY KEY, participant TEXT NOT NULL UNIQUE)')
            if {r['name'] for r in db.execute('PRAGMA table_info(crew_contexts)')} != {'owner','participant'}:
                raise RuntimeError('Crew storage cleanup must finish before starting this version.')
            db.execute('''CREATE TABLE IF NOT EXISTS crew_resources (
                owner TEXT NOT NULL, role INTEGER NOT NULL, native_id TEXT NOT NULL UNIQUE,
                workspace_name TEXT NOT NULL UNIQUE, chat_session TEXT NOT NULL UNIQUE,
                PRIMARY KEY(owner,role))''')
            # Expand each existing team's explicitly owned reserve roster. This
            # creates ownership records only, not native runtimes or sandboxes.
            for row in db.execute('SELECT owner FROM crew_contexts').fetchall():
                team = row['owner']
                for role in range(len(ROLES)):
                    db.execute('INSERT OR IGNORE INTO crew_resources VALUES (?,?,?,?,?)',
                               (team, role, 'bac-'+team+'-r'+str(role), team+'-'+str(role), 'bac-crew-chat-'+team+'-'+str(role)))
            self.crew_resources = {(r['owner'],r['role']):dict(r) for r in db.execute('SELECT * FROM crew_resources')}

    def crew_owner(self, owner):
        """Resolve the authenticated owner's shared team; never another account's."""
        from studio import Problem, ROLES
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            account = db.execute('SELECT participant,kind FROM agents WHERE id=?', (owner,)).fetchone()
            if not account:raise Problem('Agent not found.',404)
            if account['kind']=='crew':return owner
            found = db.execute('SELECT owner FROM crew_contexts WHERE participant=?', (account['participant'],)).fetchone()
            if found:return found['owner']
            team = secrets.token_hex(12)
            db.execute("INSERT INTO agents(id,participant,created,kind) VALUES (?,?,?,'crew')", (team,account['participant'],time.time()))
            db.execute('INSERT INTO crew_contexts(owner,participant) VALUES (?,?)', (team,account['participant']))
            resources=[]
            for role in range(len(ROLES)):
                resource=dict(owner=team,role=role,native_id='bac-'+team+'-r'+str(role),workspace_name=team+'-'+str(role),chat_session='bac-crew-chat-'+team+'-'+str(role))
                db.execute('INSERT INTO crew_resources VALUES (:owner,:role,:native_id,:workspace_name,:chat_session)',resource)
                resources.append(resource)
            self.crew_resources.update({(team,r['role']):r for r in resources})
        self.initialize_workspace(team)
        self.initialize_crew_workspaces(team)
        return team

    def crew_native_id(self, owner, role):
        resource = self.crew_resources.get((owner,role))
        return resource['native_id'] if resource else 'bac-'+owner+'-r'+str(role)

    def crew_chat_session(self, owner, role):
        resource = self.crew_resources.get((owner,role))
        return resource['chat_session'] if resource else 'bac-crew-chat-'+owner+'-'+str(role)

    def job_owner(self, selected, job_id):
        """Allow selected personal jobs and any shared team job in this account."""
        from studio import Problem
        with self.db() as db:
            row = db.execute('''SELECT j.owner FROM jobs j JOIN agents a ON a.id=j.owner
                WHERE j.id=? AND (j.owner=? OR (a.kind='crew' AND a.participant=
                (SELECT participant FROM agents WHERE id=?)))''', (job_id,selected,selected)).fetchone()
        if not row:raise Problem('Mission not found.',404)
        return row['owner']

    def available_file(self, selected, name):
        """Find generated team artifacts within the authenticated account."""
        from studio import safe_file, Problem
        path = safe_file(self.workspace(selected),name)
        if path.is_file():return safe_file(self.workspace(selected),name,True)
        # Crew downloads are generated artifacts. Never fall back to another
        # agent's memory, identity or personal inbox.
        if name.startswith('artifacts/'):
            with self.db() as db:
                teams = [r['owner'] for r in db.execute('SELECT owner FROM crew_contexts WHERE participant=(SELECT participant FROM agents WHERE id=?) ORDER BY owner', (selected,))]
            matches = [safe_file(self.workspace(team),name,True) for team in teams if safe_file(self.workspace(team),name).is_file()]
            if len(matches)==1:return matches[0]
        raise Problem('File is not available.',404)
