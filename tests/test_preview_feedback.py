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
from event_scenario import EventScenario
from agent_runtime import GatewayError
from telemetry import Reply
import container_remove
from test_agent_workflow import AgentToolsAdapter
from test_researched_event import SOURCES
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
        self.assertEqual(self.app.state(self.owner, 'event-brief')['fileWorkspaces'], [])
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

    def test_preparation_and_reset_state(self):
        self.assertFalse(any(s['hasWork'] for s in self.app.scenario_status(self.owner)))
        self.app.prepare_demo(self.teams['event-brief'],{'enabledRoles':[0]})
        self.assertTrue(next(s for s in self.app.scenario_status(self.owner) if s['id']=='event-brief')['hasWork'])
        self.app.reset_crew_chats(self.teams['event-brief'],reset_event=True)
        self.assertFalse(any(s['hasWork'] for s in self.app.scenario_status(self.owner)))

    def test_nested_specialist_files_are_browsable_and_resettable_without_chat(self):
        workspace = self.app.workspace(self.teams['plan'], 5)
        (workspace / 'artifacts/site').mkdir()
        (workspace / 'artifacts/site/index.html').write_text('<h1>Saved prototype</h1>')
        # Never follow a link, even to another workspace in the same account.
        (workspace / 'artifacts/other').symlink_to(self.app.workspace(self.teams['event-brief']), target_is_directory=True)
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


class EventRecoveryTests(unittest.TestCase):
    def call(self, failure='output-limit', second_failure=False, stopped=False):
        self.payload={}
        self.error=GatewayError('Stopped',failure)
        self.error.activity={'available':True,'calls':[{'id':'first','tool':'write','status':'completed'}]}
        reply=Reply('Saved',{})
        reply.activity={'available':True,'calls':[{'id':'second','tool':'read','status':'completed'}]}
        self.fake=SimpleNamespace(protected_response=Mock(side_effect=[self.error,GatewayError('Stopped','output-limit') if second_failure else reply]),
            files=Mock(return_value=[{'path':'artifacts/saved.md'}]),event=Mock(),stop_checkpoint=Mock(return_value=stopped))
        return EventScenario.event_response(self.fake,'job',self.payload,3,'agent','original','Write the assigned section','owner',3)

    def test_recovers_once_in_fresh_context_and_retains_observations(self):
        answer=self.call()
        self.assertEqual(len(self.fake.protected_response.call_args_list),2)
        args=self.fake.protected_response.call_args.args
        self.assertEqual(args[1],'original-output-recovery')
        self.assertIn('artifacts/saved.md',args[2])
        self.assertIn('do not restart the whole task',args[2])
        self.assertEqual([c['id'] for c in answer.activity['calls']],['first','second'])
        self.fake.protected_response.side_effect=GatewayError('again','output-limit')
        with self.assertRaises(GatewayError):
            EventScenario.event_response(self.fake,'job',self.payload,3,'agent','another','Fix a section','owner',3)
        self.assertEqual(self.fake.protected_response.call_count,3)

    def test_repeated_limit_stops(self):
        with self.assertRaisesRegex(GatewayError,'after one shorter retry'):
            self.call(second_failure=True)
        self.assertEqual(self.payload['outputLimitRecovery']['3']['status'],'failed')

    def test_network_failure_and_stop_do_not_replay(self):
        for reason,stopped in [('request_failed',False),('output-limit',True)]:
            with self.subTest(reason=reason,stopped=stopped),self.assertRaises(GatewayError):
                self.call(reason,stopped=stopped)
            self.assertEqual(self.fake.protected_response.call_count,1)


class SavedWorkLimitAdapter(AgentToolsAdapter):
    def __init__(self, repeat=False):
        super().__init__()
        self.repeat = repeat
        self.limited = set()
        self.recovered = []

    def respond(self, agent, session, prompt):
        stage = int(agent.rsplit('-r', 1)[1])
        if session.endswith('-output-recovery'):
            self.recovered.append(stage)
            if self.repeat:
                raise GatewayError('Second output limit', 'output-limit')
            # A real recovery must be able to validate previous writes without
            # repeating searches or resaving already valid deliverables.
            result = Reply('Inspected the saved deliverables. They are complete.', {})
            result.activity = {'available': True, 'calls': []}
            return result
        answer = super().respond(agent, session, prompt)
        if stage in (1, 2, 3) and stage not in self.limited and not prompt.startswith('LINKEDIN-FIRST:'):
            self.limited.add(stage)
            error = GatewayError('Final receipt truncated', 'output-limit')
            error.activity = answer.activity
            raise error
        return answer


class EventRecoveryFlowTests(unittest.TestCase):
    def test_saved_work_survives_limits_in_parallel_stages_and_page_authoring(self):
        for repeat in (False, True):
            with self.subTest(repeat=repeat), tempfile.TemporaryDirectory() as folder:
                adapter = SavedWorkLimitAdapter(repeat)
                app = Studio(folder, adapter, start_worker=False)
                owner = app.session()[0]['id']
                team = app.crew_owner(owner, 'event-brief')
                prep = app.prepare_demo(team, {'enabledRoles': [0, 1, 2, 3]})
                while (row := app.next_job()) is not None: app.execute(row)
                job = app.enqueue(team, {'kind': 'crew', 'preset': True, 'workflow': 'showcase',
                    'executionMode': 'agent-led-v1', 'brief': {'schema': 2, 'themeCount': 2},
                    'enabledRoles': [0, 1, 2, 3], 'preparationId': prep['id']})
                with patch('nvidia_research.search_one', return_value=copy.deepcopy(SOURCES['sources'])), patch('event_agent_tools.read_article', return_value='Fixture article read by the agent tool.'):
                    # Exercise the worker's real error-to-state handling, then exit
                    # as soon as the disposable queue is empty.
                    with patch.object(app.signal, 'wait', side_effect=lambda timeout: app.stop.set()):
                        app.work()
                result = app.evidence(team, job['id'])['mission']
                self.assertEqual(result['status'], 'error' if repeat else 'done', result['result'])
                self.assertEqual(len(adapter.recovered), len(set(adapter.recovered)), 'At most one output-limit recovery per role')
                self.assertTrue(app.files(team, 1), 'Research files survive either outcome')
                if not repeat:
                    self.assertEqual(set(adapter.recovered), {1, 2, 3})
                    self.assertTrue(result['payload']['website']['path'])
                    self.assertEqual(set(result['payload']['outputs']), {'0', '1', '2', '3'})
                else:
                    self.assertIn('after one shorter retry', json.dumps(result['result']))


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
