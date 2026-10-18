"""Saved handoff contracts and saved research after interrupted replies."""
import unittest
import json
from pathlib import Path

import test_plan_handoff as handoff_fixture
import test_visitor_teams as visitor_fixture
from agent_runtime import GatewayError


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


class TaskOnlyExampleTests(unittest.TestCase):
    setUp = visitor_fixture.VisitorTeamTests.setUp
    enqueue = visitor_fixture.VisitorTeamTests.start
    execute = visitor_fixture.VisitorTeamTests.execute

    def test_casey_can_assign_one_equipped_hire_for_game_example(self):
        # Planner/dispatch fixture only: the saved counter is not a game-quality test.
        goals = json.loads((Path(__file__).resolve().parents[1] / 'src/goal-examples.json').read_text())
        prompt = next(g['prompt'] for g in goals if g['id'] == 'pong')
        self.adapter.selection['tasks'][0]['agent'] = self.owner
        job = self.execute(self.enqueue(prompt, teamMode='hired'))
        self.assertEqual(job['status'], 'done')
        plan = job['payload']['collaboration']
        self.assertEqual(plan.get('outcome', 'complete'), 'complete')
        self.assertEqual(plan['calledRoles'], [5])
        self.assertEqual(plan['visitorBindings']['5']['key'], self.owner)
        planning = [call for call in self.adapter.calls if call[1].endswith('-planning')]
        self.assertTrue(planning)
        self.assertIn(prompt.removeprefix('/goal '), planning[0][2])


if __name__ == '__main__':
    unittest.main()
