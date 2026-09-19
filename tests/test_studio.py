import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from studio import Studio, Problem, capacity, safe_file, MAX_AGENTS
import agent_runtime
from telegram_bridge import accept_message


class Adapter:
    def __init__(self):
        self.agents = {}
        self.calls = []
        self.profiles = {}
        self.permissions = {}
        self.policy_logs = {}

    def status(self):
        return {'ready': True, 'gateway': True, 'model': True}

    def register(self, agent_id, workspace, profile, role=None):
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / 'inbox').mkdir(exist_ok=True)
        self.agents[agent_id] = workspace
        self.profiles[agent_id] = dict(profile)

    def remove(self, agent_id, workspace):
        self.agents.pop(agent_id, None)
        self.profiles.pop(agent_id, None)

    def policy_status(self, agent_id, mode, approved):
        from agent_policy import CATALOG, policy_document, network_rows
        native = agent_id in self.agents
        current = self.permissions.get(agent_id, [])
        return {'mode': mode, 'hostReady': True, 'status': 'standard' if mode == 'standard' else 'awaiting-first-mission' if not native else 'applied' if current == approved else 'needs-review',
                'catalog': CATALOG, 'requested': approved, 'checkedAt': time.time(), 'testFixture': True,
                'sandboxes': [{'name': 'fixture-' + agent_id, 'running': True, 'revision': 1, 'loaded': True, 'matchesRequest': current == approved}] if native else [],
                'rules': network_rows(policy_document(current)), 'logs': self.policy_logs.get(agent_id, [])}

    def policy_apply(self, agent_id, approved):
        if agent_id not in self.agents:
            raise RuntimeError('Fixture sandbox does not exist yet')
        self.permissions[agent_id] = list(approved)
        return self.policy_status(agent_id, 'openshell', approved)

    def respond(self, agent_id, session, prompt):
        self.calls.append((agent_id, session, prompt))
        if self.profiles.get(agent_id, {}).get('protection') == 'openshell' and 'weather' in prompt.lower():
            allowed = 'weather' in self.permissions.get(agent_id, [])
            self.policy_logs.setdefault(agent_id, []).insert(0, {'action': 'allow' if allowed else 'deny', 'host': 'api.open-meteo.com', 'binary': '/usr/bin/curl', 'source': 'Simulated test fixture'})
            if not allowed:
                raise RuntimeError('TEST FIXTURE: OpenShell denied api.open-meteo.com. Approve Weather in Policies before retrying.')
        if 'remember' in prompt:
            (self.agents[agent_id] / 'MEMORY.md').write_text('# Saved preferences\nVegetarian, concise English.\n')
        if 'app fixture' in prompt:
            return 'Test double output\n```html\n<button id="play">Play</button>\n```'
        return 'Fixture deliverable by ' + agent_id


