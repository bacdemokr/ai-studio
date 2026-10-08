"""Prepare a demo without running inference; use the same serial worker as missions."""
import hashlib
import json
import secrets
import time


class DemoReadiness:
    def demo_preparation(self, owner):
        with self.db() as db:
            row = db.execute("SELECT * FROM jobs WHERE owner=? AND kind='prepare' ORDER BY created DESC LIMIT 1", (owner,)).fetchone()
        return {**self.public_job(row), 'valid':json.loads(row['payload']).get('bootId') == self.boot_id} if row else None

    def require_event_crew_idle(self, db, owner):
        from studio import Problem
        self.require_bac_not_resetting(db, owner)
        if not db.execute('SELECT 1 FROM agents WHERE id=? AND deleting=0', (owner,)).fetchone():
            raise Problem('This workspace is unavailable or being deleted.', 409)
        if db.execute('SELECT 1 FROM agent_policies WHERE owner=? AND role>=0 AND updating=1', (owner,)).fetchone():
            raise Problem('This agent’s policy is being updated. Please wait.', 409)
        if db.execute("SELECT 1 FROM jobs WHERE owner=? AND kind IN ('crew','crew-chat','prepare') AND status IN ('queued','running','waiting','stopping')", (owner,)).fetchone():
            raise Problem('The BaC crew is busy. Finish its current work before preparing or starting another event.', 409)

    def prepared_event(self, db, owner, preparation_id, roles):
        from studio import Problem
        row = db.execute("SELECT * FROM jobs WHERE id=? AND owner=? AND kind='prepare'", (preparation_id, owner)).fetchone()
        if not row or row['status'] != 'done':
            raise Problem('Prepare the selected BaC crew before starting the event.', 409)
        payload = json.loads(row['payload'])
        if payload.get('bootId') != self.boot_id or not set(roles).issubset(payload.get('enabledRoles', [])):
            raise Problem('Preparation changed or expired. Check the selected crew again.', 409)
        return payload

    def prepare_demo(self, owner, data):
        from studio import Problem
        background = data.get('background') is True
        selected = data.get('enabledRoles', [0, 1, 2, 3])
        if not isinstance(selected, list) or not selected or 0 not in selected or any(type(i) is not int or not 0 <= i <= 3 for i in selected) or len(set(selected)) != len(selected):
            raise Problem('Choose the BaC crew, including Riley.')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute("SELECT * FROM jobs WHERE owner=? AND kind='prepare' ORDER BY created DESC LIMIT 1", (owner,)).fetchone()
            # Multiple tabs and polling share one attempt per server boot. A failed
            # warmup stays visible for an explicit retry instead of looping.
            if background and previous:
                prior = json.loads(previous['payload'])
                if prior.get('bootId') == self.boot_id and set(selected).issubset(prior.get('enabledRoles', [])):
                    return {'id': previous['id'], 'cached': True}
            if previous and previous['status'] in ('queued', 'running'):
                pending = json.loads(previous['payload'])
                if pending.get('background') and pending.get('bootId') == self.boot_id and set(selected).issubset(pending['enabledRoles']):
                    return {'id': previous['id'], 'cached': True}
            self.require_event_crew_idle(db, owner)
            roster = self.crew_roster(db, owner, {}, True)
            # Startup warms the built-in crew only. Capture personal guests later,
            # when the user opens the event form and chooses the current roster.
            guests = {} if background else self.capture_roundtable(db, owner)
            policies = [dict(row) for row in db.execute('SELECT owner,role,approved,events,updating FROM agent_policies WHERE owner IN (SELECT id FROM agents WHERE participant=(SELECT participant FROM agents WHERE id=?)) ORDER BY owner,role', (owner,))]
            signature = hashlib.sha256(json.dumps([self.boot_id, sorted(selected), roster, guests, policies], sort_keys=True).encode()).hexdigest()
            expected = {roster[i]['id'] for i in selected}
            if expected.issubset(self.provisioned) and previous and previous['status'] == 'done' and time.time()-previous['updated'] < 180 and json.loads(previous['payload']).get('signature') == signature:
                return {'id': previous['id'], 'cached': True}
            payload = {'roster': roster, 'roundtable': guests, 'enabledRoles': selected, 'signature': signature, 'bootId':self.boot_id,
                       'background':background, 'checks':[]}
            job_id = secrets.token_hex(12)
            now = time.time()
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?)', (job_id, owner, 'prepare', 'queued', json.dumps(payload), '{}', '[]', now, now, now))
        self.signal.set()
        return {'id': job_id, 'cached': False}

    def prepare_demo_run(self, row, payload):
        owner, job_id = row['owner'], row['id']
        targets = [(i, payload['roster'][i]) for i in payload['enabledRoles']]
        # Optional reactions never provision or probe personal runtimes here.
        # Their protection is verified immediately before the actual reaction.
        for role, member in targets:
            if self.stop_checkpoint(job_id):
                return
            check = {'name': member['name'], 'key': member.get('key'), 'required':role is not None, 'status': 'preparing'}
            payload['checks'].append(check)
            self.event(job_id, 'Preparing '+member['name'], 'Preparing runtime and checking saved access. No model request is sent.', payload=json.dumps(payload))
            try:
                report = self.prepare_builtin_crew(owner, role, member)
                if report:
                    check['protection'] = report
                check.update(status='ready')
            except Exception as error:
                import logging
                logging.exception('Demo preparation failed for %s', member['id'])
                check.update(status='error', detail='Runtime preparation failed. Check the host runtime and try again.')
        failed = [c for c in payload['checks'] if c['status'] == 'error']
        result = {'answer': 'BaC crew ready. Optional guests are checked before their reactions. No model inference was run.'} if not failed else {'error': 'BaC crew preparation needs attention: '+', '.join(c['name'] for c in failed)}
        self.event(job_id, 'Demo preparation finished', result.get('error') or result['answer'], status='error' if failed else 'done', result=json.dumps(result), payload=json.dumps(payload))
