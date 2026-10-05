"""Two-scenario lifecycle and HTTP isolation checks with no live runtimes."""
import http.client
import json
import tempfile
import threading
import unittest
from unittest.mock import patch

from test_studio import Studio, Adapter, Problem
from serve import create_server
import team_models


class ScenarioBoundaryTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.adapter = Adapter()
        self.app = Studio(folder.name, self.adapter, start_worker=False)
        self.person = self.app.session()[0]
        self.owner = self.person['id']
        self.teams = {s: self.app.crew_owner(self.owner, s) for s in ('plan', 'event-brief')}

    def finish(self):
        while (row := self.app.next_job()) is not None:
            self.app.execute(row)

    def saved(self, scenario, name='report.md'):
        path = self.app.workspace(self.teams[scenario]) / 'artifacts' / name
        path.write_text(scenario)
        return path

    def test_scoped_reset_drains_only_its_running_job_and_fences_new_work(self):
        rows = {}
        for scenario, owner in self.teams.items():
            self.saved(scenario)
            self.app.enqueue(owner, {'kind': 'crew-chat', 'crewRole': 0, 'prompt': 'hello'})
            rows[scenario] = self.app.next_job()
            self.assertEqual(rows[scenario]['owner'], owner)
        self.assertTrue(self.app.reset_crew_chats(self.teams['plan'], reset_event=True)['resetting'])
        self.assertTrue(self.app.state(self.owner)['bacResetting'])
        self.assertFalse(self.app.state(self.owner, 'event-brief')['bacResetting'])
        with self.assertRaises(Problem):
            self.app.upload(self.teams['plan'], {'crewRole': 0, 'name': 'blocked.md', 'content': 'blocked'})
        with self.assertRaises(Problem):
            self.app.enqueue(self.teams['plan'], {'kind': 'crew-chat', 'crewRole': 5, 'prompt': 'blocked'})
        self.app.execute(rows['plan'])
        self.app.finish_pending_bac_resets()
        self.assertEqual(self.app.state(self.owner)['crewChats'], [])
        self.assertFalse((self.app.workspace(self.teams['plan']) / 'artifacts/report.md').exists())
        self.assertEqual(self.app.state(self.owner, 'event-brief')['crewChats'][0]['status'], 'running')
        self.app.execute(rows['event-brief'])
        self.assertEqual(self.app.state(self.owner, 'event-brief')['crewChats'][0]['status'], 'done')
        self.assertEqual((self.app.workspace(self.teams['event-brief']) / 'artifacts/report.md').read_text(), 'event-brief')

    def test_reset_all_waits_for_both_teams_and_preserves_models(self):
        with patch.object(team_models, 'public', return_value={'models': [{'id': m} for m in team_models.MODELS]}):
            for index, owner in enumerate(self.teams.values()):
                team_models.select(self.app, owner, {'role': 0, 'model': team_models.MODELS[index]})
        rows = []
        for scenario, owner in self.teams.items():
            self.saved(scenario)
            self.app.upload(owner, {'crewRole': 0, 'name': 'notes.md', 'content': scenario})
            self.app.enqueue(owner, {'kind': 'crew-chat', 'crewRole': 0, 'prompt': 'hello'})
            rows.append(self.app.next_job())
        self.assertTrue(self.app.reset_crew_chats(self.owner, reset_event=True)['resetting'])
        for scenario in self.teams:
            self.assertTrue(self.app.state(self.owner, scenario)['bacResetting'])
        self.app.execute(rows[0]); self.app.finish_pending_bac_resets()
        self.assertTrue(self.app.state(self.owner)['bacResetting'])
        self.app.execute(rows[1]); self.app.finish_pending_bac_resets()
        for index, (scenario, owner) in enumerate(self.teams.items()):
            state = self.app.state(self.owner, scenario)
            self.assertFalse(state['bacResetting'])
            self.assertEqual(state['crewChats'], [])
            self.assertEqual(state['crewDocuments'], [])
            self.assertEqual(state['teamSelections'][0]['id'], team_models.MODELS[index])
            self.assertFalse((self.app.workspace(owner) / 'artifacts/report.md').exists())

    def test_uploaded_document_counts_as_saved_work_without_a_chat(self):
        self.app.upload(self.teams['plan'], {'crewRole': 0, 'name': 'notes.md', 'content': 'Read this later'})
        status = {s['id']: s for s in self.app.scenario_status(self.owner)}
        self.assertTrue(status['plan']['hasWork'])
        self.assertFalse(status['event-brief']['hasWork'])
        self.app.reset_crew_chats(self.teams['plan'], reset_event=True)
        self.assertFalse(next(s for s in self.app.scenario_status(self.owner) if s['id'] == 'plan')['hasWork'])

    def test_lounge_deletion_preserves_both_teams(self):
        self.app.onboard(self.owner, {'name': 'Guest', 'skills': ['weather']})
        for scenario in self.teams:
            self.saved(scenario)
        self.finish()
        fresh = self.app.delete_agent(self.owner, {'name': 'Guest'})['agentId']
        for scenario, owner in self.teams.items():
            self.assertEqual(self.app.crew_owner(fresh, scenario), owner)
            self.assertTrue((self.app.workspace(owner) / 'artifacts/report.md').exists())

    def server(self):
        server = create_server('127.0.0.1', 0, self.app)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        self.port = server.server_port

    def request(self, path, scenario='plan', payload=None, token=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        headers = {'Cookie': 'bac_session=' + (token or self.person['token']), 'X-BaC-Scenario': scenario, 'X-BaC-CSRF': self.person['csrf']}
        if payload is not None: headers['Content-Type'] = 'application/json'
        connection.request('GET' if payload is None else 'POST', '/api/' + path, body=json.dumps(payload) if payload is not None else None, headers=headers)
        response = connection.getresponse(); status = response.status; result = json.loads(response.read()); connection.close()
        return status, result

    def test_http_reset_scope_and_scenario_validation(self):
        self.server()
        for scenario, owner in self.teams.items():
            self.app.enqueue(owner, {'kind': 'crew-chat', 'crewRole': 0, 'prompt': scenario})
        self.finish()
        self.assertEqual(self.request('bac-reset', payload={'scope': 'typo'})[0], 400)
        self.assertEqual(self.request('bac-reset', scenario='missing', payload={'scope': 'all'})[0], 400)
        self.assertTrue(self.app.state(self.owner)['crewChats'])
        self.assertEqual(self.request('bac-reset', scenario='event-brief', payload={'scope': 'scenario'})[0], 200)
        self.assertTrue(self.app.state(self.owner)['crewChats'])
        self.assertEqual(self.app.state(self.owner, 'event-brief')['crewChats'], [])

    def test_http_same_named_artifacts_require_the_requested_scenario(self):
        self.server()
        for scenario in self.teams: self.saved(scenario)
        for scenario in self.teams:
            status, result = self.request('file?path=artifacts/report.md', scenario)
            self.assertEqual(status, 200)
            self.assertEqual(result['content'], scenario)
        self.app.reset_crew_chats(self.teams['plan'], reset_event=True)
        self.assertEqual(self.request('file?path=artifacts/report.md', 'plan')[0], 404)
        self.assertEqual(self.request('file?path=artifacts/report.md', 'event-brief')[1]['content'], 'event-brief')

    def test_http_file_and_reset_scopes_do_not_cross_participants(self):
        self.server()
        other = self.app.session()[0]
        for scenario in self.teams:
            self.saved(scenario)
            self.assertEqual(self.request('file?path=artifacts/report.md', scenario, token=other['token'])[0], 404)
            team = self.app.crew_owner(other['id'], scenario)
            (self.app.workspace(team) / 'artifacts/private.md').write_text('Other participant')
        self.assertEqual(self.request('bac-reset', payload={'scope': 'all'})[0], 200)
        for scenario in self.teams:
            self.assertEqual(self.request('file?path=artifacts/private.md', scenario)[0], 404)
            self.assertEqual(self.request('file?path=artifacts/private.md', scenario, token=other['token'])[1]['content'], 'Other participant')


if __name__ == '__main__':
    unittest.main()
