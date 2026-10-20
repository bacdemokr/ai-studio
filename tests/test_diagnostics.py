"""Support export privacy, failure tracing and bounded persistence without inference."""
from concurrent.futures import ThreadPoolExecutor
import http.client
import json
import os
from pathlib import Path
import secrets
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from test_studio import Studio, Adapter
from diagnostics import Diagnostics, REQUEST, cause
from serve import create_server

CANARY = 'DO_NOT_EXPORT_SECRET_prompt_cookie_document_123'


class DiagnosticStorageTests(unittest.TestCase):
    def test_diagnostic_reads_do_not_break_concurrent_job_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            app = Studio(Path(folder)/'studio', Adapter(), start_worker=False)
            owner = app.session()[0]['id']
            barrier = threading.Barrier(6)
            def operation(index):
                barrier.wait(timeout=5)
                for _ in range(100):
                    if index < 3:
                        with app.db() as db:
                            db.execute('BEGIN IMMEDIATE')
                            db.execute('UPDATE participants SET last_seen=? WHERE id=?', (time.time(), owner))
                    else:
                        try:
                            with app.diagnostics.database(app) as db:
                                db.execute('SELECT count(*) FROM jobs').fetchone()
                        except sqlite3.OperationalError as error:
                            # Support exports may yield to a busy writer. They must
                            # never break the connection used by the job worker.
                            if 'locked' not in str(error) and 'busy' not in str(error):
                                raise
            with ThreadPoolExecutor(max_workers=6) as pool:
                list(pool.map(operation, range(6)))
            with app.diagnostics.database(app) as db:
                with self.assertRaises(sqlite3.OperationalError):
                    db.execute('DELETE FROM participants')
            with app.db() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM participants').fetchone()[0], 1)

    def test_diagnostic_reads_never_create_missing_database(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'missing.sqlite'
            with self.assertRaises(sqlite3.OperationalError):
                with Diagnostics.database(SimpleNamespace(db_path=path)):
                    self.fail('Missing database must not be created')
            self.assertFalse(path.exists())

    def test_rotation_permissions_and_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Diagnostics(folder)
            store.MAX_BYTES = 1300
            person = secrets.token_hex(12)
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda _:store.emit('job.progress', participant=person, job=secrets.token_hex(12)), range(80)))
            files = list((Path(folder)/'logs').glob('diagnostics.jsonl*'))
            self.assertLessEqual(len(files), 4)
            for path in files:
                self.assertLessEqual(path.stat().st_size, 1300)
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                for line in path.read_text().splitlines():
                    record = json.loads(line)
                    self.assertIn('version', record)
                    self.assertIn('commit', record)
                    self.assertIn('build', record)
            recovered = Diagnostics(folder).report(person)
            self.assertTrue(any(e['event']=='job.progress' for e in recovered['events']))

    def test_allowlist_and_storage_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Diagnostics(folder)
            person = secrets.token_hex(12)
            with patch('diagnostics.os.open', side_effect=PermissionError(CANARY)):
                store.emit('request.finished', participant=person, route='file?path='+CANARY,
                           error=RuntimeError(CANARY), apiKey=CANARY, prompt=CANARY, cookie=CANARY,
                           model='sk-'+CANARY, elapsedMs=float('nan'))
            report = store.report(person)
            self.assertEqual(report['storage'], 'memory-only')
            self.assertNotIn(CANARY, json.dumps(report))
            self.assertEqual(report['events'][-1]['route'], 'file')

    def test_runtime_and_export_limits(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Diagnostics(folder)
            store.observe_runtime({'gateway':False, 'gatewayState':'unavailable', 'error':CANARY,
                'modelConnections':{'connections':{'api':{'ready':True, 'model':'example/model',
                    'apiKey':CANARY,'baseUrl':'https://private.invalid/'+CANARY}}}})
            person = secrets.token_hex(12)
            for _ in range(420):store.emit('job.progress', participant=person)
            report = store.report(person)
            self.assertLessEqual(len(report['events']), 80)
            self.assertGreater(report['eventsOmitted'], 0)
            self.assertLess(len(json.dumps(report)), 64000)
            self.assertNotIn(CANARY, json.dumps(report))
            self.assertEqual(report['runtime']['connections']['api']['model'], 'example/model')
            self.assertLessEqual(len(store.report(person, full=True)['events']), 400)

    def test_policy_classification_does_not_blame_openshell_for_search_quota(self):
        self.assertEqual(cause('Search HTTP 403 forbidden'), 'access-denied')
        self.assertEqual(cause('Search quota reached; not an OpenShell error'), 'rate-limit')
        self.assertEqual(cause('OpenShell policy denied the request'), 'reported-openshell-denial')

    def test_startup_warmup_is_included_without_private_command_output(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Diagnostics(folder)
            store.observe_runtime({'openshellWarmup': {'state': 'ready', 'elapsedMs': 14000,
                                                       'commandOutput': CANARY}})
            store.emit('openshell.warmup', status='done', elapsedMs=14000, commandOutput=CANARY)
            report = store.report(secrets.token_hex(12))
            self.assertEqual(report['runtime']['openshellWarmup'], {'state': 'ready', 'elapsedMs': 14000})
            self.assertTrue(any(e['event'] == 'openshell.warmup' and e['status'] == 'done' for e in report['events']))
            self.assertNotIn(CANARY, json.dumps(report))


class DiagnosticHTTPTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.app = Studio(folder.name, Adapter(), start_worker=False)
        self.person = self.app.session()[0]
        self.other = self.app.session()[0]
        self.server = create_server('127.0.0.1', 0, self.app)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)

    def request(self, route='diagnostics', body=None, person=None, **overrides):
        person = person or self.person
        headers = {'Host':'192.168.1.20:8080', 'Origin':'http://192.168.1.20:8080',
                   'Cookie':'bac_session='+person['token'], 'X-BaC-CSRF':person['csrf'],
                   'Content-Type':'application/json'}
        headers.update(overrides)
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        connection.request('GET' if body is None else 'POST', '/api/'+route,
                           None if body is None else json.dumps(body), headers)
        response = connection.getresponse();value = json.loads(response.read());metadata = dict(response.getheaders())
        connection.close()
        return response.status, value, metadata

    def test_auth_and_session_isolation_even_after_job_reset(self):
        self.assertEqual(self.request(Cookie='')[0], 401)
        self.assertEqual(self.request(Host='evil.example')[0], 403)
        own, other = secrets.token_hex(12), secrets.token_hex(12)
        self.app.diagnostics.emit('job.progress', participant=self.person['id'], job=own)
        self.app.diagnostics.emit('job.progress', participant=self.other['id'], job=other)
        self.app.diagnostics.emit('request.finished', participant=self.other['id'], route='jobs')
        status, report, _ = self.request()
        self.assertEqual(status, 200)
        serialized = json.dumps(report)
        self.assertIn(own, serialized);self.assertNotIn(other, serialized)
        self.assertNotIn(self.person['id'], serialized)
        self.assertNotIn(self.person['token'], serialized)
        self.assertNotIn(self.person['csrf'], serialized)

    def test_verified_policy_denials_are_recorded_once_without_hostnames(self):
        record = {'host':'example.com', 'time':time.time(), 'action':'deny', 'reason':'policy-denied'}
        self.app.remember_policy_denials(self.person['id'], [record])
        self.app.remember_policy_denials(self.person['id'], [record])
        report = self.request()[1]
        self.assertEqual(len([e for e in report['events'] if e['event']=='policy.denial-observed']),1)
        self.assertNotIn('example.com',json.dumps(report))

    def test_busy_database_does_not_prevent_support_export(self):
        with patch.object(self.app.diagnostics, 'database', side_effect=OSError(CANARY)):
            report = self.request()[1]
        self.assertEqual(report['workload'], {'available':False})
        self.assertNotIn(CANARY, json.dumps(report))

    def test_unexpected_get_and_post_errors_have_correlated_safe_frames(self):
        for route, body, target in [('runtime',None,'runtime_status'), ('onboard',{},'onboard')]:
            with self.subTest(route=route), patch.object(self.app, target, side_effect=RuntimeError('timeout '+CANARY)):
                status, result, headers = self.request(route, body)
            self.assertEqual(status, 500)
            self.assertEqual(result['requestId'], headers['X-BaC-Request-ID'])
            for _ in range(30):
                report = self.request()[1]
                found = [r for r in report['events'] if r.get('requestId')==result['requestId']]
                if found:break
                time.sleep(.01)
            self.assertTrue(found)
            self.assertEqual(found[-1]['error']['category'], 'timeout')
            self.assertTrue(found[-1]['error']['frames'])
            self.assertNotIn(CANARY, json.dumps(report))
            self.assertNotIn(str(Path.home()), json.dumps(report))

    def test_job_progress_failure_and_request_link_survive_reset(self):
        job = secrets.token_hex(12)
        with self.app.db() as db:
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?)',
                (job,self.person['id'],'chat','running',json.dumps({'prompt':CANARY}), '{}','[]',time.time(),time.time(),0))
        token = REQUEST.set({'requestId':'abcdef1234567890', 'participant':self.person['id']})
        try:self.app.diagnostics.job(self.app,job,'job.queued')
        finally:REQUEST.reset(token)
        self.app.event(job, 'Review '+CANARY, 'Missing required handoff '+CANARY)
        with self.app.db() as db:row = dict(db.execute('SELECT * FROM jobs WHERE id=?',(job,)).fetchone())
        with patch.object(self.app,'_execute',side_effect=RuntimeError('context limit '+CANARY)), patch.object(self.app,'stop_checkpoint',return_value=False):
            with self.assertRaises(RuntimeError):self.app.execute(row)
        with self.app.db() as db:db.execute('DELETE FROM jobs WHERE id=?',(job,))
        report = self.request()[1]
        own = [e for e in report['events'] if e.get('job')==job]
        self.assertEqual(own[0]['requestId'],'abcdef1234567890')
        self.assertTrue(any(e.get('category')=='missing-handoff' for e in own))
        self.assertTrue(any(e.get('error',{}).get('category')=='context-limit' for e in own))
        self.assertNotIn(CANARY,json.dumps(report))


if __name__ == '__main__':unittest.main()
