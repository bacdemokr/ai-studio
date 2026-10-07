"""Regressions for goal routing, scoped files, reset state and bounded recovery."""
import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from test_scenario_boundaries import ScenarioBoundaryTests
from test_container_remove import Engine
from collaboration_plan import is_plan, plan_task
from event_scenario import EventScenario
from agent_runtime import GatewayError
from telemetry import Reply
import container_remove


class FeedbackBoundaries(unittest.TestCase):
    setUp = ScenarioBoundaryTests.setUp
    server = ScenarioBoundaryTests.server
    request = ScenarioBoundaryTests.request

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


class StopTests(unittest.TestCase):
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
            bad=copy.deepcopy(owned);bad['Mounts']=[]
            engine=Engine(containers=[owned,bad])
            with self.assertRaises(RuntimeError):container_remove.stop(engine,gateway)
            self.assertFalse(any(c[0]=='POST' for c in engine.calls))

if __name__=='__main__':unittest.main()
