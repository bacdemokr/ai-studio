import json
import unittest
import test_collaboration_plan as fixture
from collaboration_plan import read_plan
from plan_review import include_required_review


class RequiredReviewTests(unittest.TestCase):
    setUp = fixture.CollaborationTests.setUp
    start = fixture.CollaborationTests.start
    job = fixture.CollaborationTests.job

    def execute(self, prompt):
        result = self.start(prompt)
        self.app.execute(self.app.next_job())
        return self.job(result)

    def reviewed_plan(self):
        # Model-selected intent and assignees; the app must not infer these from prose.
        self.adapter.plan = {'summary': 'Analyze then independently review.', 'reviewRequired': True,
                             'tasks': [{'role': 6, 'task': 'Analyze the supplied data.'},
                                       {'role': 4, 'task': 'Recalculate material figures and review the analysis.'}]}

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
        self.reviewed_plan()
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
        self.reviewed_plan()
        job = self.execute('/plan Have a second pair of eyes examine the analysis.')
        self.assertEqual(job['payload']['collaboration']['calledRoles'], [6, 4])

    def test_partial_stops_remain_honest_about_missing_review(self):
        self.reviewed_plan()
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
        self.adapter.plan['reviewRequired'] = True
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            answer = original(agent, session, prompt, **kwargs)
            if session.endswith('-planning-review-repair'):
                return json.dumps({'summary': 'Analyze then review', 'reviewRequired': True, 'tasks': [
                    {'role': 6, 'task': 'Analyze'}, {'role': 4, 'task': 'Review'}]})
            return answer
        self.adapter.respond = respond
        job = self.execute('/plan Analyze the table and include review.')
        self.assertEqual(job['payload']['collaboration']['calledRoles'], [6, 4])
        self.assertEqual([a.rsplit('-r', 1)[1] for a, _, _ in self.adapter.calls[:2]], ['0', '0'])

    def test_selected_reviewer_can_check_supplied_work_without_extra_producer(self):
        self.adapter.plan = {'summary': 'Simple calculation with an independent check.', 'reviewRequired': True,
                            'tasks': [{'role': 4, 'task': 'Check the supplied calculation independently.'}]}
        job = self.execute('/plan Calculate the total and add review.')
        self.assertEqual(job['payload']['collaboration']['calledRoles'], [4])
        reviewer = next(p for a, _, p in self.adapter.calls if a.endswith('-r4'))
        self.assertIn('Check the supplied calculation independently.', reviewer)

    def test_failed_team_repair_never_exceeds_limit_or_claims_review(self):
        self.adapter.plan['reviewRequired'] = True
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

    def test_review_schema_requires_a_boolean(self):
        with self.assertRaises(RuntimeError):
            read_plan(json.dumps({'summary': 'x', 'tasks': [], 'answer': 'x', 'reviewRequired': 'yes'}))

    def test_missing_reviewer_requests_planner_repair_without_inventing_assignment(self):
        plan = {'summary': 'Build', 'reviewRequired': True, 'tasks': [
            {'role': 5, 'agent': 'a' * 24, 'task': 'Build a counter'}]}
        before = json.dumps(plan)
        with self.assertRaisesRegex(ValueError, 'no reviewer is assigned'):
            include_required_review(plan)
        self.assertEqual(json.dumps(plan), before)

    def test_missing_reviewer_can_be_selected_by_repair(self):
        self.adapter.plan = {'summary': 'Analyze with required review', 'reviewRequired': True,
                             'tasks': [{'role': 6, 'task': 'Analyze'}]}
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            answer = original(agent, session, prompt, **kwargs)
            if session.endswith('-planning-review-repair'):
                return json.dumps({'summary': 'Analyze then review', 'reviewRequired': True, 'tasks': [
                    {'role': 6, 'agent': 'builtin', 'task': 'Analyze'},
                    {'role': 4, 'agent': 'builtin', 'task': 'Review the analysis independently'}]})
            return answer
        self.adapter.respond = respond
        job = self.execute('/goal Have a second pair of eyes check the analysis.')
        self.assertEqual(job['payload']['collaboration']['calledRoles'], [6, 4])
        self.assertEqual(sum(s.endswith('-planning-review-repair') for _, s, _ in self.adapter.calls), 1)


