"""Authenticated attendee controls for their own personal-agent policy."""
import json
import time

from agent_policy import CATALOG


class PolicyControls:
    def policy_report(self, owner):
        from studio import Problem
        profile = self.profile(owner)
        if not profile:
            raise Problem('Create a personal agent to inspect its policy.', 404)
        with self.db() as db:
            row = db.execute('SELECT * FROM agent_policies WHERE owner=?', (owner,)).fetchone()
        approved = json.loads(row['approved']) if row else []
        report = self.adapter.policy_status(profile['id'], profile.get('protection', 'standard'), approved)
        report.update(agentId=owner, agentName=profile['name'], history=json.loads(row['events']) if row else [],
                      updating=bool(row and row['updating']))
        return report

    def policy_change(self, owner, data):
        from studio import Problem
        profile = self.profile(owner)
        if not profile:
            raise Problem('Create a personal agent first.', 404)
        if 'mode' in data:
            mode = data['mode']
            if mode not in ('standard', 'openshell'):
                raise Problem('Choose OpenShell on or off.')
            self.configure(owner, {**profile, 'protection': mode})
            self.record_policy(owner, 'OpenShell ' + ('selected' if mode == 'openshell' else 'turned off'),
                               'Saved for this personal agent. The next mission loads its native configuration.')
            return {'saved': True, 'mode': mode}
        permission, allow = data.get('permission'), data.get('allow')
        retry = data.get('retry') is True
        if not retry and (not isinstance(permission, str) or permission not in CATALOG or type(allow) is not bool):
            raise Problem('Choose an available public-read permission.')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            self.require_available(db, owner)
            self.require_idle(db, owner)
            current = json.loads(db.execute('SELECT profile FROM agents WHERE id=?', (owner,)).fetchone()['profile'])
            if current.get('protection') != 'openshell':
                raise Problem('Turn on OpenShell for this agent first.', 409)
            db.execute('INSERT OR IGNORE INTO agent_policies (owner) VALUES (?)', (owner,))
            row = db.execute('SELECT approved FROM agent_policies WHERE owner=?', (owner,)).fetchone()
            approved = set(json.loads(row['approved']))
            if not retry:
                approved.add(permission) if allow else approved.discard(permission)
            approved = sorted(approved)
            db.execute('UPDATE agent_policies SET approved=?,updating=1 WHERE owner=?', (json.dumps(approved), owner))
        try:
            self.adapter.policy_apply(profile['id'], approved)
            self.record_policy(owner, 'Policy synchronized' if retry else 'Permission approved' if allow else 'Permission revoked', ('Requested permissions' if retry else CATALOG[permission]['title']) + ' · OpenShell confirmed the loaded policy.')
            return {'applied': True}
        except Exception:
            self.record_policy(owner, 'Policy update needs attention', 'The requested change is not confirmed. Refresh the live policy; no successful approval is claimed.')
            raise Problem('The policy change was not confirmed. Check host setup and refresh the live policy before retrying.', 503) from None
        finally:
            with self.db() as db:
                db.execute('UPDATE agent_policies SET updating=0 WHERE owner=?', (owner,))

    def record_policy(self, owner, title, detail):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM agents WHERE id=?', (owner,)).fetchone():
                return
            db.execute('INSERT OR IGNORE INTO agent_policies (owner) VALUES (?)', (owner,))
            row = db.execute('SELECT events FROM agent_policies WHERE owner=?', (owner,)).fetchone()
            events = json.loads(row['events']) + [{'time': time.time(), 'title': title, 'detail': detail, 'source': 'Attendee control'}]
            db.execute('UPDATE agent_policies SET events=? WHERE owner=?', (json.dumps(events[-40:]), owner))

    def check_protected_run(self, owner, profile):
        if profile.get('protection') != 'openshell':
            return
        report = self.policy_report(owner)
        if report['status'] not in ('applied', 'awaiting-first-mission'):
            raise RuntimeError('OpenShell protection is not verified. Inspect this agent’s Policies tab before running a mission. No unprotected fallback was used.')
