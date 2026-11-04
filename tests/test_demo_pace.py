"""Budget boundaries preserve deliverables instead of extending review loops."""
import unittest
from unittest.mock import patch
import test_collaboration_plan as fixture
from plan_revision import PLAN_TIME_BUDGET_SECONDS
from agent_runtime import GatewayError


class DemoPaceTests(unittest.TestCase):
    setUp=fixture.CollaborationTests.setUp
    start=fixture.CollaborationTests.start
    job=fixture.CollaborationTests.job

    def configure(self, finish_at, *, timeout=False):
        self.clock=[0]; self.observed=[]
        self.adapter.plan={'summary':'Build the page','tasks':[{'role':5,'task':'Build a small page','requiredFiles':['artifacts/index.html']}]}
        original=self.adapter.respond
        def respond(agent,session,prompt,**kwargs):
            if not session.startswith('bac-plan-'):return original(agent,session,prompt,**kwargs)
            self.observed.append((session,prompt,kwargs['timeout'],self.clock[0]))
            answer=original(agent,session,prompt,**kwargs)
            if session.endswith('-planning'):self.clock[0]=20
            elif session.endswith('-planning-captain-scope-check'):self.clock[0]=30
            elif session.endswith('-working'):
                (self.adapter.agents[agent]/'artifacts/index.html').write_text('<!doctype html><html><body>Saved core</body></html>')
                self.clock[0]=finish_at
                if timeout:raise GatewayError('Demo time limit reached','timeout')
            return answer
        self.adapter.respond=respond

    def run_demo(self):
        result=self.start('/goal Build a small HTML page.')
        with patch('collaboration_plan.monotonic',side_effect=lambda:self.clock[0]):
            self.app.execute(self.app.next_job())
        return self.job(result)

    def test_near_deadline_skips_review_and_preserves_html_as_partial(self):
        self.configure(PLAN_TIME_BUDGET_SECONDS-10)
        job=self.run_demo();plan=job['payload']['collaboration']
        self.assertEqual(job['status'],'done');self.assertEqual(plan['outcome'],'partial')
        self.assertTrue(plan['budgetReached'])
        self.assertFalse(any(s.endswith('-reviewing') for s,_,_,_ in self.observed))
        self.assertTrue(any(f.endswith('.html') for f in job['result']['files']))
        self.assertIn('without another task step or review',job['result']['answer'])

    def test_native_timeout_receives_only_remaining_budget_and_keeps_saved_page(self):
        self.configure(PLAN_TIME_BUDGET_SECONDS,timeout=True)
        job=self.run_demo();plan=job['payload']['collaboration']
        work=next(x for x in self.observed if x[0].endswith('-working'))
        self.assertEqual(work[2],PLAN_TIME_BUDGET_SECONDS-30)
        for _,_,timeout,started in self.observed:self.assertLessEqual(timeout,PLAN_TIME_BUDGET_SECONDS-started)
        self.assertEqual(plan['outcome'],'partial');self.assertTrue(plan['outputs']['5']['incomplete'])
        self.assertTrue(any(f.endswith('.html') for f in job['result']['files']))
        self.assertFalse(any(s.endswith('-reviewing') for s,_,_,_ in self.observed))
        self.assertFalse(self.adapter.reaction_calls)

    def test_short_remaining_time_allows_final_answer_but_not_optional_revision(self):
        self.configure(PLAN_TIME_BUDGET_SECONDS-30)
        job=self.run_demo()
        review=next(x for x in self.observed if x[0].endswith('-reviewing'))
        self.assertEqual(review[2],30)
        self.assertIn('No further revision is allowed within the remaining time',review[1])
        self.assertNotIn('You may request ONE targeted revision',review[1])
        self.assertNotIn('revision',job['payload']['collaboration'])
        self.assertEqual(job['payload']['collaboration']['outcome'],'complete')


