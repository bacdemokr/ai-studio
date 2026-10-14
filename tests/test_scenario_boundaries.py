"""Open Task ownership, reset and retired-route checks with isolated HTTP."""
import http.client,json,tempfile,threading,unittest
from unittest.mock import patch
from test_studio import Studio,Adapter,Problem
from serve import create_server
import team_models

class ScenarioBoundaryTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.adapter=Adapter();self.app=Studio(folder.name,self.adapter,start_worker=False)
        self.person=self.app.session()[0];self.owner=self.person['id']
        self.teams={'plan':self.app.crew_owner(self.owner)}
        self.other=self.app.session()[0];self.other_team=self.app.crew_owner(self.other['id'])

    def finish(self):
        while (row := self.app.next_job()) is not None:
            self.app.execute(row)

    def saved(self, scenario, name='report.md'):
        path = self.app.workspace(self.teams[scenario]) / 'artifacts' / name
        path.write_text(scenario)
        return path

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

    def test_retired_routes_cannot_allocate_or_run_work(self):
        self.server()
        with self.app.db() as db:before=db.execute('SELECT COUNT(*) FROM agents').fetchone()[0]
        for path,data in [('prepare-demo',{}),('event-plan',{}),('survey-replan',{}),('jobs',{'kind':'crew'}),('jobs',{'kind':'prepare'})]:
            self.assertEqual(self.request(path,payload=data)[0],410,path)
        for path in ('event-catalog','survey-report'):
            self.assertEqual(self.request(path)[0],410,path)
        self.assertEqual(self.request('state','event-brief')[0],400)
        with self.app.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM agents').fetchone()[0],before)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],0)
        self.assertEqual(self.adapter.calls,[])

    def test_reset_is_scoped_to_open_task_and_preserves_hired_files(self):
        self.app.onboard(self.owner,{'name':'Guest','skills':[]})
        personal=self.app.workspace(self.owner)/'artifacts/personal.md';personal.write_text('Keep')
        other=self.app.workspace(self.other_team)/'artifacts/other.md';other.write_text('Other account')
        self.saved('plan');self.server()
        self.assertEqual(self.request('bac-reset',payload={'scope':'typo'})[0],400)
        self.assertEqual(self.request('bac-reset',payload={'scope':'scenario'})[0],200)
        self.assertFalse((self.app.workspace(self.teams['plan'])/'artifacts/report.md').exists())
        self.assertEqual(personal.read_text(),'Keep');self.assertEqual(other.read_text(),'Other account')

    def test_files_do_not_cross_account_or_retired_room(self):
        self.saved('plan');self.server()
        self.assertEqual(self.request('file?path=artifacts/report.md')[1]['content'],'plan')
        self.assertEqual(self.request('file?path=artifacts/report.md',token=self.other['token'])[0],404)
        self.assertEqual(self.request('file?path=artifacts/report.md','event-brief')[0],400)

    def test_only_current_slots_receive_new_workspaces(self):
        team=self.teams['plan']
        with self.app.db() as db:roles={r[0] for r in db.execute('SELECT role FROM crew_resources WHERE owner=?',(team,))}
        self.assertEqual(roles,{0,4,5,6,7,8})
        for role in (1,2,3):
            self.assertFalse(self.app.workspace(team,role).exists())
            with self.assertRaises(Problem):self.app.enqueue(team,{'kind':'crew-chat','crewRole':role,'prompt':'Hi'})
