import unittest
from unittest.mock import patch
import test_collaboration_plan as fixture
from agent_runtime import GatewayError
from collaboration_plan import compact_contributions


class OutputRetryTests(unittest.TestCase):
    setUp = fixture.CollaborationTests.setUp
    start = fixture.CollaborationTests.start
    job = fixture.CollaborationTests.job
    def install_failure(self, reason='output-limit', always=False, captain=False):
        self.adapter.plan={'summary':'Small demo design','tasks':[{'role':7,'task':'Save a compact design spec to artifacts/spec.md','requiredFiles':['artifacts/spec.md']}]}
        original=self.adapter.respond
        self.attempts=[]
        def respond(agent, session, prompt, **kwargs):
            target=session.endswith('-planning') if captain else session.endswith('-working')
            retry=session.endswith('-output-retry')
            if target or retry:
                self.attempts.append((session,prompt))
                if not captain and not retry:
                    workspace=self.app.workspace(self.app.crew_owner(self.owner),7)
                    (workspace/'artifacts/spec.md').write_text('# Core demo\nA board, keyboard controls and restart.\n')
                if not retry or always:
                    raise GatewayError('Output stopped',reason)
            normalized=session.removesuffix('-output-retry')
            return original(agent,normalized,prompt,**kwargs)
        self.adapter.respond=respond

    def test_retry_reuses_saved_file_in_fresh_session_and_finishes(self):
        self.install_failure()
        result=self.start('/plan Build a small demo')
        self.app.execute(self.app.next_job())
        plan=self.job(result)['payload']['collaboration']
        self.assertEqual(plan['outputLimitRetry']['status'],'recovered')
        self.assertEqual(len(self.attempts),2)
        self.assertTrue(self.attempts[1][0].endswith('-output-retry'))
        self.assertIn('artifacts/spec.md',self.attempts[1][1])
        self.assertTrue(plan['outputs']['7']['files'])
        self.assertFalse(plan['outputs']['7'].get('incomplete'))
        self.assertEqual(plan['outcome'],'complete')

    def test_retry_replaces_old_snapshot_of_same_source(self):
        self.install_failure()
        original=self.adapter.respond
        def respond(agent,session,prompt,**kwargs):
            if session.endswith('-output-retry'):
                workspace=self.app.workspace(self.app.crew_owner(self.owner),7)
                (workspace/'artifacts/spec.md').write_text('# Corrected design\nMinimal working demo.\n')
            return original(agent,session,prompt,**kwargs)
        self.adapter.respond=respond
        result=self.start();self.app.execute(self.app.next_job())
        plan=self.job(result)['payload']['collaboration']
        files=plan['outputs']['7']['files']
        self.assertEqual(len(files),1,'Forward only the newest snapshot of a source file')
        self.assertIn('Corrected design',(self.app.workspace(self.app.crew_owner(self.owner))/files[0]).read_text())

    def test_second_output_limit_stops_and_preserves_partial_work(self):
        self.install_failure(always=True)
        result=self.start();self.app.execute(self.app.next_job())
        plan=self.job(result)['payload']['collaboration']
        self.assertEqual(len(self.attempts),2)
        self.assertEqual(plan['outputLimitRetry']['status'],'failed')
        self.assertEqual(plan['outcome'],'partial')
        self.assertTrue(plan['outputs']['7']['files'])

    def test_text_tool_failure_gets_one_native_write_retry(self):
        self.install_failure(reason='unexecuted-tool-call')
        result=self.start();self.app.execute(self.app.next_job())
        plan=self.job(result)['payload']['collaboration']
        self.assertEqual(plan['outputLimitRetry']['reason'],'unexecuted-tool-call')
        self.assertEqual(plan['outputLimitRetry']['status'],'recovered')
        self.assertEqual(len(self.attempts),2)
        self.assertIn('native write/edit tools',self.attempts[1][1])
        self.assertIn('under 6000 characters',self.attempts[1][1])

    def test_repeated_text_tool_failure_stops_after_one_retry(self):
        self.install_failure(reason='unexecuted-tool-call',always=True)
        result=self.start();self.app.execute(self.app.next_job())
        plan=self.job(result)['payload']['collaboration']
        self.assertEqual(len(self.attempts),2)
        self.assertEqual(plan['outcome'],'partial')
        self.assertEqual(plan['outputLimitRetry']['status'],'failed')

    def test_unrelated_failure_is_not_retried(self):
        self.install_failure(reason='request_failed')
        result=self.start();self.app.execute(self.app.next_job())
        self.assertEqual(len(self.attempts),1)
        self.assertNotIn('outputLimitRetry',self.job(result)['payload']['collaboration'])

    def test_captain_can_retry_compact_decision(self):
        self.install_failure(captain=True)
        result=self.start();self.app.execute(self.app.next_job())
        self.assertEqual(self.job(result)['payload']['collaboration']['outputLimitRetry']['role'],0)
        self.assertEqual(len(self.attempts),2)

    def test_retry_respects_remaining_time_budget(self):
        self.install_failure()
        original=self.adapter.respond
        clock=[0]
        def respond(*args,**kwargs):
            try:return original(*args,**kwargs)
            except GatewayError:
                clock[0]=580
                raise
        self.adapter.respond=respond
        result=self.start()
        with patch('collaboration_plan.monotonic',side_effect=lambda:clock[0]):
            self.app.execute(self.app.next_job())
        self.assertEqual(len(self.attempts),1)
        self.assertNotIn('outputLimitRetry',self.job(result)['payload']['collaboration'])

    def test_cancellation_during_failure_prevents_retry(self):
        self.install_failure()
        original=self.adapter.respond
        result=self.start()
        def respond(*args,**kwargs):
            try:return original(*args,**kwargs)
            except GatewayError:
                self.app.decision(self.app.crew_owner(self.owner),result['id'],'cancel')
                raise
        self.adapter.respond=respond
        self.app.execute(self.app.next_job())
        self.assertEqual(len(self.attempts),1)
        self.assertEqual(self.job(result)['status'],'cancelled')
        self.assertNotIn('outputLimitRetry',self.job(result)['payload']['collaboration'])

    def test_retry_allowance_is_shared_with_captain(self):
        self.install_failure(captain=True)
        original=self.adapter.respond
        def respond(agent,session,prompt,**kwargs):
            if session.endswith('-working'):
                self.attempts.append((session,prompt))
                workspace=self.app.workspace(self.app.crew_owner(self.owner),7)
                (workspace/'artifacts/spec.md').write_text('# Saved partial work')
                raise GatewayError('Output stopped','output-limit')
            return original(agent,session,prompt,**kwargs)
        self.adapter.respond=respond
        result=self.start();self.app.execute(self.app.next_job())
        self.assertEqual(len(self.attempts),3)
        plan=self.job(result)['payload']['collaboration']
        self.assertEqual(plan['outputLimitRetry']['role'],0)
        self.assertEqual(plan['outcome'],'partial')

    def test_remaining_budget_is_passed_to_model_call(self):
        self.install_failure()
        original=self.adapter.respond;clock=[0];timeouts=[]
        def respond(agent,session,prompt,**kwargs):
            if session.endswith('-output-retry'):timeouts.append(kwargs['timeout'])
            try:return original(agent,session,prompt,**kwargs)
            except GatewayError:
                clock[0]=550
                raise
        self.adapter.respond=respond
        result=self.start()
        with patch('collaboration_plan.monotonic',side_effect=lambda:clock[0]):
            self.app.execute(self.app.next_job())
        self.assertEqual(timeouts,[50])

    def test_compact_context_preserves_artifact_references(self):
        value=compact_contributions({'7':{'answer':'x'*20000,'task':'y'*3000,'files':['artifacts/spec.md'],'activity':{'calls':['large']}}})[0]
        self.assertLess(len(value['answer']),2100)
        self.assertEqual(value['files'],['artifacts/spec.md'])
        self.assertNotIn('activity',value)


