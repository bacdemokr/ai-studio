import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from studio import Studio, Problem, capacity, safe_file
import agent_runtime
from telegram_bridge import accept_message


class Adapter:
    def __init__(self):
        self.agents = {}
        self.calls = []

    def status(self):
        return {'ready': True, 'gateway': True, 'model': True}

    def register(self, agent_id, workspace, profile, role=None):
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / 'inbox').mkdir(exist_ok=True)
        self.agents[agent_id] = workspace

    def respond(self, agent_id, session, prompt):
        self.calls.append((agent_id, session, prompt))
        if 'remember' in prompt:
            (self.agents[agent_id] / 'MEMORY.md').write_text('# Saved preferences\nVegetarian, concise English.\n')
        if 'app fixture' in prompt:
            return 'Test double output\n```html\n<button id="play">Play</button>\n```'
        return 'Fixture deliverable by ' + agent_id


class StudioTests(unittest.TestCase):
    def setUp(self):
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


if __name__ == '__main__':
    unittest.main()
