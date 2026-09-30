"""Casey delegates only when necessary and stops on explicit evidence-based decisions."""
import json
import unittest
from collaboration_plan import read_plan, read_checkpoint
import test_collaboration_plan as fixture


class AdaptivePlanTests(unittest.TestCase):
    setUp = fixture.CollaborationTests.setUp
    start = fixture.CollaborationTests.start
    job = fixture.CollaborationTests.job

    def called(self):
        return [int(agent.rsplit('-r', 1)[1]) for agent, _, _ in self.adapter.calls]

    def test_direct_answer_or_missing_expertise_never_dispatches(self):
        for outcome in ('complete', 'unavailable'):
            with self.subTest(outcome=outcome):
                self.adapter.calls.clear()
                self.adapter.plan = {'summary': 'No additional specialist is appropriate.', 'tasks': [],
                                     'outcome': outcome, 'answer': 'Answer or honest capability limitation.'}
                result = self.start()
                self.app.execute(self.app.next_job())
                job = self.job(result)
                self.assertEqual(self.called(), [0])
                self.assertEqual(job['status'], 'done')
                self.assertEqual(job['payload']['collaboration']['outcome'], outcome)
                self.assertEqual(job['payload']['collaboration']['calledRoles'], [])
                self.assertEqual(job['result']['answer'], self.adapter.plan['answer'])
                self.assertIn('Do not assign loosely related specialists', self.adapter.calls[0][2])

    def test_one_specialist_is_enough(self):
        self.adapter.plan['tasks'] = [{'role': 3, 'task': 'Write a short greeting.'}]
        result = self.start(); self.app.execute(self.app.next_job())
        self.assertEqual(self.called(), [0, 3, 0])
        self.assertEqual(self.job(result)['payload']['collaboration']['calledRoles'], [3])

    def test_expected_result_is_validated_saved_and_sent_to_specialist(self):
        self.adapter.plan['tasks'] = [{'role':3,'task':'Write a greeting.',
                                     'expected':'One friendly sentence, no invented event details.'}]
        result = self.start(); self.app.execute(self.app.next_job())
        plan = self.job(result)['payload']['collaboration']
        self.assertEqual(plan['handoffs']['3']['expected'], self.adapter.plan['tasks'][0]['expected'])
        self.assertIn('Expected result and acceptance criteria from Casey:',self.adapter.calls[1][2])
        self.assertIn(plan['handoffs']['3']['expected'],self.adapter.calls[1][2])
        for expected in ('', None, ['invented'], 'x'*1501):
            with self.subTest(expected=expected), self.assertRaises(RuntimeError):
                read_plan(json.dumps({'summary':'Write','tasks':[{'role':3,'task':'Write','expected':expected}]}))

    def test_stops_after_first_or_second_result_with_explicit_reason(self):
        original = self.adapter.respond
        for finish_after in (1, 2):
            with self.subTest(finish_after=finish_after):
                self.adapter.calls.clear()
                checks = []
                def respond(agent, session, prompt, **kwargs):
                    answer = original(agent, session, prompt, **kwargs)
                    if '-checking-' in session:
                        checks.append(session)
                        return json.dumps({'done': len(checks)==finish_after,
                            'reason': 'The supplied result satisfies the request; no additional agents are needed.' if len(checks)==finish_after else 'The constraints still need analysis.',
                            'answer': 'Final grounded answer.'})
                    return answer
                self.adapter.respond = respond
                result = self.start(); self.app.execute(self.app.next_job())
                plan = self.job(result)['payload']['collaboration']
                self.assertEqual(self.called(), [0,8,0] if finish_after==1 else [0,8,0,2,0])
                self.assertEqual(plan['skippedRoles'], [2,3] if finish_after==1 else [3])
                self.assertEqual(len(plan['outputs']), finish_after)
                self.assertIn('no additional agents', plan['checks'][-1]['reason'])
                checkpoint_prompt=next(prompt for _,session,prompt in self.adapter.calls if '-checking-' in session)
                self.assertIn('include that explanation in answer itself',checkpoint_prompt)
                self.assertIn('never imply that a skipped reviewer performed a review',checkpoint_prompt)
                self.assertEqual(self.job(result)['result']['answer'], 'Final grounded answer.')

    def test_missing_capability_midway_preserves_work_without_false_success(self):
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            answer = original(agent, session, prompt, **kwargs)
            if '-checking-' in session:
                return json.dumps({'done':True, 'outcome':'unavailable',
                    'reason':'No deployment specialist or deployment tool is available.',
                    'answer':'Research is complete; deployment is not possible with this team.'})
            return answer
        self.adapter.respond = respond
        result = self.start(); self.app.execute(self.app.next_job())
        plan = self.job(result)['payload']['collaboration']
        self.assertEqual(self.called(), [0,8,0])
        self.assertEqual(plan['outcome'], 'unavailable')
        self.assertEqual(set(plan['outputs']), {'8'})
        self.assertEqual(plan['skippedRoles'], [2,3])

    def test_bad_checkpoint_never_calls_remaining_specialists(self):
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            answer = original(agent, session, prompt, **kwargs)
            return 'Enough' if '-checking-' in session else answer
        self.adapter.respond = respond
        result = self.start()
        with self.assertRaises(RuntimeError): self.app.execute(self.app.next_job())
        self.assertEqual(self.called(), [0,8,0])
        self.assertEqual(set(self.job(result)['payload']['collaboration']['outputs']), {'8'})

    def test_final_review_reports_unavailable_capability_after_one_specialist(self):
        self.adapter.plan['tasks'] = [{'role':5,'task':'Write a prototype.'}]
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            answer = original(agent, session, prompt, **kwargs)
            if session.endswith('-reviewing'):
                return json.dumps({'done':True,'outcome':'unavailable','reason':'No deployment tool is available.',
                                   'answer':'The prototype is drafted, but it has not been deployed.'})
            return answer
        self.adapter.respond = respond
        result = self.start(); self.app.execute(self.app.next_job())
        plan = self.job(result)['payload']['collaboration']
        self.assertEqual(self.called(), [0,5,0])
        self.assertEqual(plan['checks'][-1]['outcome'], 'unavailable')
        self.assertEqual(plan['outcome'], 'unavailable')
        self.assertIn('not been deployed', self.job(result)['result']['answer'])

    def test_checkpoint_can_read_actual_artifact_and_transient_copy_is_removed(self):
        self.adapter.plan['tasks'] = [{'role':5,'task':'Build'}, {'role':4,'task':'Review'}]
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            answer = original(agent, session, prompt, **kwargs)
            if agent.endswith('-r5'):
                (self.adapter.agents[agent]/'artifacts/example.py').write_text('RESULT_CONTENT')
            if '-checking-' in session:
                copies = list((self.adapter.agents[agent]/'inbox').glob('plan-*'))
                self.assertEqual(len(copies), 1)
                self.assertEqual(copies[0].read_text(), 'RESULT_CONTENT')
                self.assertIn(copies[0].name, prompt)
                return json.dumps({'done':True,'reason':'The requested source file is complete.','answer':'Saved the requested source file.'})
            return answer
        self.adapter.respond = respond
        result = self.start(); self.app.execute(self.app.next_job())
        team = self.app.crew_owner(self.owner)
        self.assertEqual(list((self.app.workspace(team,0)/'inbox').glob('plan-*')), [])
        self.assertTrue(any(path.endswith('.py') for path in self.job(result)['result']['files']))
        self.assertEqual(self.called(), [0,5,0])

    def test_invalid_decisions_and_empty_answers_are_rejected(self):
        for value in ({'done':'true','reason':'x','answer':'x'}, {'done':True,'reason':'x'},
                      {'done':True,'reason':' ','answer':'x'}, {'done':True,'reason':'x','answer':'x','outcome':'unknown'}):
            with self.subTest(value=value), self.assertRaises(RuntimeError): read_checkpoint(json.dumps(value))
        for value in ({'summary':'x','tasks':[]}, {'summary':'x','tasks':[],'answer':' '},
                      {'summary':'x','tasks':[],'answer':'x','outcome':'unknown'}):
            with self.subTest(value=value), self.assertRaises(RuntimeError): read_plan(json.dumps(value))
