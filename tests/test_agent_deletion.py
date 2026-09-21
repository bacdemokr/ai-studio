"""Deletion must retire a native identity without touching another agent's state."""
import json
from pathlib import Path
import sys
import tempfile
import time
import threading
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts'), str(Path(__file__).resolve().parent)]
from studio import Studio, Problem
from test_studio import Adapter
import agent_runtime as runtime


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
        removed = self.studio.delete_agent(self.owner, {'name': 'Jinny'})
        self.assertEqual(removed['agentId'], self.scout)
        self.assertEqual(self.studio.resolve_agent(self.owner), self.scout)
        for role in (None, 1, 2, 3, 4):
            self.assertFalse(self.studio.workspace(self.owner, role).exists())
        self.assertEqual(self.adapter.agents, {})
        self.assertEqual((self.studio.workspace(self.scout) / 'MEMORY.md').read_text(), 'Keep Scout memory')
        with self.studio.db() as db:
            for table in ('jobs',):
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

    def test_queued_followups_and_waiting_assigned_crew_are_cancelled_on_delete(self):
        self.studio.enqueue(self.scout, {'kind': 'reminder', 'prompt': 'Later', 'delay': 60})
        crew = self.studio.enqueue(self.owner, {'kind': 'crew', 'brief': {}, 'members': {'1': self.scout}})
        with self.studio.db() as db:
            db.execute("UPDATE jobs SET status='waiting' WHERE id=?", (crew['id'],))
        self.studio.delete_agent(self.scout, {'name': 'Scout'})
        self.assertIsNone(self.studio.profile(self.scout))
        evidence = self.studio.evidence(self.owner, crew['id'])['mission']
        self.assertEqual(evidence['status'], 'cancelled')
        self.assertEqual(evidence['payload']['roster'][1]['key'], self.scout)
        self.assertIsNone(self.studio.next_job())

    def test_running_call_finishes_before_native_cleanup_and_deletion_resumes_automatically(self):
        entered, release = threading.Event(), threading.Event()
        job = self.studio.enqueue(self.scout, {'kind': 'chat', 'prompt': 'Hello'})
        original = self.adapter.respond
        def respond(*args, **kwargs):
            entered.set()
            if not release.wait(5): raise RuntimeError('test timed out')
            (self.studio.workspace(self.scout) / 'in-flight.txt').write_text('finishing')
            return original(*args, **kwargs)
        with patch.object(self.adapter, 'respond', side_effect=respond), patch.object(self.adapter, 'remove', wraps=self.adapter.remove) as remove:
            worker = threading.Thread(target=self.studio.work)
            worker.start()
            try:
                self.assertTrue(entered.wait(5))
                result = self.studio.delete_agent(self.scout, {'name': 'Scout'})
                self.assertEqual(result['deleting'], self.scout)
                remove.assert_not_called()
                self.assertTrue(self.studio.workspace(self.scout).exists())
                self.assertEqual(self.studio.evidence(self.scout, job['id'])['mission']['status'], 'stopping')
                with self.assertRaises(Problem): self.studio.enqueue(self.scout, {'prompt': 'New request'})
                release.set()
                deadline = time.monotonic() + 5
                while self.studio.profile(self.scout) is not None and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertIsNone(self.studio.profile(self.scout))
                self.assertFalse(self.studio.workspace(self.scout).exists())
                self.assertEqual(remove.call_count, 5)  # Personal identity plus four prepared crew workspaces.
                self.assertIsNotNone(self.studio.profile(self.owner))
            finally:
                release.set();self.studio.stop.set();self.studio.signal.set();worker.join(5)

    def test_claimed_job_cannot_start_after_deletion_request(self):
        self.studio.enqueue(self.scout, {'kind': 'chat', 'prompt': 'Hello'})
        row = self.studio.next_job()  # Claimed but execute() has not entered yet.
        result = self.studio.delete_agent(self.scout, {'name': 'Scout'})
        self.assertIn('deleting', result)
        with patch.object(self.adapter, 'respond') as respond:
            self.studio.execute(row)
            respond.assert_not_called()
        self.studio.finish_pending_deletions()
        self.assertIsNone(self.studio.profile(self.scout))

    def test_running_shared_crew_stops_before_member_cleanup(self):
        crew = self.studio.enqueue(self.owner, {'kind': 'crew', 'brief': {}, 'members': {'1': self.scout}})
        row = self.studio.next_job()
        self.studio.delete_agent(self.scout, {'name': 'Scout'})
        self.assertEqual(self.studio.evidence(self.owner, crew['id'])['mission']['status'], 'stopping')
        self.studio.execute(row)
        self.studio.finish_pending_deletions()
        self.assertIsNone(self.studio.profile(self.scout))
        self.assertEqual(self.studio.evidence(self.owner, crew['id'])['mission']['status'], 'cancelled')

    def test_post_result_writes_and_native_cleanup_are_still_fenced(self):
        self.studio.executing_owners = {self.scout}
        self.studio.delete_agent(self.scout, {'name': 'Scout'})
        self.studio.finish_pending_deletions()
        self.assertTrue(self.studio.workspace(self.scout).exists())
        self.studio.executing_owners = set()
        def failed_cleanup(*args):
            agent = next(a for a in self.studio.state(self.owner)['agents'] if a['key'] == self.scout)
            self.assertTrue(agent['deletionWaiting'], 'Polling must keep waiting during native cleanup')
            raise RuntimeError('native cleanup failed')
        with patch.object(self.adapter, 'remove', side_effect=failed_cleanup) as remove:
            self.studio.finish_pending_deletions()
            self.studio.finish_pending_deletions()
            self.assertEqual(remove.call_count, 1, 'Failed cleanup must not spin/retry forever')
        agent = next(a for a in self.studio.state(self.owner)['agents'] if a['key'] == self.scout)
        self.assertTrue(agent['deleting']);self.assertFalse(agent['deletionWaiting'])
        self.studio.delete_agent(self.scout, {'name': 'Scout'})
        self.assertIsNone(self.studio.profile(self.scout))

    def test_pending_deletion_survives_restart(self):
        self.studio.enqueue(self.scout, {'kind': 'chat', 'prompt': 'Hello'})
        self.studio.next_job()
        self.studio.delete_agent(self.scout, {'name': 'Scout'})
        restarted = Studio(self.temp.name, self.adapter, start_worker=False, recover=True)
        restarted.finish_pending_deletions()
        self.assertIsNone(restarted.profile(self.scout))

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


    def test_native_adapter_checks_cleanup_outcomes_and_preserves_shared_storage(self):
        native_root = Path(self.temp.name) / 'native'
        workspace = self.studio.workspace(self.owner)
        native_id = 'bac-' + self.owner
        with patch('agent_runtime.root', return_value=native_root):
            runtime.save_config(runtime.initial_config())
            runtime.register(native_id, workspace, self.profile)
            for report in ({'purgeFailed': True}, {'failed': [{'path': 'private', 'reason': 'storage'}]},
                           {'workspaceRetained': True}, {'agentId': 'another-agent'}):
                with patch('agent_runtime.delete_native', return_value=json.dumps({'agentId': native_id, **report})), self.assertRaises(RuntimeError):
                    runtime.remove(native_id, workspace)
                self.assertTrue(workspace.exists())
            with patch('agent_runtime.delete_native', return_value=json.dumps({'agentId': native_id, 'failed': []})) as command:
                runtime.remove(native_id, workspace)
                command.assert_called_once_with(native_id)
            with self.assertRaises(RuntimeError):
                runtime.remove('bac-host', workspace)
            config = json.loads(runtime.config_path().read_text())
            config['agents']['entries'][native_id]['workspace'] = str(workspace / 'changed')
            runtime.save_config(config)
            with patch('agent_runtime.delete_native') as command, self.assertRaises(RuntimeError):
                runtime.remove(native_id, workspace)
            command.assert_not_called()

    def test_cleanup_accepts_every_catalog_role_but_rejects_unknown_ids(self):
        catalog = json.loads((Path(runtime.__file__).resolve().parents[1] / 'src/crew-catalog.json').read_text())
        with patch('agent_runtime.root', return_value=Path(self.temp.name) / 'offline'), patch('agent_runtime.delete_native') as command:
            for role in range(len(catalog)):
                runtime.remove('bac-' + self.owner + '-r' + str(role), Path(self.temp.name) / ('absent-' + str(role)))
            for suffix in ['-r01', '-r-1', '/../other']:
                with self.assertRaises(RuntimeError):
                    runtime.remove('bac-' + self.owner + suffix, Path(self.temp.name) / 'absent')
            command.assert_not_called()

    def test_openshell_runtime_lookup_accepts_all_catalog_roles(self):
        import agent_policy
        catalog=json.loads((Path(runtime.__file__).resolve().parents[1]/'src/crew-catalog.json').read_text())
        with patch('agent_policy.sandbox_registry',return_value={'containers': []}) as command:
            for i in range(len(catalog)):
                self.assertEqual(agent_policy.runtimes('bac-'+self.owner+'-r'+str(i)),[])
            self.assertEqual(command.call_count,len(catalog))
            for suffix in ('-r01','-r-1','/../other'):
                with self.assertRaises(RuntimeError):agent_policy.runtimes('bac-'+self.owner+suffix)

    def test_missing_openshell_records_are_retired_only_after_live_inventory(self):
        native_id='bac-'+self.owner;workspace=self.studio.workspace(self.owner)
        with patch('agent_runtime.root',return_value=Path(self.temp.name)/'native'):
            config=runtime.initial_config()
            config['agents']['entries'][native_id]={'workspace':str(workspace)}
            config.setdefault('plugins',{}).setdefault('entries',{})['openshell']={'enabled':True}
            runtime.save_config(config)
            with patch('agent_policy.runtimes',return_value=[{'containerName':'oc-missing'}]), patch('agent_policy.sandbox_names',return_value=set()), patch('agent_policy.sandbox_registry') as retire, patch('agent_runtime.delete_native',return_value=json.dumps({'agentId':native_id})) as cli:
                runtime.remove(native_id,workspace)
                retire.assert_called_once_with(native_id,['oc-missing'])
                cli.assert_called_once_with(native_id)
            with patch('agent_policy.runtimes',return_value=[{'containerName':'oc-missing'}]), patch('agent_policy.sandbox_names',side_effect=RuntimeError('offline')), patch('agent_policy.sandbox_registry') as retire, patch('agent_runtime.delete_native') as cli:
                with self.assertRaises(RuntimeError):runtime.remove(native_id,workspace)
                retire.assert_not_called();cli.assert_not_called()

    def test_scoped_registry_lookup_does_not_probe_unrelated_sandboxes(self):
        import agent_policy
        native_id = 'bac-' + self.owner
        entries = [{'backendId': 'openshell', 'sessionKey': 'agent:' + native_id + ':main', 'containerName': 'oc-owned'},
                   {'backendId': 'openshell', 'sessionKey': 'agent:' + native_id + '-r1:main', 'containerName': 'oc-other'}]
        with patch('agent_policy.sandbox_registry', return_value={'containers': entries}), patch('agent_runtime.cli') as cli:
            self.assertEqual([r['containerName'] for r in agent_policy.runtimes(native_id, probe=False)], ['oc-owned'])
            cli.assert_not_called()

    def test_scoped_cleanup_recovers_committed_timeout_and_preserves_other_sandboxes(self):
        import subprocess
        native_id = 'bac-' + self.owner
        workspace = self.studio.workspace(self.owner)
        with patch('agent_runtime.root', return_value=Path(self.temp.name) / 'native'):
            config = runtime.initial_config()
            config['agents']['entries'][native_id] = {'workspace': str(workspace)}
            config.setdefault('plugins', {}).setdefault('entries', {})['openshell'] = {'enabled': True}
            runtime.save_config(config)
            for mode in ('normal', 'committed-timeout', 'still-present', 'no-sandbox', 'registry-failed'):
                with self.subTest(mode=mode), patch('agent_policy.runtimes', return_value=[] if mode == 'no-sandbox' else [{'containerName': 'oc-owned'}]) as lookup, patch('agent_policy.sandbox_names') as inventory, patch('agent_policy.shell') as remove, patch('agent_policy.sandbox_registry') as retire, patch('agent_runtime.delete_native', return_value=json.dumps({'agentId': native_id})) as cli:
                    inventory.return_value = {'oc-owned', 'oc-unrelated'}
                    if mode in ('normal', 'committed-timeout'):
                        inventory.side_effect = [{'oc-owned', 'oc-unrelated'}, {'oc-unrelated'}]
                    if mode in ('committed-timeout', 'still-present'):
                        remove.side_effect = subprocess.TimeoutExpired('sandbox delete', 35)
                    if mode == 'registry-failed':
                        lookup.side_effect = RuntimeError('registry unavailable')
                    if mode in ('still-present', 'registry-failed'):
                        with self.assertRaises((RuntimeError, subprocess.TimeoutExpired)):
                            runtime.remove(native_id, workspace)
                        retire.assert_not_called()
                        cli.assert_not_called()
                    else:
                        runtime.remove(native_id, workspace)
                        cli.assert_called_once_with(native_id)
                        if mode == 'no-sandbox':
                            inventory.assert_not_called()
                            remove.assert_not_called()
                            retire.assert_not_called()
                        else:
                            remove.assert_called_once_with('sandbox', 'delete', 'oc-owned')
                            retire.assert_called_once_with(native_id, ['oc-owned'])
                            self.assertEqual(inventory.call_count, 2, 'One verified absence is sufficient, including after a committed timeout')
                    lookup.assert_called_once_with(native_id, probe=False)

    def test_cleanup_discovers_sparse_and_retired_roles(self):
        for role in (0,5,17):
            self.studio.workspace(self.owner,role).mkdir(parents=True,exist_ok=True)
        with patch.object(self.adapter,'remove',wraps=self.adapter.remove) as remove:
            self.studio.delete_agent(self.owner,{'name':'Jinny'})
        self.assertEqual([call.args[0] for call in remove.call_args_list],
                         ['bac-'+self.owner]+['bac-'+self.owner+'-r'+str(i) for i in (0,1,2,3,5,17)])
        self.assertIsNotNone(self.studio.profile(self.scout))

    def test_native_discovery_ignores_other_owners_and_catalog_size(self):
        with patch('agent_runtime.root',return_value=Path(self.temp.name)/'discovery'):
            native_id='bac-'+self.owner
            config=runtime.initial_config()
            config['agents']['entries'].update({native_id+'-r'+str(i):{} for i in (2,17)})
            config['agents']['entries']['bac-'+self.scout+'-r9']={}
            runtime.save_config(config)
            (runtime.root()/'state/agents'/ (native_id+'-r24')).mkdir(parents=True)
            self.assertEqual(runtime.deletion_roles(native_id),[2,17,24])

    def test_no_children_only_deletes_the_personal_identity(self):
        import shutil
        for role in range(4):shutil.rmtree(self.studio.workspace(self.owner,role))
        with patch.object(self.adapter,'remove',wraps=self.adapter.remove) as remove:
            self.studio.delete_agent(self.owner,{'name':'Jinny'})
        self.assertEqual(len(remove.call_args_list),1)

    def test_never_provisioned_agent_needs_no_native_runtime(self):
        with patch('agent_runtime.root', return_value=Path(self.temp.name) / 'offline'), patch('agent_runtime.delete_native') as command:
            runtime.remove('bac-' + self.owner, self.studio.workspace(self.owner))
            command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
