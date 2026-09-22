"""Hiring warms only the protected runtime, never the model or extra grants."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts'), str(Path(__file__).parent)]
from studio import Studio, Problem
from test_studio import Adapter


class ProtectedAdapter(Adapter):
    def __init__(self):
        super().__init__()
        self.prepared = set()
        self.prepares = []

    def policy_status(self, agent_id, mode, approved):
        result = super().policy_status(agent_id, mode, approved)
        if mode == 'openshell' and agent_id not in self.prepared:
            result.update(status='awaiting-first-mission', sandboxes=[])
        return result

    def policy_prepare(self, agent_id):
        self.prepares.append(agent_id)
        self.prepared.add(agent_id)


class HiringPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.adapter = ProtectedAdapter()
        self.studio = Studio(self.temp.name, self.adapter, start_worker=False)
        self.owner = self.studio.session()[0]['id']
        self.profile = dict(name='Scout', skills=['web'], protection='openshell')

    def hire(self):
        return self.studio.onboard(self.owner, self.profile)

    def test_hire_returns_before_native_work_and_prepares_without_model(self):
        self.hire()
        self.assertEqual(self.adapter.agents, {})
        with patch.object(self.adapter, 'status', side_effect=AssertionError('No model check')):
            row = self.studio.next_job()
            self.assertEqual(row['kind'], 'prepare-agent')
            self.studio.execute(row)
        self.assertEqual(self.adapter.prepares, ['bac-' + self.owner])
        self.assertEqual(self.adapter.calls, [])
        self.assertEqual(self.adapter.permissions['bac-' + self.owner], [])
        state = self.studio.state(self.owner)
        self.assertEqual(state['agents'][0]['workspacePreparation'], 'done')
        self.assertEqual(state['jobs'], [])
        self.assertIsNone(state['agents'][0]['latestMission'])
        self.assertEqual(self.studio.policy_report(self.owner)['status'], 'applied')
        self.assertIsNone(self.studio.next_job())

    def test_standard_agents_do_not_prepare_and_added_protected_agents_do(self):
        self.studio.onboard(self.owner, {**self.profile, 'protection':'standard'})
        self.assertIsNone(self.studio.next_job())
        other = self.studio.add_agent(self.owner, self.profile)['agentId']
        row = self.studio.next_job()
        self.assertEqual(row['owner'], other)
        self.studio.execute(row)
        self.assertEqual(self.adapter.prepares, ['bac-' + other])

    def test_immediate_chat_coalesces_unstarted_preparation(self):
        self.hire()
        job = self.studio.enqueue(self.owner, {'prompt':'Hello'})
        row = self.studio.next_job()
        self.assertEqual(row['id'], job['id'])
        self.studio.execute(row)
        self.assertEqual(len(self.adapter.calls), 1)
        self.assertEqual(len(self.adapter.prepares), 1)
        self.assertIsNone(self.studio.next_job())

    def test_running_preparation_is_not_personal_work_and_chat_queues_safely(self):
        self.hire()
        row = self.studio.next_job()
        state = self.studio.state(self.owner)
        self.assertEqual(state['agents'][0]['pending'], 0)
        self.assertIsNone(state['agents'][0]['activity'])
        self.assertTrue(self.studio.policy_report(self.owner)['preparing'])
        with self.assertRaises(Problem):
            self.studio.policy_change(self.owner, {'retry':True})
        job = self.studio.enqueue(self.owner, {'prompt':'Hello'})
        self.studio.execute(row)
        chat = self.studio.next_job()
        self.assertEqual(chat['id'], job['id'])
        self.studio.execute(chat)
        self.assertEqual(len(self.adapter.prepares), 1)
        self.assertEqual(len(self.adapter.calls), 1)

    def test_deletion_waits_for_native_prepare_and_cannot_recreate_deleted_agent(self):
        self.hire()
        row = self.studio.next_job()
        entered, release = threading.Event(), threading.Event()
        original = self.adapter.policy_prepare
        def prepare(agent_id):
            entered.set()
            self.assertTrue(release.wait(5))
            original(agent_id)
        with patch.object(self.adapter, 'policy_prepare', side_effect=prepare):
            worker = threading.Thread(target=self.studio.execute, args=(row,))
            worker.start()
            try:
                self.assertTrue(entered.wait(5))
                result = self.studio.delete_agent(self.owner, {'name':'Scout'})
                self.assertEqual(result['deleting'], self.owner)
                self.assertIsNotNone(self.studio.profile(self.owner))
            finally:
                release.set()
                worker.join(5)
        self.assertFalse(worker.is_alive())
        self.studio.finish_pending_deletions()
        self.assertIsNone(self.studio.profile(self.owner))
        self.assertNotIn('bac-' + self.owner, self.adapter.agents)
        self.assertIsNone(self.studio.next_job())
        self.assertEqual(self.adapter.calls, [])

    def test_queued_deletion_never_creates_runtime(self):
        self.hire()
        self.studio.delete_agent(self.owner, {'name':'Scout'})
        self.assertIsNone(self.studio.next_job())
        self.assertEqual(self.adapter.prepares, [])

    def test_failure_preserves_agent_and_first_chat_retries_protection(self):
        self.hire()
        row = self.studio.next_job()
        with patch.object(self.adapter, 'policy_prepare', side_effect=RuntimeError('Unavailable')):
            with self.assertRaises(RuntimeError):
                self.studio.execute(row)
        self.studio.event(row['id'], 'Preparation failed', 'Unavailable', status='error')
        self.assertIsNotNone(self.studio.profile(self.owner))
        self.assertEqual(self.studio.state(self.owner)['jobs'], [])
        self.studio.enqueue(self.owner, {'prompt':'Hello'})
        self.studio.execute(self.studio.next_job())
        self.assertEqual(len(self.adapter.calls), 1)
        self.assertEqual(self.studio.policy_report(self.owner)['status'], 'applied')

    def test_worker_does_not_race_explicit_policy_update(self):
        self.hire()
        with self.studio.db() as db:
            db.execute('INSERT INTO agent_policies(owner,role,updating) VALUES (?,-1,1)', (self.owner,))
        self.assertIsNone(self.studio.next_job())
        with self.studio.db() as db:
            db.execute('UPDATE agent_policies SET updating=0 WHERE owner=?', (self.owner,))
        self.studio.execute(self.studio.next_job())
        self.assertEqual(len(self.adapter.prepares), 1)

    def test_foreground_work_has_priority_over_unstarted_warmups(self):
        self.hire()
        other = self.studio.add_agent(self.owner, {**self.profile, 'protection':'standard'})['agentId']
        job = self.studio.enqueue(other, {'prompt':'Hello'})
        self.assertEqual(self.studio.next_job()['id'], job['id'])

    def test_restart_preserves_unstarted_warmup(self):
        self.hire()
        restarted = Studio(self.temp.name, self.adapter, start_worker=False, recover=True)
        restarted.execute(restarted.next_job())
        self.assertEqual(len(self.adapter.prepares), 1)
        self.assertEqual(self.adapter.calls, [])
