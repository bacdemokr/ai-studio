"""App-open warmup uses actual crew preparation without inference or new grants."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts'), str(Path(__file__).parent)]
from studio import Studio, Problem
from test_hiring_preparation import ProtectedAdapter


class CrewStartupTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.adapter = ProtectedAdapter()
        self.studio = Studio(folder.name, self.adapter, start_worker=False)
        self.personal = self.studio.session()[0]['id']
        self.owner = self.studio.crew_owner(self.personal, 'event-brief')

    def warmup(self):
        return self.studio.prepare_demo(self.owner, {'background': True})

    def run_next(self):
        self.studio.execute(self.studio.next_job())


    def test_background_prepares_event_crew_without_inference_or_grants(self):
        job = self.warmup()
        self.run_next()
        prepared = self.studio.demo_preparation(self.owner)
        self.assertEqual(prepared['id'], job['id'])
        self.assertTrue(prepared['valid'])
        self.assertEqual(prepared['status'], 'done')
        self.assertEqual([c['status'] for c in prepared['payload']['checks']], ['ready']*4)
        self.assertEqual(self.adapter.calls, [])
        for role in range(4):
            agent = prepared['payload']['roster'][role]['id']
            if agent in self.adapter.permissions:
                self.assertEqual(self.adapter.permissions[agent], self.studio.saved_policy(self.owner, role)[1])
        self.assertEqual(prepared['payload']['roundtable'], {})
        plan = self.studio.crew_owner(self.personal, 'plan')
        self.assertIsNone(self.studio.demo_preparation(plan))

    def test_concurrent_tabs_and_form_share_pending_then_finished_warmup(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = [j['id'] for j in pool.map(lambda _: self.warmup(), range(4))]
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(self.studio.prepare_demo(self.owner, {})['id'], ids[0])
        self.run_next()
        self.assertEqual(self.warmup()['id'], ids[0])
        self.assertIsNone(self.studio.next_job())

    def test_model_invalidation_and_server_restart_require_new_preparation(self):
        self.warmup(); self.run_next()
        prepared = self.studio.demo_preparation(self.owner)
        self.studio.provisioned.discard(prepared['payload']['roster'][1]['id'])
        self.assertFalse(self.studio.demo_preparation(self.owner)['valid'])
        with self.studio.db() as db, self.assertRaises(Problem):
            self.studio.prepared_event(db, self.owner, prepared['id'], [0,1])
        retry = self.warmup(); self.assertNotEqual(retry['id'], prepared['id'])
        self.run_next()
        self.studio.boot_id = 'new-boot'
        self.assertFalse(self.studio.demo_preparation(self.owner)['valid'])
        self.assertNotEqual(self.warmup()['id'], retry['id'])

    def test_failed_protection_stays_unready_and_only_explicit_retry_recovers(self):
        job = self.warmup()
        with patch.object(self.adapter, 'policy_prepare', side_effect=RuntimeError('Unavailable')):
            self.run_next()
        prepared = self.studio.demo_preparation(self.owner)
        self.assertEqual(prepared['status'], 'error')
        for role in (1,):
            self.assertNotIn(prepared['payload']['roster'][role]['id'], self.studio.provisioned)
        self.assertEqual(self.warmup()['id'], job['id'])
        self.assertIsNone(self.studio.next_job())
        retry = self.studio.prepare_demo(self.owner, {})
        self.assertNotEqual(retry['id'], job['id'])
        self.run_next()
        self.assertEqual(self.studio.demo_preparation(self.owner)['status'], 'done')
        self.assertEqual(self.adapter.calls, [])

    def test_reset_rewarms_without_making_empty_scenario_resettable(self):
        first = self.warmup()
        self.run_next()
        self.studio.reset_crew_chats(self.owner, reset_event=True)
        self.assertIsNone(self.studio.demo_preparation(self.owner))
        second = self.warmup()
        self.assertNotEqual(first['id'], second['id'])
        self.run_next()
        status = next(s for s in self.studio.scenario_status(self.personal) if s['id'] == 'event-brief')
        self.assertFalse(status['hasWork'])
        self.assertFalse(status['busy'])
        self.assertTrue(self.studio.demo_preparation(self.owner)['valid'])
        # New files must still enable Reset even when the newest job is a warmup.
        artifact = self.studio.workspace(self.owner, 3) / 'artifacts' / 'report.md'
        artifact.write_text('Saved result')
        self.assertTrue(next(s for s in self.studio.scenario_status(self.personal) if s['id'] == 'event-brief')['hasWork'])


if __name__ == '__main__':
    unittest.main()
