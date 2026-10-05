import json
import tempfile
import unittest
from unittest.mock import patch
from test_studio import Studio, Adapter, Problem
from collaboration_plan import is_plan, read_plan, plan_task


class PlanAdapter(Adapter):
    def __init__(self):
        super().__init__()
        self.plan = {'summary': 'Research, check operations, then write the proposal.', 'tasks': [
            {'role': 8, 'task': 'Research current NVIDIA themes.'},
            {'role': 6, 'task': 'Check a practical sequence and constraints.'},
            {'role': 7, 'task': 'Write the proposal using both contributions.'}]}
        self.reaction_calls = []
        self.after_call = None
        self.fail_role = None

    def respond(self, agent, session, prompt, **kwargs):
        if session.startswith('bac-roundtable-'):
            self.reaction_calls.append((agent, session, prompt))
            return self.profiles[agent]['name'] + ': That result sparks a personal thought.'
        self.calls.append((agent, session, prompt))
        role = int(agent.rsplit('-r', 1)[1]) if '-r' in agent else None
        if self.after_call:
            self.after_call(role, prompt)
        if role == self.fail_role and role is not None:
            raise RuntimeError('Fixture policy denial')
        if session.endswith('-planning'):
            return json.dumps(self.plan)
        if '-checking-' in session:
            return json.dumps({'done':False,'reason':'The remaining assigned work is still required.'})
        if session.endswith('-reviewing'):
            return json.dumps({'done':True,'reason':'The requested contributions are complete; no additional agents are needed.','answer':'A combined proposal grounded in the three saved contributions.'})
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
        self.assertEqual([a.rsplit('-r',1)[1] for a,_,_ in self.adapter.calls], ['0','8','0','6','0','7','0'])
        self.assertIn('Verified contribution from Scout', self.adapter.calls[2][2])
        self.assertIn('Verified contribution from Ada', self.adapter.calls[4][2])
        self.assertIn('Verified contribution from Iris', self.adapter.calls[6][2])
        self.assertEqual(len(self.app.state(self.owner)['agents']), 1)
        self.assertIn('bac-' + self.owner, self.adapter.agents)
        self.assertEqual(len(self.adapter.reaction_calls), 1)
        self.assertEqual(set(job['payload']['collaboration']['outputs']), {'8','6','7'})
        self.assertEqual(len({session for _,session,_ in self.adapter.calls}), 7)
        self.assertEqual(self.app.available_file(self.owner, job['result']['files'][0]).read_text(), job['result']['answer'])

    def test_captain_cannot_skip_planned_code_review_on_saved_file_claim(self):
        self.adapter.plan={'summary':'Build then review','tasks':[
            {'role':5,'task':'Implement the game'}, {'role':4,'task':'Review startup and controls'}]}
        original=self.adapter.respond
        def respond(agent,session,prompt,**kwargs):
            if '-checking-' in session:
                return json.dumps({'done':True,'outcome':'complete','reason':'Cody saved the file.', 'answer':'Ready to play.'})
            return original(agent,session,prompt,**kwargs)
        self.adapter.respond=respond
        result=self.start('/plan Build a browser game');self.app.execute(self.app.next_job())
        plan=self.job(result)['payload']['collaboration']
        self.assertEqual(plan['calledRoles'],[5,4])
        self.assertFalse(plan['checks'][0]['done'])
        self.assertIn('saved file is not evidence',plan['checks'][0]['reason'])

    def test_partial_code_result_can_stop_without_forcing_review(self):
        self.adapter.plan={'summary':'Build then review','tasks':[
            {'role':5,'task':'Implement the game'}, {'role':4,'task':'Review startup and controls'}]}
        original=self.adapter.respond
        def respond(agent,session,prompt,**kwargs):
            if '-checking-' in session:
                return json.dumps({'done':True,'outcome':'partial','reason':'Implementation is blocked.',
                    'remaining':['Implementation'], 'answer':'Implementation is blocked.'})
            return original(agent,session,prompt,**kwargs)
        self.adapter.respond=respond
        result=self.start('/plan Build a browser game');self.app.execute(self.app.next_job())
        plan=self.job(result)['payload']['collaboration']
        self.assertEqual(plan['calledRoles'],[5])
        self.assertEqual(plan['outcome'],'partial')

    def test_normal_message_only_runs_selected_agent(self):
        self.app.enqueue(self.owner, {'kind':'chat','prompt':'Please plan a workshop'})
        self.app.execute(self.app.next_job())
        self.assertEqual([a for a,_,_ in self.adapter.calls], ['bac-' + self.owner])
        self.assertEqual(self.app.state(self.owner)['crewChats'], [])

    def test_normal_crew_chat_only_runs_selected_specialist(self):
        team = self.app.crew_owner(self.owner)
        self.app.enqueue(team, {'kind':'crew-chat','crewRole':6,'prompt':'Check these dates'})
        self.app.execute(self.app.next_job())
        self.assertEqual([a for a,_,_ in self.adapter.calls], [self.app.crew_native_id(team,6)])

    def test_command_in_specialist_chat_is_rejected(self):
        team = self.app.crew_owner(self.owner)
        for role in (4,5,6,7,8):
            for command in ('/plan', ' \n/PLANS'):
                with self.subTest(role=role, command=command), self.assertRaisesRegex(Problem, 'Send /plan to Casey'):
                    self.app.enqueue(team, {'kind':'crew-chat','crewRole':role,'prompt':command+' Write a proposal'})
        self.assertIsNone(self.app.next_job())
        self.assertEqual(self.adapter.calls, [])

    def test_removed_specialists_cannot_be_called_directly_or_in_plan(self):
        team=self.app.crew_owner(self.owner)
        for role in (1,2,3):
            with self.subTest(role=role):
                with self.assertRaisesRegex(Problem,'no longer available'):
                    self.app.enqueue(team,{'kind':'crew-chat','crewRole':role,'prompt':'Hello'})
                with self.assertRaisesRegex(RuntimeError,'invalid or duplicate specialist'):
                    read_plan(json.dumps({'summary':'Invalid retired member','tasks':[{'role':role,'task':'Work'}]}))

    def test_parser_and_empty_command(self):
        for command in ['/plan', '  /plan', '\n \t/PLAN', '/plans', ' \n/PLANS']:
            with self.subTest(command=command):
                self.assertTrue(is_plan(command + '\nTask'))
                self.assertEqual(plan_task(command + '\nTask'), 'Task')
                with self.assertRaises(Problem):self.start(command)
        for prompt in ['Explain /plan','/planet x','/planning x','/plansomething x',None]:
            self.assertFalse(is_plan(prompt))
        self.assertEqual(self.adapter.calls,[])

    def test_alias_routes_to_captain_without_leaving_suffix_in_task(self):
        result = self.start(' \n /PLANS Build a calculator')
        job = self.job(result)
        self.assertEqual(job['payload']['crewRole'], 0)
        self.assertEqual(job['payload']['collaboration']['task'], 'Build a calculator')

    def test_invalid_plan_never_dispatches_a_specialist(self):
        for tasks in [[],[{'role':True,'task':'x'}],[{'role':9,'task':'x'},{'role':6,'task':'y'}], [{'role':1,'task':'x'},{'role':6,'task':'y'}],
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
            if role==8:self.app.decision(team,result['id'],'cancel')
        self.adapter.after_call=stop
        self.app.execute(self.app.next_job())
        self.assertEqual(len(self.adapter.calls),2)
        self.assertEqual(self.job(result)['status'],'cancelled')

    def test_failure_preserves_completed_contributions(self):
        result=self.start();self.adapter.fail_role=6
        with self.assertRaisesRegex(RuntimeError,'policy denial'):self.app.execute(self.app.next_job())
        plan=self.job(result)['payload']['collaboration']
        self.assertEqual(set(plan['outputs']),{'8'})
        self.assertEqual(len(self.adapter.calls),4)
        self.assertNotIn('answer',self.job(result)['result'])

    def test_researcher_is_unprotected_and_retired_dylan_chat_is_rejected(self):
        result=self.start()
        with patch.object(self.adapter,'policy_status',wraps=self.adapter.policy_status) as policy_status:
            self.app.execute(self.app.next_job())
        team=self.app.crew_owner(self.owner)
        dylan=self.app.crew_native_id(team,1)
        avery=self.app.crew_native_id(team,8)
        self.assertEqual(self.adapter.profiles[avery]['protection'],'standard')
        self.assertEqual(self.adapter.profiles[avery]['skills'],['web'])
        self.assertNotIn(dylan,self.adapter.profiles)
        self.assertFalse(any(c.args[0]==avery for c in policy_status.call_args_list))
        self.assertEqual(self.job(result)['status'],'done')
        # Retired event characters cannot be reopened through ordinary team chat.
        with self.assertRaisesRegex(Problem, 'no longer available'):
            self.app.enqueue(team, {'kind':'crew-chat','crewRole':1,'prompt':'Research a demo theme'})

    def test_dylan_is_not_offered_or_dispatched_even_if_captain_selects_him(self):
        result=self.start()
        self.adapter.plan['tasks']=[{'role':6,'task':'Plan'}, {'role':1,'task':'Research'}]
        with self.assertRaisesRegex(RuntimeError,'invalid or duplicate specialist'):
            self.app.execute(self.app.next_job())
        self.assertEqual(len(self.adapter.calls),1)
        prompt=self.adapter.calls[0][2]
        pool,_=json.JSONDecoder().raw_decode(prompt.split('available pool to match the current request: ',1)[1])
        self.assertNotIn('Dylan',[member['name'] for member in pool])
        self.assertIn('Scout',[member['name'] for member in pool])
        self.assertEqual(self.job(result)['payload']['collaboration']['outputs'],{})

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

    def test_plan_reads_source_conversation_and_captain_followups(self):
        self.app.enqueue(self.owner, {'kind':'chat','prompt':'Use Zurich, with a budget of CHF 800.'})
        self.app.execute(self.app.next_job())
        first=self.start('/plan Use the constraints we discussed.')
        self.app.execute(self.app.next_job())
        self.assertIn('CHF 800', self.adapter.calls[1][2])
        self.assertEqual(self.job(first)['payload']['collaboration']['origin'], {'owner':self.owner,'role':None})
        team=self.app.crew_owner(self.owner)
        self.adapter.calls.clear()
        self.app.enqueue(team, {'kind':'crew-chat','crewRole':0,'prompt':'/plan Make that proposal shorter.'})
        self.app.execute(self.app.next_job())
        self.assertIn('A combined proposal', self.adapter.calls[0][2])
        self.assertIn('Use the constraints we discussed.', self.adapter.calls[0][2])
        self.adapter.calls.clear()
        self.app.enqueue(team, {'kind':'crew-chat','crewRole':0,'prompt':'What did we decide?'})
        self.app.execute(self.app.next_job())
        self.assertEqual(len(self.adapter.calls),1)
        self.assertIn('A combined proposal', self.adapter.calls[0][2])

    def test_personal_followup_knows_team_response_without_delegation(self):
        self.start();self.app.execute(self.app.next_job());self.adapter.calls.clear()
        self.app.enqueue(self.owner, {'kind':'chat','prompt':'Summarize their proposal.'})
        self.app.execute(self.app.next_job())
        self.assertEqual(len(self.adapter.calls),1)
        self.assertEqual(self.adapter.calls[0][0],'bac-'+self.owner)
        self.assertIn('A combined proposal',self.adapter.calls[0][2])

    def test_history_does_not_read_other_personal_agents_or_accounts(self):
        outsider=self.app.session()[0]['id']
        self.app.onboard(outsider, {'name':'Other','skills':['web']})
        self.app.enqueue(outsider, {'kind':'chat','prompt':'PRIVATE_OTHER_ACCOUNT'})
        self.app.execute(self.app.next_job())
        with self.app.db() as db:
            participant=db.execute('SELECT participant FROM agents WHERE id=?',(self.owner,)).fetchone()[0]
        other=self.app.add_agent(participant, {'name':'Sibling','skills':['web']})['agentId']
        self.app.enqueue(other, {'kind':'chat','prompt':'PRIVATE_OTHER_AGENT'})
        self.app.execute(self.app.next_job());self.adapter.calls.clear()
        self.start();self.app.execute(self.app.next_job())
        self.assertTrue(all('PRIVATE_OTHER' not in p for _,_,p in self.adapter.calls))

    def test_history_is_bounded_and_reset_clears_plan_context(self):
        first=self.start('/plan UNIQUE_OLD_PLAN');self.app.execute(self.app.next_job())
        team=self.app.crew_owner(self.owner)
        with self.app.db() as db:
            db.execute('UPDATE jobs SET result=? WHERE id=?',(json.dumps({'answer':'x'*100000}),first['id']))
        context=self.app.conversation_context(team,0,float('inf'),'new')
        self.assertLess(len(context),24500)
        self.app.reset_crew_chats(self.owner)
        self.app.enqueue(team, {'kind':'crew-chat','crewRole':0,'prompt':'/plan A fresh request'})
        self.adapter.calls.clear();self.app.execute(self.app.next_job())
        self.assertNotIn('UNIQUE_OLD_PLAN',self.adapter.calls[0][2])

    def test_unfinished_or_future_jobs_are_not_context(self):
        result=self.start('/plan NOT_FINISHED')
        team=self.app.crew_owner(self.owner)
        self.assertEqual(self.app.conversation_context(team,0,float('inf'),'next'),'')
        self.app.execute(self.app.next_job())
        self.assertEqual(self.app.conversation_context(team,0,0,'next'),'')
        self.assertEqual(self.app.conversation_context(team,0,float('inf'),result['id']),'')
