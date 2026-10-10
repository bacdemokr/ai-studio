"""Account-owned BaC teams, independent of the hired-agent deletion lifecycle.

Crew contexts use the existing owner foreign keys, but are never selectable or
counted as personal agents. Each team explicitly owns its native role identities, workspace names and chat
sessions. Personal deletion never traverses these resources.
"""
import secrets
import time


class CrewOwnership:
    def browsing_workspace(self, owner, scenario, selection='personal'):
        """Resolve a browser selection through account ownership, never a host path."""
        from studio import Problem, CREW_CATALOG
        if selection == 'personal':
            return owner, None
        role = None
        if selection != 'team':
            if not isinstance(selection, str) or not selection.isascii() or not selection.isdecimal():
                raise Problem('Choose a valid workspace.')
            role = int(selection)
            if role not in range(len(CREW_CATALOG)) or (scenario == 'event-brief' and role >= 4) or (scenario == 'plan' and CREW_CATALOG[role].get('planEligible') is False):
                raise Problem('Choose a member of this scenario.')
        team = self.existing_crew_owner(owner, scenario)
        return team, role

    def existing_crew_owner(self, owner, scenario=None):
        """Reading session/settings state must not create a team or workspaces."""
        with self.db() as db:
            if scenario is None and db.execute('SELECT 1 FROM crew_contexts WHERE owner=?',(owner,)).fetchone():return owner
            from scenarios import validate
            scenario=validate(scenario or 'plan')
            row=db.execute('''SELECT c.owner FROM crew_contexts c JOIN agents a
                ON a.participant=c.participant WHERE a.id=? AND c.scenario=?''',(owner,scenario)).fetchone()
        return row['owner'] if row else None

    def crew_scenario(self, owner):
        with self.db() as db:
            row=db.execute('SELECT scenario FROM crew_contexts WHERE owner=?',(owner,)).fetchone()
        return row['scenario'] if row else 'plan'

    def scenario_status(self, owner):
        from scenarios import SCENARIOS
        from studio import ROLES
        with self.db() as db:
            result=[]
            for scenario in SCENARIOS:
                team=db.execute('SELECT owner FROM crew_contexts WHERE scenario=? AND participant=(SELECT participant FROM agents WHERE id=?)',(scenario,owner)).fetchone()
                # Completed automatic warmup is infrastructure, not saved user
                # work. Otherwise Reset immediately enables itself again.
                latest=db.execute("SELECT status,updated FROM jobs WHERE owner=? AND kind IN ('crew','crew-chat','prepare') AND NOT (kind='prepare' AND status='done' AND COALESCE(json_extract(payload,'$.background'),0)=1) ORDER BY created DESC LIMIT 1",(team['owner'],)).fetchone() if team else None
                busy=bool(team and db.execute("SELECT 1 FROM jobs WHERE owner=? AND status IN ('queued','running','waiting','stopping') LIMIT 1",(team['owner'],)).fetchone())
                reset=self.crew_chat_reset_state(db,team['owner'])['at'] if team else 0
                if latest and latest['updated']<reset:latest=None
                saved_files = [f for role in (None, *range(len(ROLES)))
                               for f in self.files(team['owner'], role, recursive=True)] if team and not latest else []
                result.append(dict(id=scenario,hasWork=bool(latest or saved_files),busy=busy,status=latest['status'] if latest else None,updated=latest['updated'] if latest else max((f['updated'] for f in saved_files), default=None)))
        return result

    def initialize_crew_ownership(self):
        from studio import ROLES
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if 'kind' not in {r['name'] for r in db.execute('PRAGMA table_info(agents)')}:
                db.execute("ALTER TABLE agents ADD COLUMN kind TEXT NOT NULL DEFAULT 'personal'")
            db.execute("CREATE TABLE IF NOT EXISTS crew_contexts (owner TEXT PRIMARY KEY, participant TEXT NOT NULL, scenario TEXT NOT NULL DEFAULT 'plan', UNIQUE(participant,scenario))")
            columns={r['name'] for r in db.execute('PRAGMA table_info(crew_contexts)')}
            if columns == {'owner','participant'}:
                # Existing Zurich teams and native identities remain the /plan team.
                db.execute('ALTER TABLE crew_contexts RENAME TO crew_contexts_before_scenarios')
                db.execute("CREATE TABLE crew_contexts (owner TEXT PRIMARY KEY, participant TEXT NOT NULL, scenario TEXT NOT NULL DEFAULT 'plan', UNIQUE(participant,scenario))")
                db.execute("INSERT INTO crew_contexts SELECT owner,participant,'plan' FROM crew_contexts_before_scenarios")
                db.execute('DROP TABLE crew_contexts_before_scenarios')
            elif columns != {'owner','participant','scenario'}:
                raise RuntimeError('Crew storage cleanup must finish before starting this version.')
            db.execute('''CREATE TABLE IF NOT EXISTS crew_resources (
                owner TEXT NOT NULL, role INTEGER NOT NULL, native_id TEXT NOT NULL UNIQUE,
                workspace_name TEXT NOT NULL UNIQUE, chat_session TEXT NOT NULL UNIQUE,
                PRIMARY KEY(owner,role))''')
            if 'model' not in {r['name'] for r in db.execute('PRAGMA table_info(crew_resources)')}:
                db.execute('ALTER TABLE crew_resources ADD COLUMN model TEXT')
            # Expand each existing team's explicitly owned reserve roster. This
            # creates ownership records only, not native runtimes or sandboxes.
            for row in db.execute('SELECT owner FROM crew_contexts').fetchall():
                team = row['owner']
                for role in range(len(ROLES)):
                    db.execute('INSERT OR IGNORE INTO crew_resources(owner,role,native_id,workspace_name,chat_session) VALUES (?,?,?,?,?)',
                               (team, role, 'bac-'+team+'-r'+str(role), team+'-'+str(role), 'bac-crew-chat-'+team+'-'+str(role)))
            self.crew_resources = {(r['owner'],r['role']):dict(r) for r in db.execute('SELECT * FROM crew_resources')}

    def crew_owner(self, owner, scenario=None):
        """Resolve the authenticated owner's shared team; never another account's."""
        from studio import Problem, ROLES
        from scenarios import validate
        if scenario is not None:validate(scenario)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            account = db.execute('SELECT participant,kind FROM agents WHERE id=?', (owner,)).fetchone()
            if not account:raise Problem('Agent not found.',404)
            if account['kind']=='crew' and scenario is None:return owner
            scenario=scenario or 'plan'
            found = db.execute('SELECT owner FROM crew_contexts WHERE participant=? AND scenario=?', (account['participant'],scenario)).fetchone()
            if found:return found['owner']
            team = secrets.token_hex(12)
            db.execute("INSERT INTO agents(id,participant,created,kind) VALUES (?,?,?,'crew')", (team,account['participant'],time.time()))
            db.execute('INSERT INTO crew_contexts(owner,participant,scenario) VALUES (?,?,?)', (team,account['participant'],scenario))
            resources=[]
            for role in range(len(ROLES)):
                resource=dict(owner=team,role=role,native_id='bac-'+team+'-r'+str(role),workspace_name=team+'-'+str(role),chat_session='bac-crew-chat-'+team+'-'+str(role))
                db.execute('INSERT INTO crew_resources(owner,role,native_id,workspace_name,chat_session) VALUES (:owner,:role,:native_id,:workspace_name,:chat_session)',resource)
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

    def available_file(self, selected, name, scenario=None):
        """Find generated team artifacts within the authenticated account."""
        from studio import safe_file, Problem
        path = safe_file(self.workspace(selected),name)
        if path.is_file():return safe_file(self.workspace(selected),name,True)
        # Crew downloads are generated artifacts. Never fall back to another
        # agent's memory, identity or personal inbox.
        if name.startswith('artifacts/'):
            with self.db() as db:
                query = 'SELECT owner FROM crew_contexts WHERE participant=(SELECT participant FROM agents WHERE id=?)'
                values = [selected]
                if scenario is not None:
                    from scenarios import validate
                    query += ' AND scenario=?'
                    values.append(validate(scenario))
                teams = [r['owner'] for r in db.execute(query + ' ORDER BY owner', values)]
            matches = [safe_file(self.workspace(team),name,True) for team in teams if safe_file(self.workspace(team),name).is_file()]
            if len(matches)==1:return matches[0]
        raise Problem('File is not available.',404)
