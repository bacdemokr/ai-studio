"""Old event jobs must not reappear or restart after upgrading."""
import json
import tempfile
import time
import unittest
from test_studio import Studio, Adapter, Problem


class RetiredEventFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.adapter = Adapter()
        self.app = Studio(self.temp.name, self.adapter, start_worker=False)
        self.owner = self.app.session()[0]['id']

    def legacy_job(self, kind='crew', status='queued'):
        now = time.time()
        with self.app.db() as db:
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?)',
                       ('legacy-'+kind, self.owner, kind, status,
                        json.dumps({'brief':{'schema':2,'city':'Zurich'}}), '{}', '[]', now, now, now))

    def test_direct_legacy_requests_are_rejected_before_runtime_work(self):
        for kind in ('crew', 'prepare'):
            with self.assertRaises(Problem) as caught:
                self.app.enqueue(self.owner, {'kind':kind, 'preset':True})
            self.assertEqual(caught.exception.status, 410)
        self.assertEqual(self.adapter.calls, [])

    def test_saved_event_is_not_in_current_state(self):
        self.legacy_job(status='done')
        self.assertEqual(self.app.state(self.owner)['jobs'], [])

    def test_upgrade_cancels_legacy_queue_preserving_files(self):
        for kind in ('crew', 'prepare'):
            self.legacy_job(kind)
        self.app.initialize_workspace(self.owner)
        saved = self.app.workspace(self.owner) / 'artifacts/saved.html'
        saved.write_text('<h1>Saved result</h1>')
        upgraded = Studio(self.temp.name, self.adapter, start_worker=False)
        with upgraded.db() as db:
            statuses = [row['status'] for row in db.execute("SELECT status FROM jobs WHERE id LIKE 'legacy-%'")]
        self.assertEqual(statuses, ['cancelled', 'cancelled'])
        self.assertEqual(saved.read_text(), '<h1>Saved result</h1>')
        self.assertFalse(hasattr(upgraded, 'crew'))
        self.assertFalse(hasattr(upgraded, 'prepare_demo_run'))
