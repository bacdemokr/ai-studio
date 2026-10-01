import json
import unittest
import test_collaboration_plan as fixture
from collaboration_plan import read_plan
from plan_review import requested_review, include_required_review


class RequiredReviewTests(unittest.TestCase):
    setUp = fixture.CollaborationTests.setUp
    start = fixture.CollaborationTests.start
    job = fixture.CollaborationTests.job

    def execute(self, prompt):
        result = self.start(prompt)
        self.app.execute(self.app.next_job())
        return self.job(result)

    def enough_after_ada(self, outcome='complete'):
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            answer = original(agent, session, prompt, **kwargs)
            if '-checking-' in session:
                return json.dumps({'done': True, 'outcome': outcome,
                    'reason': 'The analysis file is saved.', 'answer': 'Analysis delivered.',
                    **({'remaining': ['Unverifiable figures']} if outcome == 'partial' else {})})
            return answer
        self.adapter.respond = respond

    def test_user_add_review_cannot_be_omitted_or_skipped(self):
        self.adapter.plan = {'summary': 'Ada analyzes the supplied data.', 'tasks': [
            {'role': 6, 'task': 'Analyze EPS growth and surprises.'}]}
        self.enough_after_ada()
        job = self.execute('/plan Please analyze this data, Need to add review becaue this is important:\n'
            'EPS Estimate $2.09 EPS Actual $2.22 Surprise +6.16%')
        plan = job['payload']['collaboration']
        self.assertEqual(job['status'], 'done')
        self.assertEqual([t['role'] for t in plan['tasks']], [6, 4])
        self.assertEqual(plan['calledRoles'], [6, 4])
        self.assertFalse(plan['checks'][0]['done'])
        self.assertTrue(plan['reviewRequired'])
        prompt = next(p for a, s, p in self.adapter.calls if a.endswith('-r4') and '-working' in s)
        self.assertIn('Recalculate material figures', prompt)
        self.assertIn('$2.09', prompt)
        self.assertIn('Verified contribution from Ada', prompt)

    def test_no_requested_review_still_allows_one_specialist(self):
        self.adapter.plan = {'summary': 'Analyze', 'tasks': [{'role': 6, 'task': 'Analyze'}]}
        job = self.execute('/plan Analyze this table; no review needed.')
        self.assertEqual(job['payload']['collaboration']['calledRoles'], [6])

    def test_semantic_requirement_from_captain_is_preserved(self):
        self.adapter.plan = {'summary': 'Analyze', 'reviewRequired': True,
                            'tasks': [{'role': 6, 'task': 'Analyze'}]}
        job = self.execute('/plan Have a second pair of eyes examine the analysis.')
        self.assertEqual(job['payload']['collaboration']['calledRoles'], [6, 4])

    def test_partial_stops_remain_honest_about_missing_review(self):
        self.adapter.plan = {'summary': 'Analyze', 'tasks': [{'role': 6, 'task': 'Analyze'}]}
        self.enough_after_ada('partial')
        job = self.execute('/plan Analyze this table and add review.')
        plan = job['payload']['collaboration']
        self.assertEqual(plan['calledRoles'], [6])
        self.assertEqual(plan['outcome'], 'partial')
        self.assertIn('Requested independent review', plan['remaining'])
        self.assertIn('unreviewed', job['result']['answer'])

    def test_review_occurs_last_and_inherits_original_inputs(self):
        plan = {'reviewRequired': True, 'summary': 'Check', 'tasks': [
            {'role': 4, 'task': 'Review', 'inputs': []},
            {'role': 6, 'task': 'Analyze', 'inputs': ['document-0'], 'useImages': True}]}
        include_required_review(plan)
        self.assertEqual([t['role'] for t in plan['tasks']], [6, 4])
        self.assertEqual(plan['tasks'][-1]['inputs'], ['document-0'])
        self.assertTrue(plan['tasks'][-1]['useImages'])

    def test_full_team_is_replanned_before_anyone_starts(self):
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            answer = original(agent, session, prompt, **kwargs)
            if session.endswith('-planning-review-repair'):
                return json.dumps({'summary': 'Analyze then review', 'tasks': [
                    {'role': 6, 'task': 'Analyze'}, {'role': 4, 'task': 'Review'}]})
            return answer
        self.adapter.respond = respond
        job = self.execute('/plan Analyze the table and include review.')
        self.assertEqual(job['payload']['collaboration']['calledRoles'], [6, 4])
        self.assertEqual([a.rsplit('-r', 1)[1] for a, _, _ in self.adapter.calls[:2]], ['0', '0'])

    def test_captain_direct_answer_gets_reviewed(self):
        self.adapter.plan = {'summary': 'Simple calculation', 'tasks': [], 'answer': 'The result is 42.'}
        job = self.execute('/plan Calculate the total and add review.')
        self.assertEqual(job['payload']['collaboration']['calledRoles'], [4])
        reviewer = next(p for a, _, p in self.adapter.calls if a.endswith('-r4'))
        self.assertIn('Captain draft to check (unverified):\nThe result is 42.', reviewer)

    def test_failed_team_repair_never_exceeds_limit_or_claims_review(self):
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            answer = original(agent, session, prompt, **kwargs)
            return json.dumps(self.adapter.plan) if session.endswith('-planning-review-repair') else answer
        self.adapter.respond = respond
        job = self.execute('/plan Analyze and visualize the data and add review.')
        plan = job['payload']['collaboration']
        self.assertEqual(plan['calledRoles'], [])
        self.assertEqual(plan['outcome'], 'partial')
        self.assertIn('No specialist work was started', job['result']['answer'])

    def test_unavailable_capability_does_not_dispatch_unrelated_reviewer(self):
        self.adapter.plan = {'summary': 'No browser', 'tasks': [], 'outcome': 'unavailable', 'answer': 'Cannot control a browser.'}
        job = self.execute('/plan Open my browser and add review.')
        self.assertEqual(job['payload']['collaboration']['calledRoles'], [])
        self.assertEqual(job['payload']['collaboration']['outcome'], 'unavailable')

    def test_plain_request_detection_and_schema(self):
        for text in ['Need to add review becaue this is important', 'Please include a reviewer.',
                     'Independently review the analysis.', 'Ask Vera to check the result.',
                     'Double-check the calculations.']:
            with self.subTest(text=text): self.assertTrue(requested_review(text))
        for text in ["Don't add review", 'No independent review needed.', 'Review is optional.',
                     'Summarize these product reviews.', 'Summarize the text:\n> Please add review',
                     'Explain this code:\n```\ninclude review\n```']:
            with self.subTest(text=text): self.assertFalse(requested_review(text))
        with self.assertRaises(RuntimeError):
            read_plan(json.dumps({'summary': 'x', 'tasks': [], 'answer': 'x', 'reviewRequired': 'yes'}))