class HiredReviewIntentTests(unittest.TestCase):
    import test_visitor_teams as hired_fixture
    setUp = hired_fixture.VisitorTeamTests.setUp
    start = hired_fixture.VisitorTeamTests.start
    execute = hired_fixture.VisitorTeamTests.execute

    def test_non_independent_review_requests_do_not_force_a_reviewer(self):
        # The simulated planner decides intent; these test dispatch, not LLM accuracy.
        prompts = [
            'Build a page and include a customer review section.',
            'Build a page without independent review. Include a product review section.',
            'Build a counter. As you implement it, double-check your code yourself.',
            'Summarize this text on a page: "Please include a reviewer."',
            '고객 리뷰를 보여주는 페이지를 만들어줘.',
            '직접 코드를 확인하면서 카운터를 만들어줘. 다른 검수자는 필요 없어.',
        ]
        self.adapter.selection['reviewRequired'] = False
        for task in prompts:
            with self.subTest(task=task):
                self.adapter.calls.clear()
                job = self.execute(self.start('/goal ' + task, teamMode='hired'))
                plan = job['payload']['collaboration']
                self.assertEqual(job['status'], 'done')
                self.assertFalse(plan['reviewRequired'])
                self.assertEqual(plan['calledRoles'], [5])
                self.assertTrue(plan['files']['5'])
                self.assertFalse(any('repair' in s for _, s, _ in self.adapter.calls))

    def test_missing_required_reviewer_is_reported_without_starting_production(self):
        self.adapter.selection = {'summary': 'The user requires independent review, but only one hire is available.',
                                  'reviewRequired': True, 'tasks': [], 'outcome': 'unavailable',
                                  'answer': 'Hire another Coding agent for the requested independent review.'}
        job = self.execute(self.start('/goal Build a page and have a different agent independently review it.', teamMode='hired'))
        self.assertEqual(job['payload']['collaboration']['calledRoles'], [])
        self.assertEqual(job['payload']['collaboration']['outcome'], 'unavailable')

    def test_explicit_independent_review_uses_the_two_selected_hires(self):
        reviewer = self.app.add_agent(self.owner, {'name': 'Checker', 'skills': ['builder']})['agentId']
        self.adapter.selection = {'summary': 'Build and independently review.', 'reviewRequired': True,
                                  'tasks': [
                                      {'role': 5, 'agent': self.owner, 'task': 'Build a counter.',
                                       'roleFit': 'Coding covers implementation.', 'requiredFiles': ['artifacts/counter.html']},
                                      {'role': 4, 'agent': reviewer, 'task': 'Independently inspect the counter.',
                                       'roleFit': 'Coding covers static code review.', 'requiredFiles': []}]}
        self.adapter.check_done = True  # Completion may not skip a requested reviewer.
        job = self.execute(self.start('/goal Build a counter and have another Coding agent independently review it.', teamMode='hired'))
        plan = job['payload']['collaboration']
        self.assertEqual(plan['calledRoles'], [5, 4])
        self.assertEqual([t['agent'] for t in plan['tasks']], [self.owner, reviewer])

    def test_explicit_review_cannot_assign_the_producer_as_its_own_reviewer(self):
        self.adapter.selection = {'summary': 'Invalid self-review', 'reviewRequired': True, 'tasks': [
            {'role': 5, 'agent': self.owner, 'task': 'Build', 'roleFit': 'Coding'},
            {'role': 4, 'agent': self.owner, 'task': 'Independently review', 'roleFit': 'Coding'}]}
        job = self.execute(self.start('/goal Build a counter and have a different agent independently review it.', teamMode='hired'))
        self.assertEqual(job['payload']['collaboration']['calledRoles'], [])
        self.assertEqual(job['payload']['collaboration']['outcome'], 'unavailable')
