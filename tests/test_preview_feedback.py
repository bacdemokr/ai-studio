"""Regressions for goal routing, scoped files, reset state and bounded recovery."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_scenario_boundaries as boundaries
from test_container_remove import Engine
from collaboration_plan import is_plan, plan_task
from agent_runtime import GatewayError
from telemetry import Reply
import container_remove
from studio import Studio
import studio


class FeedbackBoundaries(unittest.TestCase):
    setUp = boundaries.ScenarioBoundaryTests.setUp
    server = boundaries.ScenarioBoundaryTests.server
    request = boundaries.ScenarioBoundaryTests.request

    def test_file_visibility_tracks_current_agent_and_scenario(self):
        self.assertFalse(self.app.state(self.owner)['hasFiles'])
        self.assertEqual(self.app.state(self.owner)['fileWorkspaces'], [])
        personal = self.app.workspace(self.owner) / 'inbox/nested'
        personal.mkdir(parents=True)
        document = personal / 'notes.md'
        document.write_text('Personal upload')
        self.assertTrue(self.app.state(self.owner)['hasFiles'])
        result = self.app.workspace(self.teams['plan'], 5) / 'artifacts/result.md'
        result.write_text('Specialist result')
        self.assertEqual(self.app.state(self.owner)['fileWorkspaces'], ['5'])
        self.assertEqual(self.app.state(self.other['id'])['fileWorkspaces'], [])
        document.unlink()
        result.unlink()
        self.assertFalse(self.app.state(self.owner)['hasFiles'])
        self.assertEqual(self.app.state(self.owner)['fileWorkspaces'], [])

    def test_goal_aliases_and_routing(self):
        for command in ('/goal', '/goals', '/plan', '/plans', '/GOAL'):
            self.assertTrue(is_plan(' \n' + command + '\nBuild a game'))
            self.assertEqual(plan_task(' \n' + command + '\nBuild a game'), 'Build a game')
        for command in ('/goaltender', '/planet', 'Please /goal', '/goalpost'):
            self.assertFalse(is_plan(command))
        self.app.onboard(self.owner, {'name': 'Guest', 'skills': ['web']})
        self.server()
        for scenario, kind, role in [('plan','chat',0),('plan','crew-chat',5),('event-brief','crew-chat',0)]:
            self.assertEqual(self.request('jobs', scenario, {'kind':kind,'crewRole':role,'prompt':'/goal Make a page'})[0],400)
        self.assertEqual(self.request('jobs','plan',{'kind':'crew-chat','crewRole':0,'prompt':'/goal Make a page'})[0],200)

    def test_files_are_scoped_to_account_scenario_and_role(self):
        for scenario, team in self.teams.items():
            (self.app.workspace(team,0)/'artifacts/same.md').write_text(scenario)
        self.server()
        for scenario in self.teams:
            status,result=self.request('workspace-files?workspace=0',scenario)
            self.assertEqual(status,200)
            self.assertIn('artifacts/same.md',[f['path'] for f in result['files']])
            status,result=self.request('file?workspace=0&path=artifacts/same.md',scenario)
            self.assertEqual(result['content'],scenario)
        other=self.app.session()[0]
        self.assertEqual(self.request('file?workspace=0&path=artifacts/same.md',token=other['token'])[0],404)
        self.assertEqual(self.request('file?workspace=0&path=artifacts/../../api.cfg')[0],400)
        self.assertEqual(self.request('workspace-files?workspace=5','event-brief')[0],400)
        self.assertEqual(self.request('workspace-files?workspace=bogus')[0],400)


    def test_nested_specialist_files_are_browsable_and_resettable_without_chat(self):
        workspace = self.app.workspace(self.teams['plan'], 5)
        (workspace / 'artifacts/site').mkdir()
        (workspace / 'artifacts/site/index.html').write_text('<h1>Saved prototype</h1>')
        # Never follow a link, even to another workspace in the same account.
        (workspace / 'artifacts/other').symlink_to(self.app.workspace(self.other_team), target_is_directory=True)
        (workspace / 'artifacts/alias.html').symlink_to(workspace / 'artifacts/site/index.html')
        self.server()
        status, result = self.request('workspace-files?workspace=5')
        self.assertEqual(status, 200)
        self.assertEqual([f['path'] for f in result['files']], ['artifacts/site/index.html'])
        self.assertEqual(self.request('file?workspace=5&path=artifacts/site/index.html')[1]['content'], '<h1>Saved prototype</h1>')
        self.assertTrue(next(s for s in self.app.scenario_status(self.owner) if s['id'] == 'plan')['hasWork'])
        self.app.reset_crew_chats(self.teams['plan'], reset_event=True)
        self.assertFalse(next(s for s in self.app.scenario_status(self.owner) if s['id'] == 'plan')['hasWork'])
        self.assertEqual(self.request('workspace-files?workspace=5')[1]['files'], [])

    def test_file_removed_during_listing_does_not_break_remaining_results(self):
        workspace = self.app.workspace(self.teams['plan'])
        (workspace / 'artifacts/keep.md').write_text('Keep this result')
        (workspace / 'artifacts/vanish.md').write_text('Reset removes this result')
        validate = studio.safe_file
        def concurrent_removal(base, relative, exists=False):
            path = validate(base, relative, exists)
            if path.name == 'vanish.md': path.unlink()
            return path
        with patch('studio.safe_file', side_effect=concurrent_removal):
            files = self.app.files(self.teams['plan'], recursive=True)
        self.assertEqual([f['path'] for f in files], ['artifacts/keep.md'])








class StopTests(unittest.TestCase):
    def test_failed_stop_still_stops_other_sandboxes_and_keeps_resume_record(self):
        with tempfile.TemporaryDirectory() as folder:
            gateway = Path(folder)
            (gateway / '.bac-gateway.json').write_text('{"owner":"bac-demo","schema":1}')
            def sandbox(ident):
                return {'Id': ident, 'State': 'running', 'Labels': {container_remove.MANAGER: 'openshell', container_remove.NAMESPACE: 'bac-demo'}, 'Mounts': [{'Type': 'bind', 'Source': str(gateway / 'cache')}]}
            engine = Engine(containers=[sandbox('first'), sandbox('second')])
            engine.fail = ('POST', '/containers/first/stop?t=45')
            with self.assertRaises(RuntimeError):
                container_remove.stop(engine, gateway)
            self.assertIn(('POST', '/containers/second/stop?t=45'), engine.calls)
            self.assertEqual(container_remove.stopped_sandboxes(gateway), {'first', 'second'})
            engine.fail = None
            container_remove.stop(engine, gateway)
            engine.fail = ('POST', '/containers/second/start')
            with self.assertRaises(RuntimeError):
                container_remove.resume(engine, gateway)
            self.assertEqual(container_remove.stopped_sandboxes(gateway), {'first', 'second'})
            engine.fail = None
            container_remove.resume(engine, gateway)
            self.assertFalse((gateway / container_remove.STOPPED_SANDBOXES).exists())

    def test_gateway_symlink_is_rejected_even_without_remaining_containers(self):
        with tempfile.TemporaryDirectory() as folder:
            actual = Path(folder) / 'actual'; actual.mkdir()
            gateway = Path(folder) / 'gateway'; gateway.symlink_to(actual, target_is_directory=True)
            container_remove.save_stopped_sandboxes(actual, {'old'})
            before = (actual / container_remove.STOPPED_SANDBOXES).stat().st_mtime_ns
            with self.assertRaises(RuntimeError):
                container_remove.stop(Engine(), gateway)
            self.assertEqual((actual / container_remove.STOPPED_SANDBOXES).stat().st_mtime_ns, before)

    def test_stops_owned_sandboxes_preserves_other_work_and_data(self):
        with tempfile.TemporaryDirectory() as folder:
            gateway=Path(folder)
            (gateway/'.bac-gateway.json').write_text('{"owner":"bac-demo","schema":1}')
            (gateway/'saved').write_text('keep')
            owned={'Id':'sandbox','State':'running','Labels':{container_remove.MANAGER:'openshell',container_remove.NAMESPACE:'bac-demo'},'Mounts':[{'Type':'bind','Source':str(gateway/'cache')}]}
            engine=Engine(containers=[owned,{'Id':'other','State':'running','Labels':{},'Mounts':[]}])
            container_remove.stop(engine,gateway)
            self.assertEqual([c for c in engine.calls if c[0]!='GET'],[('POST','/containers/sandbox/stop?t=45')])
            self.assertEqual((gateway/'saved').read_text(),'keep')
            # A pre-existing stopped sandbox is not ours to resume implicitly.
            dormant=copy.deepcopy(owned);dormant.update(Id='dormant',State='exited')
            engine.containers.append(dormant)
            container_remove.resume(engine,gateway)
            self.assertIn(('POST','/containers/sandbox/start'),engine.calls)
            self.assertNotIn(('POST','/containers/dormant/start'),engine.calls)
            self.assertFalse((gateway/container_remove.STOPPED_SANDBOXES).exists())
            container_remove.resume(engine,gateway)  # Idempotent second startup.
            bad=copy.deepcopy(owned);bad['Mounts']=[]
            engine=Engine(containers=[owned,bad])
            with self.assertRaises(RuntimeError):container_remove.stop(engine,gateway)
            self.assertFalse(any(c[0]=='POST' for c in engine.calls))

if __name__=='__main__':unittest.main()
