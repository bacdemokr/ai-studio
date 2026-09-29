import json
import tempfile
import unittest
from unittest.mock import patch
from test_studio import Studio, Adapter, Problem
from collaboration_plan import is_plan, read_plan


class PlanAdapter(Adapter):
    def __init__(self):
        super().__init__()
        self.plan = {'summary': 'Research, check operations, then write the proposal.', 'tasks': [
            {'role': 1, 'task': 'Research current NVIDIA themes.'},
            {'role': 2, 'task': 'Check a practical sequence and constraints.'},
            {'role': 3, 'task': 'Write the proposal using both contributions.'}]}
        self.after_call = None
        self.fail_role = None

    def respond(self, agent, session, prompt, **kwargs):
        self.calls.append((agent, session, prompt))
        role = int(agent.rsplit('-r', 1)[1]) if '-r' in agent else None
        if self.after_call:
            self.after_call(role, prompt)
        if role == self.fail_role and role is not None:
            raise RuntimeError('Fixture policy denial')
        if session.endswith('-planning'):
            return json.dumps(self.plan)
        if session.endswith('-reviewing'):
            return 'A combined proposal grounded in the three saved contributions.'
        return 'Verified contribution from ' + self.profiles[agent]['name']


class CollaborationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.adapter = PlanAdapter()
        self.app = Studio(self.temp.name, self.adapter, start_worker=False)
        self.owner = self.app.session()[0]['id']
        self.app.onboard(self.owner, {'name': 'Personal', 'skills': ['web']})

    def start(self, prompt='/plan Prepare a practical NVIDIA workshop proposal.'):
        result = self.app.enqueue(self.owner, {'kind':'chat', 'prompt':prompt})
        return result

    def job(self, result):
        return next(j for j in self.app.state(self.owner)['crewChats'] if j['id'] == result['id'])

    def test_command_routes_to_captain_and_runs_real_handoffs(self):
        result = self.start()
        self.assertTrue(result['collaboration'])
        self.app.execute(self.app.next_job())
        job = self.job(result)
        self.assertEqual(job['status'], 'done')
        self.assertEqual([a.rsplit('-r',1)[1] for a,_,_ in self.adapter.calls], ['0','1','2','3','0'])
        self.assertIn('Verified contribution from Dylan', self.adapter.calls[2][2])
        self.assertIn('Verified contribution from Alex', self.adapter.calls[3][2])
        self.assertIn('Verified contribution from Morgan', self.adapter.calls[4][2])
        self.assertEqual(len(self.app.state(self.owner)['agents']), 1)
        self.assertNotIn('bac-' + self.owner, self.adapter.agents)
        self.assertEqual(set(job['payload']['collaboration']['outputs']), {'1','2','3'})
        self.assertEqual(len({session for _,session,_ in self.adapter.calls}), 5)
        self.assertEqual(self.app.available_file(self.owner, job['result']['files'][0]).read_text(), job['result']['answer'])

    def test_normal_message_only_runs_selected_agent(self):
        self.app.enqueue(self.owner, {'kind':'chat','prompt':'Please plan a workshop'})
        self.app.execute(self.app.next_job())
        self.assertEqual([a for a,_,_ in self.adapter.calls], ['bac-' + self.owner])
        self.assertEqual(self.app.state(self.owner)['crewChats'], [])

    def test_normal_crew_chat_only_runs_selected_specialist(self):
        team = self.app.crew_owner(self.owner)
        self.app.enqueue(team, {'kind':'crew-chat','crewRole':2,'prompt':'Check these dates'})
        self.app.execute(self.app.next_job())
        self.assertEqual([a for a,_,_ in self.adapter.calls], [self.app.crew_native_id(team,2)])

    def test_command_in_specialist_chat_still_uses_captain(self):
        team = self.app.crew_owner(self.owner)
        result = self.app.enqueue(team, {'kind':'crew-chat','crewRole':3,'prompt':'/plan Write a proposal'})
        self.app.execute(self.app.next_job())
        self.assertEqual(self.job(result)['payload']['crewRole'],0)
        self.assertEqual(self.adapter.calls[0][0],self.app.crew_native_id(team,0))

    def test_parser_and_empty_command(self):
        for prompt in ['/plan x',' /PLAN\nTask ']:self.assertTrue(is_plan(prompt))
        for prompt in ['Explain /plan','/planet x','/planning x',None]:self.assertFalse(is_plan(prompt))
        with self.assertRaises(Problem):self.start('/plan')
        self.assertEqual(self.adapter.calls,[])

    def test_invalid_plan_never_dispatches_a_specialist(self):
        for tasks in [[],[{'role':True,'task':'x'}],[{'role':4,'task':'x'}],
                      [{'role':1,'task':'x'},{'role':1,'task':'y'}]]:
            with self.subTest(tasks=tasks), self.assertRaises(RuntimeError):
                read_plan(json.dumps({'summary':'Plan','tasks':tasks}))
        result = self.start()
        self.adapter.plan = {'summary':'Invalid','tasks':[{'role':99,'task':'x'}]}
        with self.assertRaises(RuntimeError):self.app.execute(self.app.next_job())
        self.assertEqual(len(self.adapter.calls),1)
        self.assertEqual(self.job(result)['payload']['collaboration']['outputs'],{})

    def test_stop_after_specialist_blocks_remaining_calls(self):
        result = self.start()
        team = self.app.crew_owner(self.owner)
        def stop(role, prompt):
            if role==1:self.app.decision(team,result['id'],'cancel')
        self.adapter.after_call=stop
        self.app.execute(self.app.next_job())
        self.assertEqual(len(self.adapter.calls),2)
        self.assertEqual(self.job(result)['status'],'cancelled')

    def test_failure_preserves_completed_contributions(self):
        result=self.start();self.adapter.fail_role=2
        with self.assertRaisesRegex(RuntimeError,'policy denial'):self.app.execute(self.app.next_job())
        plan=self.job(result)['payload']['collaboration']
        self.assertEqual(set(plan['outputs']),{'1'})
        self.assertEqual(len(self.adapter.calls),3)
        self.assertNotIn('answer',self.job(result)['result'])

    def test_dylan_uses_existing_protected_runtime_and_no_added_grants(self):
        result=self.start()
        with patch.object(self.app,'protected_response',wraps=self.app.protected_response) as response:
            self.app.execute(self.app.next_job())
        team=self.app.crew_owner(self.owner);dylan=self.app.crew_native_id(team,1)
        self.assertEqual(self.adapter.profiles[dylan]['protection'],'openshell')
        self.assertTrue(any(c.args[0]==dylan and c.args[3:]==(team,1) for c in response.call_args_list))
        self.assertEqual(self.job(result)['status'],'done')

    def test_revoke_stays_revoked_and_policy_edits_are_fenced(self):
        team=self.app.crew_owner(self.owner)
        self.app.policy_change(team,{'permission':'host:blogs.nvidia.com','allow':False},1)
        self.start()
        with self.assertRaises(Problem):self.app.policy_change(team,{'permission':'host:blogs.nvidia.com','allow':True},1)
        self.app.execute(self.app.next_job())
        self.assertEqual(self.adapter.permissions[self.app.crew_native_id(team,1)],[])

    def test_ownership_persistence_reset_and_team_busy(self):
        result=self.start();team=self.app.crew_owner(self.owner)
        with self.assertRaises(Problem):self.start()
        with self.assertRaises(Problem):self.app.reset_crew_chats(self.owner)
        outsider=self.app.session()[0]['id']
        with self.assertRaises(Problem):self.app.job_owner(outsider,result['id'])
        self.app.execute(self.app.next_job())
        self.assertEqual(self.app.state(outsider)['crewChats'],[])
        restarted=Studio(self.temp.name,self.adapter,start_worker=False)
        self.assertEqual(len(restarted.state(self.owner)['crewChats']),1)
        self.app.reset_crew_chats(self.owner)
        self.assertEqual(self.app.state(self.owner)['crewChats'],[])

    def test_personal_uploads_are_not_copied_to_the_team(self):
        self.app.upload(self.owner,{'name':'private.txt','content':'private uploaded document'})
        self.start();self.app.execute(self.app.next_job())
        self.assertTrue(all('private uploaded document' not in p for _,_,p in self.adapter.calls))
        team=self.app.crew_owner(self.owner)
        for role in range(4):self.assertFalse((self.app.workspace(team,role)/'inbox/private.txt').exists())