class RuntimeDeadlineTests(unittest.TestCase):
    def test_discovery_time_is_deducted_from_model_request_timeout(self):
        import agent_runtime as runtime
        clock=[100];posts=[]
        def gateway(path,payload=None,**kwargs):
            if path=='/v1/models':
                clock[0]=110
                return {'data':[{'id':'openclaw/deadline-test'}]}
            posts.append(kwargs['timeout'])
            return {'choices':[{'message':{'content':'Done'}}]}
        with patch.object(runtime,'gateway',side_effect=gateway), patch.object(runtime.time,'monotonic',side_effect=lambda:clock[0]), patch.object(runtime,'observed_activity',return_value={'calls':[]}), patch('user_location.context',return_value=''), patch('telemetry.measure',return_value={}):
            runtime.respond('deadline-test','s','hello',timeout=30)
        self.assertEqual(posts,[20])

    def test_no_model_post_after_discovery_exhausts_budget(self):
        import agent_runtime as runtime
        clock=[100];posts=[]
        def gateway(path,payload=None,**kwargs):
            if path=='/v1/models':
                clock[0]=140
                return {'data':[{'id':'openclaw/deadline-test'}]}
            posts.append(path)
        with patch.object(runtime,'gateway',side_effect=gateway), patch.object(runtime.time,'monotonic',side_effect=lambda:clock[0]), patch('user_location.context',return_value=''):
            with self.assertRaises(GatewayError):runtime.respond('deadline-test','s','hello',timeout=30)
        self.assertEqual(posts,[])
