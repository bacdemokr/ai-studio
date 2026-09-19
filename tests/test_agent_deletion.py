"""Deletion must retire a native identity without touching another agent's state."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts'), str(Path(__file__).resolve().parent)]
from studio import Studio, Problem
from test_studio import Adapter
import agent_runtime as runtime
from telegram_bridge import accept_message


class DeletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.adapter = Adapter()
        self.studio = Studio(self.temp.name, self.adapter, start_worker=False)
        self.account, _ = self.studio.session()
        self.owner = self.account['id']
        self.profile = {'name': 'Jinny', 'persona': 'maker', 'skills': ['memory', 'documents']}
        self.studio.onboard(self.owner, self.profile)
        self.scout = self.studio.add_agent(self.owner, {**self.profile, 'name': 'Scout'})['agentId']

    def tearDown(self):
        self.temp.cleanup()

    def test_delete_original_and_last_agent_preserves_account_and_never_resurrects(self):
        for owner, note in ((self.owner, 'Private original memory'), (self.scout, 'Keep Scout memory')):
            (self.studio.workspace(owner) / 'MEMORY.md').write_text(note)
            self.studio.upload(owner, {'name': 'note.md', 'content': note})
        job = self.studio.enqueue(self.owner, {'prompt': 'remember this'})
        self.studio.execute(self.studio.next_job())
        for role in range(1, 5):
            self.studio.ensure_agent(self.owner, self.studio.profile(self.owner), role)
        with self.studio.db() as db:
            db.execute('INSERT INTO phones VALUES (?,?)', (self.owner, '123'))
            db.execute('INSERT INTO pairs VALUES (?,?,?)', ('code', self.owner, time.time() + 100))
        removed = self.studio.delete_agent(self.owner, {'name': 'Jinny'})
        self.assertEqual(removed['agentId'], self.scout)
        self.assertEqual(self.studio.resolve_agent(self.owner), self.scout)
        for role in (None, 1, 2, 3, 4):
            self.assertFalse(self.studio.workspace(self.owner, role).exists())
        self.assertEqual(self.adapter.agents, {})
        self.assertEqual((self.studio.workspace(self.scout) / 'MEMORY.md').read_text(), 'Keep Scout memory')
        with self.studio.db() as db:
            for table in ('jobs', 'phones', 'pairs'):
                self.assertEqual(db.execute('SELECT count(*) FROM ' + table + ' WHERE owner=?', (self.owner,)).fetchone()[0], 0)
        with self.assertRaises(Problem):
            self.studio.resolve_agent(self.owner, self.owner)
        with self.assertRaises(Problem):
            self.studio.evidence(self.owner, job['id'])
        restarted = Studio(self.temp.name, self.adapter, start_worker=False)
        self.assertEqual(restarted.session(self.account['token'])[0]['id'], self.owner)
        self.assertEqual([a['key'] for a in restarted.state(self.scout)['agents']], [self.scout])
        third = restarted.add_agent(self.owner, {**self.profile, 'name': 'Third'})['agentId']
        restarted.delete_agent(third, {'name': 'Third'})
        last = restarted.delete_agent(self.scout, {'name': 'Scout'})['agentId']
        self.assertNotIn(last, (self.owner, self.scout, third))
        restarted = Studio(self.temp.name, self.adapter, start_worker=False)
        self.assertEqual(restarted.resolve_agent(self.owner), last)
        self.assertEqual(restarted.state(last)['agents'], [])
        restarted.onboard(last, self.profile)
        self.assertEqual(len(restarted.state(last)['agents']), 1)
        self.assertNotIn('Private original memory', restarted.state(last)['memory'])
        restarted.add_agent(self.owner, {**self.profile, 'name': 'One more'})
        self.assertEqual(len(restarted.state(last)['agents']), 2)

    def test_pending_personal_and_assigned_crew_block_deletion(self):
        personal = self.studio.enqueue(self.scout, {'kind': 'reminder', 'prompt': 'Later', 'delay': 60})
        for status in ('queued', 'running', 'waiting', 'stopping'):
            with self.studio.db() as db:
                db.execute('UPDATE jobs SET status=? WHERE id=?', (status, personal['id']))
            with self.assertRaises(Problem) as caught:
                self.studio.delete_agent(self.scout, {'name': 'Scout'})
            self.assertEqual(caught.exception.status, 409)
            self.assertFalse(self.studio.state(self.scout)['deleting'])
        with self.studio.db() as db:
            db.execute("UPDATE jobs SET status='cancelled' WHERE id=?", (personal['id'],))
        crew = self.studio.enqueue(self.owner, {'kind': 'crew', 'brief': {}, 'members': {'1': self.scout}})
        with self.assertRaises(Problem):
            self.studio.delete_agent(self.scout, {'name': 'Scout'})
        self.studio.decision(self.owner, crew['id'], 'cancel')
        self.studio.executing_owners = {self.scout}
        with self.assertRaises(Problem):
            self.studio.delete_agent(self.scout, {'name': 'Scout'})
        self.studio.executing_owners = set()
        self.studio.delete_agent(self.scout, {'name': 'Scout'})
        # Other agents keep their historical crew evidence, including frozen specialist attribution.
        self.assertEqual(self.studio.evidence(self.owner, crew['id'])['mission']['payload']['roster'][1]['key'], self.scout)

    def test_partial_cleanup_stays_fenced_across_restart_and_can_be_retried(self):
        with patch.object(self.adapter, 'remove', side_effect=RuntimeError('native cleanup failed')):
            with self.assertRaises(Problem) as caught:
                self.studio.delete_agent(self.scout, {'name': 'Scout'})
        self.assertEqual(caught.exception.status, 503)
        self.studio = Studio(self.temp.name, self.adapter, start_worker=False)
        self.assertTrue(self.studio.state(self.scout)['deleting'])
        actions = [lambda: self.studio.configure(self.scout, self.profile),
                   lambda: self.studio.enqueue(self.scout, {'kind': 'reminder', 'prompt': 'later'}),
                   lambda: self.studio.upload(self.scout, {'name': 'new.md', 'content': 'no'}),
                   lambda: self.studio.enqueue(self.owner, {'kind': 'crew', 'brief': {}, 'members': {'1': self.scout}})]
        for action in actions:
            with self.assertRaises(Problem):
                action()
        self.studio.delete_agent(self.scout, {'name': 'Scout'})
        self.assertEqual(len(self.studio.state(self.owner)['agents']), 1)

    def test_stale_confirmation_and_other_participant_are_rejected(self):
        with self.assertRaises(Problem):
            self.studio.delete_agent(self.scout, {'name': 'Jinny'})
        other, _ = self.studio.session()
        with self.assertRaises(Problem) as caught:
            self.studio.resolve_agent(other['id'], self.scout)
        self.assertEqual(caught.exception.status, 404)
        self.assertFalse(self.studio.state(self.scout)['deleting'])

    def test_telegram_pairing_cannot_reactivate_agent_pending_cleanup(self):
        import hashlib
        with self.studio.db() as db:
            db.execute('UPDATE agents SET deleting=1 WHERE id=?', (self.scout,))
            db.execute('INSERT INTO pairs VALUES (?,?,?)', (hashlib.sha256(b'token').hexdigest(), self.scout, time.time() + 60))
        with patch('telegram_bridge.telegram') as send:
            accept_message(self.studio, {'chat': {'id': 12, 'type': 'private'}, 'text': '/start token'})
            send.assert_not_called()
        self.assertFalse(self.studio.state(self.scout)['phone'])

    def test_native_adapter_checks_cleanup_outcomes_and_preserves_shared_storage(self):
        native_root = Path(self.temp.name) / 'native'
        workspace = self.studio.workspace(self.owner)
        native_id = 'bac-' + self.owner
        with patch('agent_runtime.root', return_value=native_root):
            runtime.save_config(runtime.initial_config())
            runtime.register(native_id, workspace, self.profile)
            for report in ({'purgeFailed': True}, {'failed': [{'path': 'private', 'reason': 'storage'}]},
                           {'workspaceRetained': True}, {'agentId': 'another-agent'}):
                with patch('agent_runtime.cli', return_value=json.dumps({'agentId': native_id, **report})), self.assertRaises(RuntimeError):
                    runtime.remove(native_id, workspace)
                self.assertTrue(workspace.exists())
            with patch('agent_runtime.cli', return_value=json.dumps({'agentId': native_id, 'failed': []})) as command:
                runtime.remove(native_id, workspace)
                command.assert_called_once_with('agents', 'delete', native_id, '--force', '--json')
            with self.assertRaises(RuntimeError):
                runtime.remove('bac-host', workspace)
            config = json.loads(runtime.config_path().read_text())
            config['agents']['entries'][native_id]['workspace'] = str(workspace / 'changed')
            runtime.save_config(config)
            with patch('agent_runtime.cli') as command, self.assertRaises(RuntimeError):
                runtime.remove(native_id, workspace)
            command.assert_not_called()

    def test_never_provisioned_agent_needs_no_native_runtime(self):
        with patch('agent_runtime.root', return_value=Path(self.temp.name) / 'offline'), patch('agent_runtime.cli') as command:
            runtime.remove('bac-' + self.owner, self.studio.workspace(self.owner))
            command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
