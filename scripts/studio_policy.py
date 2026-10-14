"""Shared, identity-scoped OpenShell controls for personal agents and BaC crew."""
import json
import time
import re
import math
from urllib.parse import urlsplit

from agent_policy import CATALOG, destination_permission, permission_rule, individual_permissions


def prompt_hosts(prompt):
    """Return public destinations without letting malformed chat URLs break policy reads."""
    pattern = (r'(?:https?://|www\.)[^\s<>"\\]+'
               r'|(?<![\w@/\\.*:-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}'
               r'(?::[0-9]+)?(?:/[^\s<>"\\]*)?(?![\w@-]|\.[a-z0-9])')
    seen = set()
    for match in re.finditer(pattern, prompt.replace('\\.', '.'), re.I):
        value = match.group().rstrip('.,;!?)]}*`\'')
        try:
            host = urlsplit(value if '://' in value else 'https://' + value).hostname or ''
            key = destination_permission(host)
            host = permission_rule(key)['hosts'][0]
            # A plain uploaded filename is not a request for website access.
            if '://' not in value and not value.lower().startswith('www.') and host.rsplit('.', 1)[-1] in ('pdf','pptx','xlsx','txt','md','csv','json','py','js'):
                continue
            if host not in seen:
                seen.add(host)
                yield host
        except ValueError:
            continue


