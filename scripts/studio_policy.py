"""Authenticated attendee controls for their own personal-agent policy."""
import json
import time
import re
from pathlib import Path
from urllib.parse import urlsplit

from agent_policy import CATALOG, destination_permission, permission_rule, individual_permissions


class ProtectionNotVerified(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__('OpenShell protection is not verified. Inspect this agent’s Policies tab before running a mission. No unprotected fallback was used.')


class PolicyControls:
    def policy_report(self, owner):
        from studio import Problem
        profile = self.profile(owner)
        if not profile:
            raise Problem('Create a personal agent to inspect its policy.', 404)
        with self.db() as db:
            row = db.execute('SELECT * FROM agent_policies WHERE owner=?', (owner,)).fetchone()
        approved = json.loads(row['approved']) if row else []
        # Verify legacy native rule names against the original saved representation.
        # A read only expands the display; the next explicit edit migrates storage.
        report = self.adapter.policy_status(profile['id'], profile.get('protection', 'standard'), approved)
        approved = individual_permissions(approved)
        report.update(agentId=owner, agentName=profile['name'], history=json.loads(row['events']) if row else [],
                      updating=bool(row and row['updating']), requested=approved)
        # Candidates never grant access; assistant suggestions require explicit approval too.
        catalog = dict(report.get('catalog', CATALOG))
        with self.db() as db:
            jobs = db.execute('SELECT payload FROM jobs WHERE owner=? ORDER BY created DESC LIMIT 30', (owner,)).fetchall()
        hosts = [e.get('host', '') for e in report.get('logs', []) if e.get('action') == 'deny' and e.get('reason', 'policy-denied') == 'policy-denied']
        for job in jobs:
            prompt = json.loads(job['payload']).get('prompt', '')
            for match in re.finditer(r'(?:https?://|www\.)[^\s<>"\\]+', prompt, re.I):
                value = match.group().rstrip('.,;!?)')
                hosts.append(urlsplit(value if '://' in value else 'https://' + value).hostname or '')
        for host in hosts:
            try:
                key = destination_permission(host)
                catalog[key] = permission_rule(key)
            except ValueError:
                pass
        for key in approved:
            catalog[key] = permission_rule(key)
        with self.db() as db:
            latest = db.execute("SELECT created,payload,result FROM jobs WHERE owner=? AND kind NOT IN ('crew', 'crew-chat', 'prepare') ORDER BY created DESC LIMIT 1", (owner,)).fetchone()
        recent = [e for e in report.get('logs', []) if e.get('action') == 'deny' and latest and e.get('time') is not None and e['time'] >= latest['created']]
        report['recentDenied'] = [e for e in recent if e.get('reason', 'policy-denied') == 'policy-denied']
        report['connectionIssues'] = [e for e in recent if e.get('reason') in ('dns-failed', 'destination-blocked')]
        covered = {host for key in approved for host in permission_rule(key)['hosts']}
        pending = {e['host']: 'blocked' for e in report['recentDenied'] if e['host'] not in covered}
        if latest:
            prompt = json.loads(latest['payload']).get('prompt', '').replace('\\.', '.')
            for match in re.finditer(r'(?:https?://|www\.)[^\s<>"\\]+', prompt, re.I):
                value = match.group().rstrip('.,;!?)')
                try:
                    host = urlsplit(value if '://' in value else 'https://' + value).hostname or ''
                    key = destination_permission(host)
                    catalog[key] = permission_rule(key)
                    if host not in covered:
                        pending.setdefault(host, 'requested')
                except ValueError:
                    pass
        if latest:
            answer = json.loads(latest['result'] or '{}').get('answer', '')
            # Only approval-request paragraphs (and their following bullet list),
            # not ordinary citations or a bare HTTP error, propose destinations.
            approval_section = False
            for paragraph in re.split(r'\n\s*\n', answer):
                asks = bool(re.search(r'\b(?:please approve|needs? approval|requires? approval|approve these|approve .* in (?:the )?polic)', paragraph, re.I))
                bullet = paragraph.lstrip().startswith(('-', '*', '•'))
                approval_section = asks or (approval_section and bullet)
                if not approval_section:
                    continue
                for match in re.finditer(r'https?://[^\s<>"`\[\]()]+', paragraph, re.I):
                    try:
                        host = urlsplit(match.group()).hostname or ''
                        key = destination_permission(host)
                        catalog[key] = permission_rule(key)
                        if host not in covered:
                            pending.setdefault(host, 'suggested')
                    except ValueError:
                        pass
        report['pendingAccess'] = [{'host': host, 'reason': reason} for host, reason in pending.items()]
        from file_access import requested_files, requested_directories, proposed_files, file_rule, request_issue
        file_pending = []
        report['fileIssues'] = []
        unsupported = requested_directories(json.loads(latest['payload']).get('prompt', '')) if latest else []
        report['unsupportedFolders'] = unsupported
        if latest:
            prompt = json.loads(latest['payload']).get('prompt', '')
            direct = requested_files(prompt)
            answer = json.loads(latest['result'] or '{}').get('answer', '')
            suggested = proposed_files(prompt, answer) if not direct else []
            for path in sorted(set(direct + suggested)):
                if path in unsupported:
                    continue
                issue = request_issue(path, prompt)
                if issue:
                    report['fileIssues'].append(issue)
                    continue
                missing = False
                try:
                    Path(path).lstat()
                except FileNotFoundError:
                    missing = True
                except OSError:
                    pass  # Keep other validation errors visible below.
                for access in (('write',) if missing else ('read', 'write')):
                    key = 'file:' + access + ':' + path
                    catalog[key] = file_rule(key)
                    if path in suggested:
                        catalog[key]['suggested'] = True
                    if key not in approved and 'file:write:' + path not in approved:
                        file_pending.append(key)
        from file_access import checked_path
        for key, rule in catalog.items():
            if rule.get('kind') == 'file':
                try:
                    checked_path(rule['path'], allow_missing=rule['access'] == 'write')
                except (ValueError, OSError) as error:
                    rule['unavailableReason'] = str(error)
        report['pendingFiles'] = file_pending
        report['catalog'] = catalog
        return report

    def policy_change(self, owner, data):
        from studio import Problem
        profile = self.profile(owner)
        if not profile:
            raise Problem('Create a personal agent first.', 404)
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
        # Validate every file before native discovery or changing saved approvals.
        if not retry and allow:
            from file_access import checked_path, file_rule
            for key in permissions:
                if key.startswith('file:'):
                    try:
                        rule = file_rule(key)
                        checked_path(rule['path'], allow_missing=rule['access'] == 'write')
                    except (ValueError, OSError) as error:
                        raise Problem(str(error)) from None
        # Reject active work before an expensive native read; recheck under the write lock below.
        with self.db() as db:
            self.require_available(db, owner)
            self.require_idle(db, owner)
        snapshot = self.policy_report(owner)
        catalog = snapshot['catalog']
        if batch:
            pending = {'host:' + item['host'] for item in snapshot.get('pendingAccess', snapshot.get('recentDenied', []))}
            pending.update(snapshot.get('pendingFiles', []))
            if any(key not in pending for key in permissions):
                raise Problem('The approval list changed. Refresh and review the pending requests again.', 409)
        for key in permissions:
            if key not in catalog:
                raise Problem('Choose an available permission.')
            rule = catalog[key]
            if allow and rule.get('unavailableReason'):
                raise Problem(rule['unavailableReason'])
            if allow and key.startswith('file:'):
                if rule['path'] in snapshot.get('unsupportedFolders', []):
                    raise Problem('Host folder creation is not supported by file approvals. Create the folder inside the agent workspace instead.')
                from file_access import checked_path
                try:
                    checked_path(rule['path'], allow_missing=rule['access'] == 'write')
                except (ValueError, OSError) as error:
                    raise Problem(str(error)) from None
        # Read/write already includes read; do not store both alternatives from one click.
        if batch:
            permissions = [key for key in permissions if not (key.startswith('file:read:') and 'file:write:' + key.split(':', 2)[2] in permissions)]
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            self.require_available(db, owner)
            self.require_idle(db, owner)
            current = json.loads(db.execute('SELECT profile FROM agents WHERE id=?', (owner,)).fetchone()['profile'])
            if current.get('protection') != 'openshell':
                raise Problem('Turn on OpenShell for this agent first.', 409)
            db.execute('INSERT OR IGNORE INTO agent_policies (owner) VALUES (?)', (owner,))
            row = db.execute('SELECT approved FROM agent_policies WHERE owner=?', (owner,)).fetchone()
            approved = set(individual_permissions(json.loads(row['approved'])))
            if not retry:
                for key in individual_permissions(permissions):
                    approved.add(key) if allow else approved.discard(key)
            approved = sorted(approved)
            db.execute('UPDATE agent_policies SET approved=?,updating=1 WHERE owner=?', (json.dumps(approved), owner))
        try:
            if snapshot['status'] == 'awaiting-first-mission':
                self.ensure_agent(owner, profile)
                self.adapter.policy_prepare(profile['id'])
            verified = self.adapter.policy_apply(profile['id'], approved)
            if verified.get('status') != 'applied':
                raise RuntimeError('OpenShell policy activation was not verified.')
            title = 'Policy synchronized' if retry else 'Permissions approved' if batch else 'Permission approved' if allow else 'Permission revoked'
            detail = 'Requested permissions' if retry else ', '.join(catalog[key]['title'] for key in permissions)
            detail += (' · Host-file grants saved; protected runtime verified. Transfers use protected copies.' if any(key.startswith('file:') for key in permissions) else ' · OpenShell confirmed the loaded policy.')
            self.record_policy(owner, title, detail)
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