class PersonalReactionBudgetTests(unittest.TestCase):
    def run_reactions(self, preparation=0):
        from types import SimpleNamespace
        from crew_roundtable import RoundtableControls
        clock=[0];calls=[];prepared=[]
        members=[dict(key=k,id=k,name=k,skills=[],tone='kind',persona='guide',purpose='Friendly helper') for k in ('one','two')]
        payload={'collaboration':{'task':'A completed task','finalAnswer':'Saved result','outputs':{}},
                 'roundtable':{'members':members,'replies':{}}}
        def prepare(key,member,*,model_stage):
            self.assertEqual(model_stage, 'team')
            prepared.append(key);clock[0]+=preparation;return key
        def respond(agent,session,prompt,owner,**kwargs):
            calls.append(kwargs['timeout']);clock[0]+=11;return 'A short personal reaction.'
        app=SimpleNamespace(stop_checkpoint=lambda _:False,ensure_agent=prepare,
            check_protected_run=lambda *_:None,event=lambda *a,**kw:None,
            protected_response=respond,record_usage=lambda *a,**kw:None)
        with patch('crew_roundtable.time.monotonic',side_effect=lambda:clock[0]):
            RoundtableControls.run_roundtable(app,{'owner':'team','id':'job'},payload,budget_seconds=10)
        return payload['roundtable'],calls,prepared

    def test_reaction_cannot_start_another_call_after_budget(self):
        meeting,calls,prepared=self.run_reactions()
        self.assertEqual(calls,[10]);self.assertEqual(prepared,['one'])
        self.assertEqual(meeting['replies']['one']['status'],'done')
        self.assertEqual(meeting['replies']['two']['status'],'skipped')

    def test_slow_preparation_does_not_start_a_late_model_call(self):
        meeting,calls,prepared=self.run_reactions(preparation=11)
        self.assertEqual(calls,[]);self.assertEqual(prepared,['one'])
        self.assertTrue(all(r['status']=='skipped' for r in meeting['replies'].values()))

class ReviewIdentityTests(unittest.TestCase):
    def test_requested_review_is_not_tied_to_a_standby_name(self):
        from plan_review import include_required_review
        plan={'reviewRequired':True,'summary':'Produce and review','tasks':[{'role':5,'agent':'hired-producer','task':'Build a counter'}]}
        include_required_review(plan)
        self.assertEqual([t['role'] for t in plan['tasks']],[5,4])
        self.assertNotIn('Vera',str(plan))
        self.assertIn('independent',plan['summary'])


class NativeDemoTimeoutTests(unittest.TestCase):
    def test_timeout_aborts_only_the_exact_plan_or_reaction_session(self):
        import json
        import agent_runtime as runtime
        sessions=['bac-plan-'+'a'*24+'-5-working','bac-plan-'+'a'*24+'-0-reviewing',
                  'bac-plan-'+'a'*24+'-6-working','bac-roundtable-'+'a'*24+'-'+'b'*24+'-1','ordinary-chat']
        for session in sessions:
            with self.subTest(session=session):
                def gateway(path,payload=None,**kwargs):
                    if path=='/v1/models':return {'data':[{'id':'openclaw/deadline-test'}]}
                    raise GatewayError('Time limit','timeout')
                with patch.object(runtime,'gateway',side_effect=gateway),patch.object(runtime,'cli') as abort,patch.object(runtime,'observed_activity',return_value={'calls':[]}),patch('research_recovery.recovered_sources',return_value=[]),patch('user_location.context',return_value=''):
                    with self.assertRaises(GatewayError):runtime.respond('deadline-test',session,'Task',timeout=2)
                if session=='ordinary-chat':abort.assert_not_called()
                else:
                    abort.assert_called_once()
                    args=abort.call_args.args
                    self.assertEqual(args[:3],('gateway','call','sessions.abort'))
                    params=json.loads(args[args.index('--params')+1])
                    self.assertEqual(params,{'agentId':'deadline-test','key':'agent:deadline-test:openai-user:'+session,'clearQueued':True})
                    self.assertEqual(abort.call_args.kwargs['timeout'],5)

if __name__=='__main__':unittest.main()
