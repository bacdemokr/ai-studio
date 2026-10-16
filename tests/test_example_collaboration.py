"""Explicit collaboration contracts and saved research after interrupted replies."""
import unittest
import json

import test_plan_handoff as handoff_fixture
import test_visitor_teams as visitor_fixture
from agent_runtime import GatewayError
from collaboration_plan import validate_requested_team, PlanSelectionError


class RequestedTeamTests(unittest.TestCase):
    task = 'Use two different specialists to analyze data, then build a page.'

    def test_rejects_one_identity_even_when_assigned_twice(self):
        for tasks in ([{'role': 5}], [{'role': 6, 'agent': 'same'}, {'role': 5, 'agent': 'same'}], []):
            with self.subTest(tasks=tasks), self.assertRaises(PlanSelectionError):
                validate_requested_team({'tasks': tasks}, self.task)

    def test_accepts_real_pair_or_honest_gap_without_affecting_ordinary_goals(self):
        validate_requested_team({'tasks': [{'role': 6}, {'role': 5}]}, self.task)
        validate_requested_team({'tasks': [{'role': 6, 'agent': 'analyst'}, {'role': 5, 'agent': 'coder'}]}, self.task)
        validate_requested_team({'tasks': [], 'outcome': 'unavailable'}, self.task)
        validate_requested_team({'tasks': [{'role': 6}], 'unassignedRequirements': ['No second specialist.']}, self.task)
        validate_requested_team({'tasks': [{'role': 5}]}, 'Build a simple page.')
        validate_requested_team({'tasks': []}, '> Use two different specialists to analyze data.')

    def test_enforces_explicit_one_and_three_specialist_examples(self):
        one = '/goal Use one specialist with Coding to build a calculator.'
        validate_requested_team({'tasks': [{'role': 5}]}, one)
        with self.assertRaises(PlanSelectionError):
            validate_requested_team({'tasks': [{'role': 7}, {'role': 5}]}, one)
        three = '/goal Use three different specialists to research, design and build a page.'
        validate_requested_team({'tasks': [{'role': 8}, {'role': 7}, {'role': 5}]}, three)
        with self.assertRaises(PlanSelectionError):
            validate_requested_team({'tasks': [{'role': 8}, {'role': 5}]}, three)


class SavedResearchTests(unittest.TestCase):
    setUp = handoff_fixture.PlanHandoffTests.setUp
    start = handoff_fixture.PlanHandoffTests.start
    job = handoff_fixture.PlanHandoffTests.job
    configure = handoff_fixture.PlanHandoffTests.configure
    run_plan = handoff_fixture.PlanHandoffTests.run_plan

    def fail_after_first_reply(self, reason='request_failed', reject_evidence=False):
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            if reject_evidence and '-checking-8' in session:
                return json.dumps({'done': False, 'readyForNext': False, 'reason': 'Evidence does not support the comparison.'})
            answer = original(agent, session, prompt, **kwargs)
            if agent.endswith('-r8') and len(self.research_sessions) == 1:
                raise GatewayError('The closing reply failed after tool execution.', reason)
            return answer
        self.adapter.respond = respond

    def test_saved_brief_goes_to_captain_before_programmer_without_replaying_research(self):
        self.configure(initial='saved')
        self.fail_after_first_reply()
        plan = self.run_plan()['payload']['collaboration']
        self.assertEqual(plan['calledRoles'], [8, 5])
        self.assertEqual(len(self.research_sessions), 1)
        self.assertEqual(plan['savedResearchRecovery'][0]['reason'], 'request_failed')
        self.assertIn('unverified partial work', plan['outputs']['8']['answer'])
        self.assertNotIn('handoffRecovery', plan)

    def test_saved_but_unusable_evidence_still_blocks_dependents(self):
        self.configure(initial='saved')
        self.fail_after_first_reply(reject_evidence=True)
        plan = self.run_plan()['payload']['collaboration']
        self.assertEqual(plan['calledRoles'], [8])
        self.assertEqual(plan['outcome'], 'partial')
        self.assertEqual(plan['skippedRoles'], [5])

    def test_unrelated_file_does_not_count_as_the_required_brief(self):
        self.configure(initial='unrelated')
        self.fail_after_first_reply()
        plan = self.run_plan()['payload']['collaboration']
        self.assertEqual(plan['calledRoles'], [8])
        self.assertNotIn('savedResearchRecovery', plan)
        self.assertEqual(plan['outcome'], 'partial')

    def test_connection_failure_is_not_treated_as_a_failed_closing_reply(self):
        self.configure(initial='saved')
        self.fail_after_first_reply(reason='unavailable')
        plan = self.run_plan()['payload']['collaboration']
        self.assertEqual(plan['calledRoles'], [8])
        self.assertNotIn('savedResearchRecovery', plan)
        self.assertEqual(plan['outcome'], 'partial')


class SingleHireExampleTests(unittest.TestCase):
    setUp = visitor_fixture.VisitorTeamTests.setUp
    enqueue = visitor_fixture.VisitorTeamTests.start
    execute = visitor_fixture.VisitorTeamTests.execute

    def test_one_hire_gets_guidance_without_model_calls_or_a_runtime_error(self):
        result = self.enqueue('/goal Use two different specialists to design and build a game.', teamMode='hired')
        job = self.execute(result)
        self.assertEqual(job['status'], 'done')
        self.assertEqual(job['payload']['collaboration']['outcome'], 'unavailable')
        self.assertEqual(job['payload']['collaboration']['calledRoles'], [])
        self.assertIn('Hired + Standby', str(job['result']))
        self.assertEqual(self.adapter.calls, [])


if __name__ == '__main__':
    unittest.main()