class ProtectionNotVerified(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__('OpenShell protection is not verified. Inspect this agent’s Policies tab before running a mission. No unprotected fallback was used.')


class PolicyControls:
    def protected_response(self, agent_id, session, prompt, owner, role=None, **kwargs):
        from studio import CREW_CATALOG
        profile = CREW_CATALOG[role] if role is not None else self.profile(owner) or {}
        if profile.get('protection') == 'openshell':
            prompt += ('\n\nFile access: use only your sandbox workspace and user uploads in inbox/. '
                       'Host-file approval, import by host path and write-back are not available. '
                       'Do not ask for file permissions in the website approval panel. '
                       'For external host files, ask the user to upload the file instead. '
                       'Earlier chat references to host-file grants describe a removed feature.')
        reader = getattr(self.adapter, 'policy_events', None)
        if profile.get('protection') != 'openshell' or not callable(reader):
            return self.adapter.respond(agent_id, session, prompt, **kwargs)
        def observe(agent):
            logs = reader(agent)
            self.remember_policy_denials(owner, logs, role)
            return logs
        started = time.time()
        with self.protection_activity.watch(owner, role, agent_id, observe):
            answer = self.adapter.respond(agent_id, session, prompt, **kwargs)
        # Personal replies (including hired handoffs) are prose. Preserve crew
        # JSON contracts and never infer a policy denial from HTTP/tool errors.
        hosts = self.protection_activity.denials_since(owner, role, started)
        if role is None and hosts and not kwargs.get('json_response'):
            text = str(answer) + '\n\nOpenShell blocked: ' + ', '.join(hosts) + '. Approve the required sites in this agent\'s OpenShell Policy panel before retrying.'
            from telemetry import Reply
            result = Reply(text, getattr(answer, 'metrics', {}))
            result.__dict__.update(getattr(answer, '__dict__', {}))
            result.policy_denials = hosts
            return result
        return answer

    def policy_profile(self, owner, role=None):
        """Resolve identity only; both kinds use the same policy engine and controls."""
        from studio import CREW_CATALOG, ROLES, Problem
        if role is None:
            profile = self.profile(owner)
            if not profile:
                raise Problem('Create a personal agent first.', 404)
            with self.db() as db:
                state=db.execute('SELECT deleting FROM agents WHERE id=?',(owner,)).fetchone()
            if not state:raise Problem('Agent not found.',404)
            if state['deleting']:raise Problem('This workspace is being deleted.',409)
            return profile
        if type(role) is not int or not 0 <= role < len(CREW_CATALOG):
            raise Problem('Choose a valid crew member.')
        if CREW_CATALOG[role].get('protection') != 'openshell':
            raise Problem('This crew member does not use OpenShell.', 404)
        with self.db() as db:
            account = db.execute('SELECT deleting FROM agents WHERE id=?', (owner,)).fetchone()
        if not account:
            raise Problem('Agent not found.', 404)
        if account['deleting']:
            raise Problem('This workspace is being deleted.', 409)
        return {**CREW_CATALOG[role], 'id':self.crew_native_id(owner, role),
                'name':ROLES[role][0], 'role':ROLES[role][1]}

    def saved_policy(self, owner, role=None):
        from research_http import RESEARCH_APPROVALS
        with self.db() as db:
            row = db.execute('SELECT * FROM agent_policies WHERE owner=? AND role=?',
                             (owner, -1 if role is None else role)).fetchone()
        # Defaults apply only until the user first edits this identity's policy.
        # An explicitly saved empty list is a revocation, never a missing setting.
        defaults = list(RESEARCH_APPROVALS) if role is not None else []
        return row, json.loads(row['approved']) if row else defaults

    def crew_policy_report(self, owner, role):
        if role is None:
            from studio import Problem
            raise Problem('Choose a valid crew member.')
        return self.policy_report(owner, role)

    def remember_policy_denials(self, owner, logs, role=None):
        """Retain verified destinations when native logs rotate or restart.

        Store only host/time evidence, never URLs or commands. The same policy
        row is removed by agent deletion; late observers cannot recreate it.
        """
        from research_http import RESEARCH_APPROVALS
        policy_role = -1 if role is None else role
        now = time.time()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            state = db.execute('SELECT reset_at,deleting FROM agents WHERE id=?',(owner,)).fetchone()
            if not state or state['deleting']:return []
            row = db.execute('SELECT denials FROM agent_policies WHERE owner=? AND role=?',(owner,policy_role)).fetchone()
            previous = json.loads(row['denials']) if row else []
            retained = {}
            for event in previous + logs:
                stamp = event.get('time')
                if (event.get('action') != 'deny' or event.get('reason','policy-denied') != 'policy-denied'
                        or type(stamp) not in (int,float) or not math.isfinite(stamp)
                        or not state['reset_at'] <= stamp <= now + 2):continue
                try:host = permission_rule(destination_permission(event.get('host')))['hosts'][0]
                except ValueError:continue
                if host not in retained or retained[host]['time'] < stamp:
                    retained[host] = {'host':host,'time':stamp,'action':'deny','reason':'policy-denied','source':'OpenShell policy log'}
            events = sorted(retained.values(),key=lambda event:event['time'],reverse=True)[:256]
            if events != previous:
                # Creating an observation row must preserve crew default grants.
                defaults = list(RESEARCH_APPROVALS) if role is not None else []
                db.execute('INSERT OR IGNORE INTO agent_policies(owner,role,approved) VALUES(?,?,?)',
                           (owner,policy_role,json.dumps(defaults)))
                db.execute('UPDATE agent_policies SET denials=? WHERE owner=? AND role=?',
                           (json.dumps(events),owner,policy_role))
            return events

    def policy_report(self, owner, role=None):
        profile = self.policy_profile(owner, role)
        row, approved = self.saved_policy(owner, role)
        # Verify legacy native rule names against the original saved representation.
        # A read only expands the display; the next explicit edit migrates storage.
        report = self.adapter.policy_status(profile['id'], profile.get('protection', 'standard'), approved)
        denials = self.remember_policy_denials(owner, report.get('logs', []), role)
        report['observedDenied'] = denials
        approved = individual_permissions(approved)
        report.update(agentId=profile['id'] if role is not None else owner, agentName=profile['name'], crewRole=role, history=json.loads(row['events']) if row else [],
                      updating=bool(row and row['updating']), requested=approved)
        with self.db() as db:
            state = db.execute('SELECT reset_at,deleting FROM agents WHERE id=?',(owner,)).fetchone()
            if not state or state['deleting']:
                from studio import Problem
                raise Problem('This agent is being removed. Refresh the studio.',409 if state else 404)
            reset_at = state['reset_at']
            report['preparing'] = bool(db.execute("SELECT 1 FROM jobs WHERE owner=? AND kind=? AND status IN ('queued','running','stopping')", (owner, 'prepare-agent' if role is None else 'prepare')).fetchone())
            report['busy'] = role is not None and bool(db.execute("SELECT 1 FROM jobs WHERE owner=? AND kind IN ('crew','crew-chat','prepare') AND status IN ('queued','running','waiting','stopping')", (owner,)).fetchone())
        # Candidates never grant access; assistant suggestions require explicit approval too.
        catalog = dict(report.get('catalog', CATALOG))
        with self.db() as db:
            jobs = db.execute("SELECT payload FROM jobs WHERE owner=? AND created>=? AND (CASE WHEN ? IS NULL THEN kind NOT IN ('crew','crew-chat','prepare','prepare-agent') ELSE kind='crew' OR (kind='crew-chat' AND (json_extract(payload,'$.crewRole')=? OR json_type(payload,'$.collaboration')='object')) END) ORDER BY created DESC LIMIT 30", (owner, reset_at, role, role)).fetchall()
        hosts = [e['host'] for e in denials]
        hosts += [e.get('host', '') for e in report.get('logs', []) if e.get('action') == 'deny' and e.get('reason', 'policy-denied') == 'policy-denied']
        for job in jobs:
            hosts.extend(prompt_hosts(json.loads(job['payload']).get('prompt', '')))
        for host in hosts:
            try:
                key = destination_permission(host)
                catalog[key] = permission_rule(key)
            except ValueError:
                pass
        from research_http import RESEARCH_APPROVALS
        from tech_radar import SOURCES
        radar_hosts=[source['host'] for source in SOURCES] if role is None and 'radar' in profile.get('skills',[]) else []
        report['recommended'] = list(RESEARCH_APPROVALS) if role is not None else ['host:'+host for host in radar_hosts]
        for key in approved + report['recommended']:
            catalog[key] = permission_rule(key)
        with self.db() as db:
            latest = db.execute("SELECT created,payload,result FROM jobs WHERE owner=? AND created>=? AND (CASE WHEN ? IS NULL THEN kind NOT IN ('crew','crew-chat','prepare','prepare-agent') ELSE kind='crew' OR (kind='crew-chat' AND (json_extract(payload,'$.crewRole')=? OR json_type(payload,'$.collaboration')='object')) END) ORDER BY created DESC LIMIT 1", (owner, reset_at, role, role)).fetchone()
        # Heartbeats run without a chat job. Their native denials must remain
        # visible even before the first summary is published, including after chat.
        since = latest['created'] if latest else None
        if radar_hosts:
            since = reset_at
        recent = [e for e in report.get('logs', []) if e.get('action') == 'deny' and since is not None and e.get('time') is not None and e['time'] >= since]
        report['recentDenied'] = [e for e in recent if e.get('reason', 'policy-denied') == 'policy-denied']
        report['connectionIssues'] = [e for e in recent if e.get('reason') in ('dns-failed', 'destination-blocked')]
        covered = {host for key in approved for host in permission_rule(key)['hosts']}
        # A follow-up can refer to a previous block without making another tool
        # call. Keep observed, unapproved denials across turns until board reset.
        pending = {e['host']: 'blocked' for e in denials if e['time'] >= reset_at and e['host'] not in covered}
        if latest:
            for host in prompt_hosts(json.loads(latest['payload']).get('prompt', '')):
                key = destination_permission(host)
                catalog[key] = permission_rule(key)
                if host not in covered:
                    pending.setdefault(host, 'requested')
        if latest:
            answer = json.loads(latest['result'] or '{}').get('answer', '')
            # Only approval-request paragraphs (and their following bullet list),
            # not ordinary citations or a bare HTTP error, propose destinations.
            approval_section = False
            for paragraph in re.split(r'\n\s*\n', answer):
                asks = bool(re.search(r'\b(?:please approve|needs? approval|requires? approval|approve these|approve .* in (?:the )?(?:OpenShell )?polic)', paragraph, re.I))
                bullet = paragraph.lstrip().startswith(('-', '*', '•'))
                approval_section = asks or (approval_section and bullet)
                if not approval_section:
                    continue
                for match in re.finditer(r'https?://[^\s<>"`\[\]()]+|`([a-zA-Z0-9.-]+)`|\*\*([a-zA-Z0-9.-]+)\*\*', paragraph, re.I):
                    try:
                        host = match.group(1) or match.group(2) or urlsplit(match.group()).hostname or ''
                        host = host.lower()
                        key = destination_permission(host)
                        catalog[key] = permission_rule(key)
                        if host not in covered:
                            pending.setdefault(host, 'suggested')
                    except ValueError:
                        pass
        # The feed hosts remain available as recommendations. Do not present
        # them as pending access before the agent actually requests them.
        report['pendingAccess'] = [{'host': host, 'reason': reason} for host, reason in pending.items()]
        report['catalog'] = catalog
        return report

    def crew_policy_change(self, owner, data):
        from studio import Problem
        role = data.get('role')
        if role is None:
            raise Problem('Choose a valid crew member.')
        self.policy_profile(owner, role)
        return self.policy_change(owner, data, role)

    def policy_change(self, owner, data, role=None):
        from studio import Problem
        profile = self.policy_profile(owner, role)
        policy_role = -1 if role is None else role
        if 'mode' in data:
            raise Problem('OpenShell protection is fixed when an agent is created.', 409)
        permission, allow = data.get('permission'), data.get('allow')
        retry = data.get('retry') is True
        batch = 'permissions' in data
        if batch:
            permissions = data['permissions']
            if (retry or 'permission' in data or allow is not True
                    or not isinstance(permissions, list) or not 1 <= len(permissions) <= 256
                    or any(not isinstance(key, str) for key in permissions)
                    or len(set(permissions)) != len(permissions)):
                raise Problem('Choose the requested permissions to approve together.')
        else:
            permissions = [] if retry else [permission]
            if not retry and (not isinstance(permission, str) or type(allow) is not bool):
                raise Problem('Choose an available public-read permission.')
        # Only website rules are accepted; reject retired file grants before native I/O.
        for key in permissions:
            try:
                permission_rule(key)
            except ValueError as error:
                raise Problem(str(error)) from None
        # Reject active work before an expensive native read; recheck under the write lock below.
        with self.db() as db:
            self.require_policy_editable(db, owner, role)
        snapshot = self.policy_report(owner, role)
        catalog = snapshot['catalog']
        if batch:
            scope = data.get('scope', 'pending')
            if scope not in ('pending', 'presets'):
                raise Problem('Choose a valid approval list.')
            if scope == 'presets':
                covered = {host for key in snapshot['requested'] for host in permission_rule(key)['hosts']}
                pending = {key for key, rule in catalog.items() if rule.get('hosts')
                           and (not key.startswith('host:') or key in snapshot.get('recommended', []))
                           and key not in snapshot['requested'] and not set(rule['hosts']) <= covered}
            else:
                pending = {'host:' + item['host'] for item in snapshot.get('pendingAccess', snapshot.get('recentDenied', []))}
            if any(key not in pending for key in permissions):
                raise Problem('The approval list changed. Refresh and review the pending requests again.', 409)
        for key in permissions:
            if key not in catalog:
                raise Problem('Choose an available permission.')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            self.require_policy_editable(db, owner, role)
            current = profile if role is not None else json.loads(db.execute('SELECT profile FROM agents WHERE id=?', (owner,)).fetchone()['profile'])
            if current.get('protection') != 'openshell':
                raise Problem('Turn on OpenShell for this agent first.', 409)
            db.execute('INSERT OR IGNORE INTO agent_policies (owner,role,approved) VALUES (?,?,?)', (owner, policy_role, json.dumps(snapshot['requested'])))
            row = db.execute('SELECT approved FROM agent_policies WHERE owner=? AND role=?', (owner, policy_role)).fetchone()
            approved = set(individual_permissions(json.loads(row['approved'])))
            if not retry:
                for key in individual_permissions(permissions):
                    approved.add(key) if allow else approved.discard(key)
            approved = sorted(approved)
            db.execute('UPDATE agent_policies SET approved=?,updating=1 WHERE owner=? AND role=?', (json.dumps(approved), owner, policy_role))
        try:
            if snapshot['status'] == 'awaiting-first-mission':
                if role is None:
                    self.ensure_agent(owner, profile)
                else:
                    self.initialize_workspace(owner)
                    self.adapter.register(profile['id'], self.workspace(owner, role), profile, profile['role'])
                    self.provisioned.add(profile['id'])
                self.adapter.policy_prepare(profile['id'])
            verified = self.adapter.policy_apply(profile['id'], approved)
            if verified.get('status') != 'applied':
                raise RuntimeError('OpenShell policy activation was not verified.')
            title = 'Policy synchronized' if retry else 'Permissions approved' if batch else 'Permission approved' if allow else 'Permission revoked'
            detail = 'Requested permissions' if retry else ', '.join(catalog[key]['title'] for key in permissions)
            detail += ' · OpenShell confirmed the loaded policy.'
            self.record_policy(owner, title, detail, role)
            return {'applied': True}
        except Exception:
            self.record_policy(owner, 'Policy update needs attention', 'The requested change is not confirmed. Refresh the live policy; no successful approval is claimed.', role)
            raise Problem('The policy change was not confirmed. Check host setup and refresh the live policy before retrying.', 503) from None
        finally:
            with self.db() as db:
                db.execute('UPDATE agent_policies SET updating=0 WHERE owner=? AND role=?', (owner, policy_role))

    def require_policy_editable(self, db, owner, role):
        from studio import Problem
        if role is None:
            self.require_available(db, owner)
            self.require_idle(db, owner)
        else:
            self.require_team_idle(db, owner)
            if owner in self.executing_owners:
                raise Problem('Wait for the current task to finish before changing access.', 409)

    def record_policy(self, owner, title, detail, role=None):
        policy_role = -1 if role is None else role
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM agents WHERE id=?', (owner,)).fetchone():
                return
            db.execute('INSERT OR IGNORE INTO agent_policies (owner,role) VALUES (?,?)', (owner, policy_role))
            row = db.execute('SELECT events FROM agent_policies WHERE owner=? AND role=?', (owner, policy_role)).fetchone()
            events = json.loads(row['events']) + [{'time': time.time(), 'title': title, 'detail': detail, 'source': 'Attendee control'}]
            db.execute('UPDATE agent_policies SET events=? WHERE owner=? AND role=?', (json.dumps(events[-40:]), owner, policy_role))

    def check_protected_run(self, owner, profile):
        if profile.get('protection') != 'openshell':
            return
        report = self.policy_report(owner)
        # Retry only a timed-out read, before any inference or tool side effects.
        if report['status'] == 'unavailable' and report.get('checkFailure') == 'timeout':
            report = self.policy_report(owner)
        if report['status'] == 'awaiting-first-mission':
            self.adapter.policy_prepare(profile['id'])
            self.adapter.policy_apply(profile['id'], report['requested'])
            report = self.policy_report(owner)
        elif report['status'] == 'needs-review':
            self.adapter.policy_apply(profile['id'], report['requested'])
            report = self.policy_report(owner)
        if report['status'] != 'applied':
            raise ProtectionNotVerified(report['status'])
        return report