class StudioTests(unittest.TestCase):
    def setUp(self):
        agent_runtime._expected_identity.clear()
        self.addCleanup(agent_runtime._expected_identity.clear)
        self.temp = tempfile.TemporaryDirectory()
        self.adapter = Adapter()
        self.studio = Studio(self.temp.name, self.adapter, start_worker=False)
        self.person, _ = self.studio.session()
        self.owner = self.person['id']
        self.studio.onboard(self.owner, {'name': 'Jinny', 'persona': 'maker', 'skills': list(agent_runtime.SKILLS)})

    def tearDown(self):
        self.temp.cleanup()

    def run_next(self):
        row = self.studio.next_job()
        self.assertIsNotNone(row)
        self.studio.execute(row)
        return row

    def add_agent(self, name='Scout'):
        return self.studio.add_agent(self.owner, {'name': name, 'persona': 'analyst', 'skills': ['documents', 'web']})['agentId']

    def test_appearance_persists_and_follows_custom_crew_assignments(self):
        appearance = {'body': 'rover', 'color': 'coral', 'accessory': 'glasses'}
        created = self.studio.add_agent(self.owner, {'name': 'Rover', 'persona': 'analyst',
                                       'skills': ['documents'], 'avatar': appearance})
        key = created['agentId']
        restarted = Studio(self.temp.name, self.adapter, start_worker=False)
        self.assertEqual(restarted.profile(key)['avatar'], appearance)
        self.assertEqual(next(a for a in restarted.state(self.owner)['agents'] if a['key'] == key)['avatar'], appearance)
        restarted.configure(key, {'name': 'Rover II', 'persona': 'maker', 'skills': ['writer']})
        self.assertEqual(restarted.profile(key)['avatar'], appearance)
        job = restarted.enqueue(self.owner, {'kind': 'crew', 'brief': {}, 'members': {'1': key}})
        self.assertEqual(restarted.state(self.owner)['jobs'][0]['payload']['roster'][1]['avatar'], appearance)

    def test_legacy_appearance_is_stable_and_invalid_appearance_is_rejected(self):
        profile = self.studio.profile(self.owner)
        profile.pop('avatar')
        with self.studio.db() as db:
            db.execute('UPDATE agents SET profile=? WHERE id=?', (json.dumps(profile), self.owner))
        expected = self.studio.profile(self.owner)['avatar']
        restarted = Studio(self.temp.name, self.adapter, start_worker=False)
        self.assertEqual(restarted.profile(self.owner)['avatar'], expected)
        self.assertEqual(restarted.state(self.owner)['agents'][0]['avatar'], expected)
        for avatar in ('bad', {}, {'body': '<script>', 'color': 'cyan', 'accessory': 'headset'},
                       {'body': 'round', 'color': 'cyan', 'accessory': 'headset', 'extra': True}):
            with self.assertRaises(Problem):
                restarted.configure(self.owner, {**profile, 'avatar': avatar})
        self.assertEqual(restarted.profile(self.owner)['avatar'], expected)

    def test_agent_collection_keeps_native_identity_memory_files_and_jobs_separate(self):
        scout = self.add_agent()
        self.studio.enqueue(self.owner, {'prompt': 'remember my preferences'})
        self.run_next()
        self.studio.upload(self.owner, {'name': 'private.md', 'content': 'Lead preferences'})
        self.studio.enqueue(scout, {'prompt': 'Read a public page'})
        self.run_next()
        restarted = Studio(self.temp.name, self.adapter, start_worker=False)
        self.assertEqual(len(restarted.state(scout)['agents']), 2)
        self.assertEqual(restarted.resolve_agent(self.owner, scout), scout)
        self.assertEqual(restarted.state(scout)['profile']['name'], 'Scout')
        self.assertNotIn('Vegetarian', restarted.state(scout)['memory'])
        self.assertFalse(any(f['path'] == 'inbox/private.md' for f in restarted.files(scout)))
        self.assertEqual(len(restarted.state(scout)['jobs']), 1)
        self.assertNotEqual(self.adapter.calls[0][0], self.adapter.calls[1][0])
        self.assertNotEqual(self.adapter.calls[0][1], self.adapter.calls[1][1])
        restarted.reset_board(scout)
        self.assertEqual(restarted.state(scout)['jobs'], [])
        self.assertEqual(len(restarted.state(self.owner)['jobs']), 1)
        self.assertIn('Vegetarian', restarted.state(self.owner)['memory'])

    def test_existing_single_agent_database_migrates_without_changing_ownership(self):
        self.studio.enqueue(self.owner, {'prompt': 'remember my preferences'})
        self.run_next()
        self.studio.reset_board(self.owner)
        with self.studio.db() as db:
            db.execute('INSERT INTO phones VALUES (?,?)', (self.owner, 'fixture-chat'))
            db.execute('DROP TABLE agents')  # Represents the previous single-agent schema.
            db.execute("DELETE FROM metadata WHERE key='agent-collection-migrated'")
        migrated = Studio(self.temp.name, self.adapter, start_worker=False)
        state = migrated.state(self.owner)
        self.assertEqual(state['agentId'], self.owner)
        self.assertEqual(state['profile']['id'], 'bac-' + self.owner)
        self.assertEqual(state['jobs'], [])
        self.assertIn('Vegetarian', state['memory'])
        self.assertTrue(state['files'])
        self.assertTrue(state['phone'])
        self.assertFalse(migrated.session(self.person['token'])[1])
        migrated.configure(self.owner, {'name': 'Renamed', 'persona': 'guide', 'skills': ['memory']})
        again = Studio(self.temp.name, self.adapter, start_worker=False)
        self.assertEqual(again.profile(self.owner)['name'], 'Renamed')

    def test_custom_agents_receive_crew_handoffs_in_their_own_workspaces(self):
        scout = self.add_agent()
        writer = self.add_agent('Echo')
        job = self.studio.enqueue(self.owner, {'kind': 'crew', 'brief': {}, 'members': {'1': scout, '3': writer}})
        with self.assertRaises(Problem):
            self.studio.configure(scout, {'name': 'Changed', 'skills': ['writer'], 'persona': 'guide'})
        self.run_next()
        evidence = self.studio.evidence(self.owner, job['id'])['mission']
        self.assertEqual(evidence['status'], 'done')
        self.assertEqual(evidence['payload']['roster'][1]['name'], 'Scout')
        self.assertEqual(self.adapter.calls[1][0], 'bac-' + scout)
        self.assertEqual(self.adapter.calls[3][0], 'bac-' + writer)
        self.assertEqual(len(set(c[0] for c in self.adapter.calls)), 5)
        self.assertIn('Operations planner', (self.studio.workspace(writer) / 'inbox/handoffs.md').read_text())
        self.assertEqual(evidence['payload']['handoffs']['3']['receivedFrom'], ['0', '1', '2'])
        self.assertEqual(self.studio.profile(scout)['skills'], ['documents', 'web'])
        self.assertEqual(self.studio.state(scout)['agents'][1]['pending'], 0)
        self.studio.configure(scout, {'name': 'Scout 2', 'skills': ['web'], 'persona': 'guide'})
        self.assertEqual(self.studio.evidence(self.owner, job['id'])['mission']['payload']['roster'][1]['name'], 'Scout')

    def test_collection_access_and_crew_assignments_are_account_scoped(self):
        scout = self.add_agent()
        other, _ = self.studio.session()
        self.studio.onboard(other['id'], {'name': 'Other', 'persona': 'guide', 'skills': ['memory']})
        with self.assertRaises(Problem):
            self.studio.resolve_agent(other['id'], scout)
        for members in ({'1': scout, '2': scout}, {'1': self.owner}, {'1': other['id']}, {'0': scout}, {'1': ['invalid']}):
            with self.assertRaises(Problem):
                self.studio.enqueue(self.owner, {'kind': 'crew', 'members': members})
        self.assertEqual(self.studio.state(self.owner)['jobs'], [])
        self.assertEqual(len(self.studio.state(other['id'])['agents']), 1)

    def test_queue_budget_is_shared_across_personal_agents(self):
        scout = self.add_agent()
        for owner in (self.owner, scout, self.owner):
            self.studio.enqueue(owner, {'kind': 'reminder', 'prompt': 'Follow up', 'delay': 60})
        with self.assertRaises(Problem) as caught:
            self.studio.enqueue(scout, {'kind': 'reminder', 'prompt': 'Fourth task', 'delay': 60})
        self.assertEqual(caught.exception.status, 429)
        self.studio.reset_board(scout)
        self.assertEqual(len(self.studio.state(self.owner)['jobs']), 2)
        self.studio.enqueue(scout, {'kind': 'reminder', 'prompt': 'Slot available', 'delay': 60})

    def test_agent_limit_and_invalid_creation_leave_existing_collection_unchanged(self):
        with self.assertRaises(Problem):
            self.studio.add_agent(self.owner, {'name': 'No skills', 'skills': []})
        self.assertEqual(len(self.studio.state(self.owner)['agents']), 1)
        for i in range(MAX_AGENTS - 1):
            self.add_agent('Agent ' + str(i))
        with self.assertRaises(Problem):
            self.add_agent('One too many')
        self.assertEqual(len(self.studio.state(self.owner)['agents']), MAX_AGENTS)

    def test_native_memory_and_deliverables_survive_restart(self):
        self.studio.enqueue(self.owner, {'prompt': 'remember my preferences and make an app fixture'})
        self.run_next()
        restarted = Studio(self.temp.name, self.adapter, start_worker=False, recover=True)
        person, new = restarted.session(self.person['token'])
        self.assertFalse(new)
        state = restarted.state(person['id'])
        self.assertIn('Vegetarian', state['memory'])
        self.assertEqual(state['jobs'][0]['status'], 'done')
        self.assertTrue(any(f['path'].endswith('.html') for f in state['files']))
        self.assertEqual(state['profile']['name'], 'Jinny')

    def test_crew_handoffs_wait_for_concrete_equipment_decision(self):
        job = self.studio.enqueue(self.owner, {'kind': 'crew', 'brief': {'spark': 0, 'workstation': 0}})
        self.run_next()
        state = self.studio.state(self.owner)['jobs'][0]
        self.assertEqual(state['status'], 'waiting')
        self.assertEqual(len(self.adapter.calls), 3)
        # Marketing cannot run before the participant approves the actual shortfall.
        other, _ = self.studio.session()
        with self.assertRaises(Problem):
            self.studio.decision(other['id'], job['id'], 'approve-equipment')
        self.studio.decision(self.owner, job['id'], 'approve-equipment')
        with self.assertRaises(Problem):
            self.studio.decision(self.owner, job['id'], 'approve-equipment')
        self.run_next()
        self.assertEqual(len(self.adapter.calls), 5)
        self.assertEqual(len(set(call[0] for call in self.adapter.calls)), 5)
        self.assertIn(self.adapter.calls[0][0], self.adapter.calls[3][2])
        self.assertIn('pending availability', self.adapter.calls[3][2])
        self.assertEqual(self.studio.state(self.owner)['jobs'][0]['status'], 'done')

    def test_capacity_rounding_preserves_people_and_exposes_assumptions(self):
        for count in (1, 3, 17, 121, 2999):
            brief, calc = capacity({'attendees': count})
            self.assertEqual(sum(x['attendees'] for x in calc['topics']), count)
            self.assertTrue(all(x['stations'] * calc['slots'] * brief['groupSize'] >= x['attendees'] for x in calc['topics']))
        with self.assertRaises(Problem):
            capacity({'shares': [20, 20, 20]})
        with self.assertRaises(Problem):
            capacity({'duration': 30, 'common': 30})

    def test_isolation_path_guards_and_input_validation(self):
        other, _ = self.studio.session()
        self.studio.upload(self.owner, {'name': 'brief.txt', 'content': 'Private participant brief'})
        self.assertEqual(self.studio.state(other['id'])['files'], [])
        for path in ('../studio.sqlite', '/etc/passwd', 'inbox/../../studio.sqlite', 'inbox/malware.exe'):
            with self.assertRaises(Problem):
                safe_file(self.studio.workspace(self.owner), path)
        linked = self.studio.workspace(self.owner) / 'inbox/leak.txt'
        linked.symlink_to(self.studio.db_path)
        self.assertEqual(len(self.studio.files(self.owner)), 1)
        with self.assertRaises(Problem):
            self.studio.onboard(other['id'], {'name': 'Bad\nname', 'persona': 'guide', 'skills': ['writer']})

    def test_schedule_cancel_and_interrupted_task_are_durable(self):
        job = self.studio.enqueue(self.owner, {'kind': 'reminder', 'prompt': 'Come back later', 'delay': 60})
        self.assertIsNone(self.studio.next_job())
        self.studio.decision(self.owner, job['id'], 'cancel')
        self.assertIsNone(self.studio.next_job())
        self.studio.enqueue(self.owner, {'prompt': 'normal task'})
        self.studio.next_job()  # model accepted a request, then the app crashes
        restarted = Studio(self.temp.name, self.adapter, start_worker=False, recover=True)
        self.assertEqual(restarted.state(self.owner)['jobs'][0]['status'], 'error')
        self.assertIsNone(restarted.next_job(), 'Do not replay possibly completed work after restart')

    def test_phone_pair_is_private_expiring_single_use_and_shares_web_session(self):
        code = 'test-code'
        with self.studio.db() as db:
            db.execute('INSERT INTO pairs VALUES (?,?,?)', (hashlib.sha256(code.encode()).hexdigest(), self.owner, time.time()+60))
        with patch('telegram_bridge.telegram', return_value={}):
            accept_message(self.studio, {'chat': {'type': 'group', 'id': 1}, 'text': '/start '+code})
            self.assertFalse(self.studio.state(self.owner)['phone'])
            accept_message(self.studio, {'chat': {'type': 'private', 'id': 2}, 'text': '/start '+code})
            self.assertTrue(self.studio.state(self.owner)['phone'])
            accept_message(self.studio, {'chat': {'type': 'private', 'id': 3}, 'text': '/start '+code})
            accept_message(self.studio, {'chat': {'type': 'private', 'id': 3}, 'text': 'unpaired task'})
            self.assertEqual(len(self.studio.state(self.owner)['jobs']), 0)
            accept_message(self.studio, {'chat': {'type': 'private', 'id': 2}, 'text': 'phone task'})
            self.run_next()
        self.studio.enqueue(self.owner, {'prompt': 'web task'})
        self.run_next()
        self.assertEqual(self.adapter.calls[0][0:2], self.adapter.calls[1][0:2])

    def test_native_config_restricts_tools_and_models(self):
        with patch('agent_runtime.root', return_value=Path(self.temp.name) / 'native'):
            agent_runtime.save_config(agent_runtime.initial_config())
            agent_runtime.register('bac-test', Path(self.temp.name) / 'workspace', {'name': 'Nova', 'persona': 'maker', 'skills': ['builder']})
            config = json.loads(agent_runtime.config_path().read_text())
            entry = config['agents']['entries']['bac-test']
            self.assertEqual(entry['modelPolicy']['allow'], ['bac-vllm/bac-local'])
            self.assertNotIn('web_fetch', entry['tools']['allow'])
            self.assertTrue(entry['tools']['fs']['workspaceOnly'])
            self.assertIn('exec', config['tools']['deny'])
            self.assertEqual(agent_runtime.config_path().stat().st_mode & 0o777, 0o600)

    def test_new_agent_waits_for_gateway_discovery_without_replaying_post(self):
        with patch('agent_runtime.gateway', side_effect=[{'data': []}, {'data': [{'id': 'openclaw/bac-test'}]},
                   {'choices': [{'message': {'content': 'Completed once'}}]}]) as gateway, patch('agent_runtime.time.sleep'):
            self.assertEqual(agent_runtime.respond('bac-test', 'stable-user', 'A request'), 'Completed once')
            calls = gateway.call_args_list
            self.assertEqual([c.args[0] for c in calls], ['/v1/models', '/v1/models', '/v1/chat/completions'])
            self.assertEqual(calls[-1].args[1]['user'], 'stable-user')

    def test_running_stop_keeps_completed_work_and_never_starts_next_role(self):
        job = self.studio.enqueue(self.owner, {'kind': 'crew', 'brief': {}})
        original = self.adapter.respond
        def stop_during_call(*args):
            self.assertEqual(self.studio.decision(self.owner, job['id'], 'cancel')['status'], 'stopping')
            with self.assertRaises(Problem):
                self.studio.reset_board(self.owner)
            return original(*args)
        with patch.object(self.adapter, 'respond', side_effect=stop_during_call):
            self.run_next()
        state = self.studio.state(self.owner)
        self.assertEqual(state['jobs'][0]['status'], 'cancelled')
        self.assertEqual(len(self.adapter.calls), 1)
        self.assertTrue(state['files'])
        handoff = state['jobs'][0]['payload']['handoffs']['0']
        self.assertEqual(handoff['receivedFrom'], [])
        self.assertEqual(handoff['sharedState']['brief']['city'], 'Zurich')
        self.assertEqual(len(handoff['outputSHA256']), 64)
        self.assertIsNone(self.studio.next_job())

    def test_stop_solo_does_not_send_channel_reply(self):
        job = self.studio.enqueue(self.owner, {'prompt': 'Make a draft'}, source='telegram')
        def finish(*args):
            self.studio.decision(self.owner, job['id'], 'cancel')
            return 'Draft created while the active call was completing.'
        with patch.object(self.adapter, 'respond', side_effect=finish), patch('telegram_bridge.reply_to_owner') as send:
            self.run_next()
            send.assert_not_called()
        self.assertEqual(self.studio.state(self.owner)['jobs'][0]['status'], 'cancelled')

    def test_reset_archives_only_own_board_and_preserves_memory_files_evidence(self):
        self.studio.enqueue(self.owner, {'prompt': 'remember my preferences'})
        self.run_next()
        job = self.studio.enqueue(self.owner, {'kind': 'reminder', 'prompt': 'pending', 'delay': 60})
        other, _ = self.studio.session()
        self.studio.onboard(other['id'], {'name': 'Other', 'persona': 'guide', 'skills': ['writer']})
        other_job = self.studio.enqueue(other['id'], {'kind': 'reminder', 'prompt': 'different participant', 'delay': 60})
        self.studio.reset_board(self.owner)
        state = self.studio.state(self.owner)
        self.assertEqual(state['jobs'], [])
        self.assertIn('Vegetarian', state['memory'])
        self.assertEqual(state['profile']['name'], 'Jinny')
        self.assertTrue(state['files'])
        self.assertEqual(self.studio.state(other['id'])['jobs'][0]['id'], other_job['id'])
        self.assertEqual(self.studio.evidence(self.owner, job['id'])['mission']['status'], 'cancelled')
        with self.assertRaises(Problem):
            self.studio.evidence(other['id'], job['id'])
        export = json.dumps(self.studio.evidence(self.owner, job['id']))
        self.assertNotIn(self.person['token'], export)
        self.assertNotIn(self.person['csrf'], export)

    def test_stop_and_reset_claims_do_not_survive_crash_as_false_success(self):
        job = self.studio.enqueue(self.owner, {'prompt': 'in flight'})
        self.studio.next_job()
        self.studio.decision(self.owner, job['id'], 'cancel')
        with self.assertRaises(Problem):
            self.studio.reset_board(self.owner)
        restarted = Studio(self.temp.name, self.adapter, start_worker=False, recover=True)
        self.assertEqual(restarted.state(self.owner)['jobs'][0]['status'], 'error')
        self.assertIsNone(restarted.next_job())


if __name__ == '__main__':
    unittest.main()
