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
        self.owner = self.studio.session()[0]['id']

    def warmup(self):
        return self.studio.prepare_demo(self.owner, {'background': True})

    def run_next(self):
        self.studio.execute(self.studio.next_job())

    def test_without_model_or_hired_agent_prepares_dylan_and_never_infers(self):
        with patch.object(self.adapter, 'status', return_value={'gateway': True, 'ready': False, 'model': False}):
            self.warmup()
            self.assertTrue(self.studio.crew_policy_report(self.owner, 1)['preparing'])
            self.run_next()
        self.assertEqual(self.studio.demo_preparation(self.owner)['status'], 'done')
        self.assertEqual(self.adapter.prepares, ['bac-' + self.owner + '-r1'])
        self.assertEqual(self.adapter.calls, [])
        self.assertEqual(self.studio.state(self.owner)['jobs'], [])
        self.assertFalse(self.studio.crew_policy_report(self.owner, 1)['preparing'])

    def test_tabs_and_event_form_join_existing_warmup(self):
        with ThreadPoolExecutor(max_workers=3) as pool:
            ids = list(pool.map(lambda _: self.warmup()['id'], range(3)))
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(self.studio.prepare_demo(self.owner, {})['id'], ids[0])
        self.run_next()
        self.assertEqual(self.warmup()['id'], ids[0])
        self.assertIsNone(self.studio.next_job())

    def test_failed_warmup_does_not_loop_and_manual_retry_recovers(self):
        first = self.warmup()['id']
        with patch.object(self.adapter, 'policy_prepare', side_effect=RuntimeError('offline')):
            self.run_next()
        self.assertEqual(self.studio.demo_preparation(self.owner)['status'], 'error')
        self.assertEqual(self.warmup()['id'], first)
        self.assertIsNone(self.studio.next_job())
        self.assertNotEqual(self.studio.prepare_demo(self.owner, {})['id'], first)
        self.run_next()
        self.assertEqual(self.studio.demo_preparation(self.owner)['status'], 'done')

    def test_a_previous_casey_only_check_does_not_skip_dylan(self):
        partial = self.studio.prepare_demo(self.owner, {'enabledRoles': [0]})
        self.run_next()
        self.assertNotEqual(self.warmup()['id'], partial['id'])
        self.run_next()
        self.assertEqual(self.adapter.prepares, ['bac-' + self.owner + '-r1'])

    def test_server_restart_rechecks_without_restoring_revoked_access(self):
        with self.studio.db() as db:
            db.execute('INSERT INTO agent_policies(owner,role,approved) VALUES (?,1,?)', (self.owner, '[]'))
        first = self.warmup()['id']
        self.run_next()
        self.studio = Studio(self.studio.directory, self.adapter, start_worker=False, recover=True)
        self.assertNotEqual(self.warmup()['id'], first)
        self.run_next()
        self.assertEqual(self.adapter.permissions['bac-' + self.owner + '-r1'], [])
        self.assertEqual(self.adapter.calls, [])

    def test_policy_change_and_deletion_fences(self):
        self.warmup()
        with self.studio.db() as db:
            db.execute('INSERT INTO agent_policies(owner,role,updating) VALUES (?,1,1)', (self.owner,))
        self.assertIsNone(self.studio.next_job())
        with self.studio.db() as db:
            db.execute('UPDATE agent_policies SET updating=0')
        self.run_next()
        other = self.studio.session()[0]['id']
        with self.studio.db() as db:
            db.execute('UPDATE agents SET deleting=1 WHERE id=?', (other,))
        with self.assertRaises(Problem):
            self.studio.prepare_demo(other, {'background': True})

    def test_foreground_work_takes_priority_and_new_guests_can_join(self):
        self.warmup()
        profile = dict(name='Scout', persona='analyst', skills=['weather'], protection='standard')
        self.studio.onboard(self.owner, profile)
        guest = self.studio.add_agent(self.owner, {**profile, 'name': 'Pixel'})['agentId']
        chat = self.studio.enqueue(guest, {'prompt': 'Hello'})
        row = self.studio.next_job()
        self.assertEqual(row['id'], chat['id'])
        self.studio.execute(row)
        self.run_next()
        prepared = self.studio.demo_preparation(self.owner)['payload']
        self.assertEqual(prepared['roundtable'], {})
        with self.studio.db() as db:
            guests = self.studio.capture_roundtable(db, self.owner, prepared, [guest])
        self.assertEqual([m['key'] for m in guests['members']], [guest])

    def test_hidden_preparation_does_not_consume_user_mission_quota(self):
        profile = dict(name='Scout', persona='guide', skills=['weather'])
        self.studio.onboard(self.owner, profile)
        owners = [self.owner] + [self.studio.add_agent(self.owner, {**profile, 'name': name})['agentId'] for name in ('Pixel', 'Orbit')]
        for owner in owners:
            self.studio.prepare_demo(owner, {'background': True})
        for owner in owners:
            self.studio.enqueue(owner, {'prompt': 'Hello'})
        with self.assertRaisesRegex(Problem, 'three pending missions'):
            self.studio.enqueue(self.owner, {'prompt': 'Fourth message'})
        self.assertEqual(self.studio.next_job()['kind'], 'chat')


if __name__ == '__main__':
    unittest.main()
