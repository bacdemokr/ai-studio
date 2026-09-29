"""Adversarial collaboration lifecycle and handoff coverage."""
import json
import unittest
import concurrent.futures
import test_collaboration_plan as fixture
from test_studio import Problem

class PlanEdgeCases(unittest.TestCase):
    setUp=fixture.CollaborationTests.setUp
    start=fixture.CollaborationTests.start
    job=fixture.CollaborationTests.job

    def test_deleting_personal_agent_cannot_start_plan(self):
        with self.app.db() as db:db.execute('UPDATE agents SET deleting=1 WHERE id=?',(self.owner,))
        with self.assertRaises(Problem):self.start()
        self.assertEqual(self.app.state(self.owner)['crewChats'],[])

    def test_bac_reset_stops_running_plan_and_discards_late_reply(self):
        import threading
        entered,release=threading.Event(),threading.Event()
        original=self.adapter.respond
        def respond(*args,**kwargs):
            entered.set();release.wait(5)
            return original(*args,**kwargs)
        self.adapter.respond=respond
        result=self.start();row=self.app.next_job()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            execution=pool.submit(self.app.execute,row)
            try:
                self.assertTrue(entered.wait(5))
                reset=self.app.reset_crew_chats(self.owner,reset_event=True)
                self.assertTrue(reset['resetting'])
                self.assertEqual(self.job(result)['status'],'stopping')
                with self.assertRaises(Problem):self.start('/plan New work')
            finally:release.set()
            execution.result(timeout=5)
        self.app.finish_pending_bac_resets()
        self.assertEqual(self.app.state(self.owner)['crewChats'],[])
        self.assertEqual(len(self.adapter.calls),1)
        self.app.event(result['id'],'Late reply','',status='done',result=json.dumps({'answer':'STALE'}))
        self.assertEqual(self.app.state(self.owner)['crewChats'],[])
        fresh=self.start('/plan Fresh work')
        self.app.reset_crew_chats(self.owner,reset_event=True,pending_only=True)
        self.assertEqual(self.job(fresh)['status'],'queued')

    def test_pending_bac_reset_survives_restart_and_preserves_personal_chat(self):
        self.app.enqueue(self.owner,{'kind':'chat','prompt':'Keep personal history'})
        self.app.execute(self.app.next_job())
        self.start();self.app.next_job()
        self.assertTrue(self.app.reset_crew_chats(self.owner,reset_event=True)['resetting'])
        from test_studio import Studio
        restarted=Studio(self.temp.name,self.adapter,start_worker=False,recover=True)
        restarted.finish_pending_bac_resets()
        state=restarted.state(self.owner)
        self.assertEqual(state['crewChats'],[])
        self.assertTrue(any(j['payload'].get('prompt')=='Keep personal history' for j in state['jobs']))

    def test_crew_remains_usable_while_personal_agent_is_deleting(self):
        team=self.app.crew_owner(self.owner)
        with self.app.db() as db:db.execute('UPDATE agents SET deleting=1 WHERE id=?',(self.owner,))
        for prompt in ('Hello Casey','/plan Prepare a proposal'):
            result=self.app.enqueue(team,{'kind':'crew-chat','crewRole':0,'prompt':prompt})
            self.app.execute(self.app.next_job())
            self.assertEqual(self.job(result)['status'],'done')
        self.assertEqual(self.app.policy_profile(team,1)['name'],'Dylan')
        with self.assertRaises(Problem):self.app.enqueue(self.owner,{'kind':'chat','prompt':'Hello'})

    def test_specialist_followup_remembers_own_contribution(self):
        self.start();self.app.execute(self.app.next_job());self.adapter.calls.clear()
        team=self.app.crew_owner(self.owner)
        self.app.enqueue(team,{'kind':'crew-chat','crewRole':2,'prompt':'Explain your last contribution.'})
        self.app.execute(self.app.next_job())
        self.assertEqual(len(self.adapter.calls),1)
        self.assertIn('Verified contribution from Alex',self.adapter.calls[0][2])

    def test_specialist_plan_continuation_has_previous_work(self):
        self.start();self.app.execute(self.app.next_job());self.adapter.calls.clear()
        team=self.app.crew_owner(self.owner)
        self.app.enqueue(team,{'kind':'crew-chat','crewRole':3,'prompt':'/plan Revise your proposal.'})
        self.app.execute(self.app.next_job())
        self.assertIn('Verified contribution from Morgan',self.adapter.calls[0][2])

    def test_failed_plan_followup_includes_completed_work_and_failure(self):
        first=self.start();self.adapter.fail_role=2
        try:self.app.execute(self.app.next_job())
        except RuntimeError as error:self.app.event(first['id'],'Failed',str(error),status='error',result=json.dumps({'error':str(error)}))
        self.adapter.fail_role=None;self.adapter.calls.clear()
        self.start('/plan Continue from the completed research.');self.app.execute(self.app.next_job())
        prompt=self.adapter.calls[0][2]
        self.assertIn('Verified contribution from Avery',prompt)
        self.assertIn('error',prompt)

    def test_webpage_is_handed_to_next_specialist_not_just_its_filename(self):
        self.adapter.plan['tasks']=[{'role':3,'task':'Write HTML'},{'role':2,'task':'Review the written HTML'}]
        def respond(agent,session,prompt,**kwargs):
            if session.startswith('bac-roundtable-'):return 'A personal reaction.'
            self.adapter.calls.append((agent,session,prompt))
            if '-checking-' in session:return json.dumps({'done':False,'reason':'Review is required.'})
            if session.endswith('-planning'):return json.dumps(self.adapter.plan)
            if session.endswith('-reviewing'):return json.dumps({'done':True,'reason':'Complete.','answer':'Combined'})
            if agent.endswith('-r3'):
                (self.adapter.agents[agent]/'artifacts'/'index.html').write_text('<html><body>HANDOFF_PAGE_MARKER</body></html>')
                return 'Saved artifacts/index.html'
            workspace=self.adapter.agents[agent]
            pages=list((workspace/'inbox').glob('plan-*.html'))
            self.assertTrue(pages,'Reviewing specialist has no HTML to inspect')
            self.assertIn('HANDOFF_PAGE_MARKER',pages[0].read_text())
            self.assertIn(str(pages[0].relative_to(workspace)),prompt)
            return 'Reviewed actual page'
        self.adapter.respond=respond
        self.start();self.app.execute(self.app.next_job())
        team=self.app.crew_owner(self.owner)
        self.assertEqual(list((self.app.workspace(team,2)/'inbox').glob('plan-*.html')),[],'Temporary handoffs should not pile up')

    def test_two_simultaneous_plan_requests_only_accept_one(self):
        def enqueue(_):
            try:return self.start()
            except Problem:return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(enqueue,range(2)))
        self.assertEqual(sum(r is not None for r in results),1)

    def test_stop_at_each_model_phase_starts_no_later_call(self):
        for stop_at in range(1,8):
            with self.subTest(stop_at=stop_at):
                self.adapter.calls.clear();first=self.start();team=self.app.crew_owner(self.owner)
                def stop(role,prompt):
                    if len(self.adapter.calls)==stop_at:self.app.decision(team,first['id'],'cancel')
                self.adapter.after_call=stop;self.app.execute(self.app.next_job())
                self.assertEqual(len(self.adapter.calls),stop_at)
                self.assertEqual(self.job(first)['status'],'cancelled')
        self.adapter.after_call=None

    def test_malformed_planner_output_never_runs_specialist(self):
        for value in [None,[],True,{'summary':'x','tasks':[None]}, {'summary':' ','tasks':[]},
                      {'summary':'x','tasks':[{'role':1.0,'task':'x'}]}, {'summary':'x','tasks':[{'role':2,'task':' '*3}]}]:
            with self.subTest(value=value),self.assertRaises(RuntimeError):fixture.read_plan(json.dumps(value))

    def test_image_sent_to_captain_not_unrelated_specialists(self):
        import base64
        from chat_images import validate_images
        raw=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9V8AAAAASUVORK5CYII=')
        images=[{'dataUrl':'data:image/png;base64,'+base64.b64encode(raw).decode()}]
        validate_images(images)
        seen=[];original=self.adapter.respond
        def respond(agent,session,prompt,**kwargs):seen.append((agent,kwargs.get('images')));return original(agent,session,prompt,**kwargs)
        self.adapter.respond=respond
        self.app.enqueue(self.owner,{'kind':'chat','prompt':'/plan Summarize this diagram','images':images})
        self.app.execute(self.app.next_job())
        self.assertTrue(seen[0][1]);self.assertTrue(all(images for agent,images in seen if agent.endswith('-r0')))
        self.assertTrue(all(not images for agent,images in seen if not agent.endswith('-r0')))

    def test_failed_and_cancelled_handoffs_remove_temporary_page_copies(self):
        for stop in (False,True):
            with self.subTest(stop=stop):
                self.adapter.plan['tasks']=[{'role':3,'task':'Write HTML'},{'role':2,'task':'Review'}]
                result=self.start();team=self.app.crew_owner(self.owner)
                original=self.adapter.respond
                def respond(agent,session,prompt,**kwargs):
                    if '-checking-' in session:return json.dumps({'done':False,'reason':'Review is required.'})
                    if session.endswith('-planning'):return json.dumps(self.adapter.plan)
                    if agent.endswith('-r3'):
                        (self.adapter.agents[agent]/'artifacts'/'index.html').write_text('<html><body>draft</body></html>')
                        return 'Saved a draft'
                    if agent.endswith('-r2'):
                        self.assertTrue(list((self.adapter.agents[agent]/'inbox').glob('plan-*.html')))
                        if stop:
                            self.app.decision(team,result['id'],'cancel')
                            return 'Finished review after stop'
                        raise RuntimeError('Review fixture failure')
                    return 'Combined'
                self.adapter.respond=respond
                if stop:self.app.execute(self.app.next_job())
                else:
                    with self.assertRaises(RuntimeError):self.app.execute(self.app.next_job())
                    self.app.event(result['id'],'Failed','Fixture',status='error',result='{}')
                self.assertEqual(list((self.app.workspace(team,2)/'inbox').glob('plan-*.html')),[])
                self.adapter.respond=original

    def test_context_limits_do_not_starve_previous_plans_with_direct_turns(self):
        self.start();self.app.execute(self.app.next_job());team=self.app.crew_owner(self.owner)
        for _ in range(13):
            self.app.enqueue(team,{'kind':'crew-chat','crewRole':0,'prompt':'A brief direct follow-up'})
            self.app.execute(self.app.next_job())
        prompt=self.adapter.calls[-1][2]
        self.assertIn('A combined proposal',prompt)

    def test_restart_does_not_resume_half_finished_plan_automatically(self):
        result=self.start();row=self.app.next_job()
        payload=json.loads(row['payload']);payload['collaboration']['outputs']['1']={'name':'Dylan','answer':'SAVED_BEFORE_RESTART'}
        self.app.event(result['id'],'Contribution saved','Fixture',payload=json.dumps(payload))
        from test_studio import Studio
        restarted=Studio(self.temp.name,self.adapter,start_worker=False,recover=True)
        job=next(j for j in restarted.state(self.owner)['crewChats'] if j['id']==result['id'])
        self.assertEqual(job['status'],'error')
        self.assertIn('SAVED_BEFORE_RESTART',json.dumps(job))
        self.assertEqual(self.adapter.calls,[])

    def test_two_three_specialists_and_non_default_order(self):
        for order in [(5,4),(2,3),(3,2,8),(2,5,4)]:
            with self.subTest(order=order):
                self.adapter.plan['tasks']=[{'role':role,'task':'Do your part'} for role in order]
                self.adapter.calls.clear();result=self.start();self.app.execute(self.app.next_job())
                self.assertEqual([int(agent.rsplit('-r',1)[1]) for agent,_,_ in self.adapter.calls],[0,*[item for role in order[:-1] for item in (role,0)],order[-1],0])
                self.assertEqual(self.job(result)['status'],'done')

    def test_preparation_failure_makes_no_unprotected_model_call(self):
        from unittest.mock import patch
        result=self.start()
        with patch.object(self.app,'prepare_builtin_crew',side_effect=RuntimeError('Protection not verified')):
            with self.assertRaises(RuntimeError):self.app.execute(self.app.next_job())
        self.assertEqual(self.adapter.calls,[])
        self.assertEqual(self.job(result)['payload']['collaboration']['outputs'],{})

    def test_failure_in_each_specialist_or_final_review_preserves_prior_work(self):
        for completed, failing in enumerate((8,2,3,0)):
            with self.subTest(failing=failing):
                result=self.start();original=self.adapter.respond
                def respond(agent,session,prompt,**kwargs):
                    role=int(agent.rsplit('-r',1)[1])
                    if role==failing and (session.endswith('-reviewing') if failing==0 else not session.endswith('-planning')):raise RuntimeError('Fixture runtime failure')
                    return original(agent,session,prompt,**kwargs)
                self.adapter.respond=respond
                with self.assertRaises(RuntimeError):self.app.execute(self.app.next_job())
                plan=self.job(result)['payload']['collaboration']
                self.assertEqual(len(plan['outputs']),completed)
                self.app.event(result['id'],'Failed','Fixture',status='error',result='{}');self.adapter.respond=original
