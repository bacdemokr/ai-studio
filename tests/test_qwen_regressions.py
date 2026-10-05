"""Failures observed or plausibly returned by tool-calling chat models."""
import json
import unittest
from unittest.mock import patch
import agent_runtime as runtime
import test_collaboration_plan as fixture
from collaboration_plan import read_checkpoint, CaptainDecisionError
from webpage_artifacts import html_files, collect_pages


class QwenPlanRegressions(unittest.TestCase):
    setUp = fixture.CollaborationTests.setUp
    start = fixture.CollaborationTests.start
    job = fixture.CollaborationTests.job

    def checkpoint(self, decision, scope_warning=False):
        self.adapter.plan['tasks'] = [{'role':8,'task':'Research'}, {'role':5,'task':'Build'}]
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            result = original(agent, session, prompt, **kwargs)
            if agent.endswith('-r8') and scope_warning:
                (self.adapter.agents[agent]/'artifacts/unassigned.html').write_text('<html><body>Unassigned</body></html>')
            if '-checking-8' in session: return json.dumps(decision)
            return result
        self.adapter.respond = respond
        result = self.start('/plan Give a research summary.')
        self.app.execute(self.app.next_job())
        return self.job(result)['payload']['collaboration']

    def test_finished_answer_with_no_next_step_is_not_forced_partial(self):
        plan = self.checkpoint({'done':True,'readyForNext':False,'reason':'The answer is sufficient.', 'answer':'Completed summary.'})
        self.assertEqual(plan['outcome'], 'complete')
        self.assertEqual(plan['calledRoles'], [8])

    def test_scope_warning_does_not_override_a_deliberate_partial_stop(self):
        plan = self.checkpoint({'done':True,'outcome':'partial','reason':'Source unavailable.',
            'answer':'Partial findings only. Source access is missing.', 'remaining':['Verified sources']}, scope_warning=True)
        self.assertEqual(plan['outcome'], 'partial')
        self.assertEqual(plan['calledRoles'], [8])

    def test_empty_and_cut_off_saved_pages_are_not_deliverables(self):
        w=self.app.workspace(self.owner)
        for i, content in enumerate(['', '  ', '<!doctype html><html><body>Cut off', 'I saved the page.']):
            with self.subTest(content=content):
                before=html_files(w)
                (w/'artifacts'/('bad'+str(i)+'.html')).write_text(content)
                self.assertEqual(collect_pages(self.app,self.owner,'bad'+str(i),None,before,''), [])

    def test_unavailable_cannot_mean_continue(self):
        with self.assertRaises(CaptainDecisionError):
            read_checkpoint(json.dumps({'done':False,'outcome':'unavailable','reason':'No access.'}))

    def test_saved_page_survives_one_bounded_output_retry(self):
        self.adapter.plan['tasks'] = [{'role':5,'task':'Build a page','requiredFiles':['artifacts/page.html']},
                                     {'role':4,'task':'Review'}]
        original = self.adapter.respond
        def respond(agent,session,prompt,**kwargs):
            result=original(agent,session,prompt,**kwargs)
            if agent.endswith('-r5'):
                (self.adapter.agents[agent]/'artifacts/page.html').write_text('<html><body>Saved before failure</body></html>')
                raise runtime.GatewayError('Output limit', 'output-limit')
            return result
        self.adapter.respond=respond
        result=self.start('/plan Build and review a webpage')
        self.app.execute(self.app.next_job())
        job=self.job(result);plan=job['payload']['collaboration']
        self.assertEqual(plan['outcome'],'partial')
        self.assertEqual(plan['calledRoles'],[5])
        self.assertTrue(plan['outputs']['5']['incomplete'])
        pages=[p for p in job['result']['files'] if p.endswith('.html')]
        self.assertEqual(len(pages),1)
        self.assertIn('Saved before failure',self.app.available_file(self.owner,pages[0]).read_text())
        self.assertEqual(sum(agent.endswith('-r5') for agent,_,_ in self.adapter.calls),2)
        self.assertEqual(plan['outputLimitRetry']['status'],'failed')

    def test_good_page_does_not_validate_an_incomplete_sibling(self):
        self.adapter.plan['tasks'] = [{'role':5,'task':'Build two pages',
            'requiredFiles':['artifacts/good.html','artifacts/broken.html']}, {'role':4,'task':'Review'}]
        original=self.adapter.respond
        def respond(agent,session,prompt,**kwargs):
            result=original(agent,session,prompt,**kwargs)
            if agent.endswith('-r5'):
                w=self.adapter.agents[agent]
                (w/'artifacts/good.html').write_text('<html><body>Good</body></html>')
                (w/'artifacts/broken.html').write_text('<html><body>Cut off')
                return 'Both pages are complete.'
            return result
        self.adapter.respond=respond
        result=self.start('/plan Build two webpages and review them')
        self.app.execute(self.app.next_job())
        plan=self.job(result)['payload']['collaboration']
        self.assertEqual(plan['outcome'],'partial')
        self.assertEqual(plan['calledRoles'],[5])
        self.assertNotIn('artifacts/broken.html',plan['verifiedSources']['5'])


class QwenRuntimeRegressions(unittest.TestCase):
    def test_empty_reply_is_diagnosed_without_replay(self):
        posts=[]
        def gateway(path,*args,**kwargs):
            if path=='/v1/models':return {'data':[{'id':'openclaw/qa-empty'}]}
            posts.append(path)
            return {'choices':[{'message':{'content':''}}]}
        with patch.object(runtime,'gateway',side_effect=gateway), patch.object(runtime,'observed_activity',return_value={'calls':[]}), patch('user_location.context',return_value=''):
            with self.assertRaises(runtime.GatewayError) as raised:
                runtime.respond('qa-empty','s','hello')
            self.assertEqual(raised.exception.reason,'empty-response')
        self.assertEqual(len(posts),1)

    def test_explicit_length_stop_is_not_returned_as_success_or_retried(self):
        posts=[]
        def gateway(path,*args,**kwargs):
            if path=='/v1/models': return {'data':[{'id':'openclaw/qa-length'}]}
            posts.append(path)
            return {'choices':[{'finish_reason':'length','message':{'content':'A truncated response'}}]}
        with patch.object(runtime,'gateway',side_effect=gateway), patch.object(runtime,'observed_activity',return_value={'calls':[]}), patch('user_location.context',return_value=''), patch('telemetry.measure',return_value={}):
            with self.assertRaises(runtime.GatewayError) as raised:
                runtime.respond('qa-length','s','hello')
            self.assertEqual(raised.exception.reason,'output-limit')
        self.assertEqual(len(posts),1)
