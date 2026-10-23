import json
import tempfile
import unittest

from test_collaboration_plan import PlanAdapter
from test_studio import Studio


class DirectScopeAdapter(PlanAdapter):
    def __init__(self, decision, repair=None):
        super().__init__()
        self.plan = {'summary': 'I can answer directly.', 'tasks': [], 'answer': 'Direct answer.'}
        self.decision = decision
        self.repair = repair
        self.scope_checks = 0

    def respond(self, agent, session, prompt, **kwargs):
        if session.endswith('-planning-captain-scope-check'):
            self.calls.append((agent, session, prompt))
            self.scope_checks += 1
            if self.repair and self.scope_checks > 1:
                return json.dumps({'decisions': [{'agent': 'casey', 'allowed': True,
                    'reason': 'The repaired plan delegates analysis rather than doing it in the assignment.'}]})
            return json.dumps({'decisions': [self.decision]})
        if session.endswith('-planning-input-repair'):
            self.calls.append((agent, session, prompt))
            return json.dumps(self.repair or {
                'summary': 'Missing a suitable skill.', 'tasks': [],
                'outcome': 'unavailable', 'answer': 'Please hire an agent with the required skill.',
            })
        return super().respond(agent, session, prompt, **kwargs)


class CaptainDirectScopeTests(unittest.TestCase):
    def run_case(self, decision, repair=None, proposed=None):
        with tempfile.TemporaryDirectory() as directory:
            adapter = DirectScopeAdapter(decision, repair)
            if proposed is not None:
                adapter.plan = proposed
            app = Studio(directory, adapter, start_worker=False)
            owner = app.session()[0]['id']
            app.onboard(owner, {'name': 'Personal', 'skills': ['web']})
            result = app.enqueue(app.crew_owner(owner), {
                'kind': 'crew-chat', 'crewRole': 0, 'prompt': '/goal Help with the requested work.',
            })
            app.execute(app.next_job())
            job = next(j for j in app.state(owner)['crewChats'] if j['id'] == result['id'])
            return job, adapter.calls

    def test_in_scope_conversation_keeps_direct_answer_without_specialist(self):
        job, _ = self.run_case({'agent': 'casey', 'allowed': True, 'reason': 'Team explanation.'})
        plan = job['payload']['collaboration']
        self.assertEqual(plan['outcome'], 'complete')
        self.assertEqual(plan['calledRoles'], [])
        self.assertEqual(job['result']['answer'], 'Direct answer.')

    def test_out_of_scope_direct_work_gets_one_replan_and_honest_refusal(self):
        job, calls = self.run_case({'agent': 'casey', 'allowed': False, 'reason': 'Specialist work, not coordination.'})
        plan = job['payload']['collaboration']
        self.assertEqual(plan['outcome'], 'unavailable')
        self.assertEqual(plan['calledRoles'], [])
        self.assertEqual(plan['inputSelectionRecovery']['status'], 'corrected')
        self.assertEqual(sum(s.endswith('-planning-input-repair') for _, s, _ in calls), 1)
        self.assertNotIn('Direct answer.', job['result']['answer'])

    def test_scope_check_can_replan_to_an_available_specialist(self):
        repair = {
            'summary': 'Delegate to the available analyst.',
            'tasks': [{'role': 6, 'agent': 'builtin', 'task': 'Analyze the supplied figures.'}],
        }
        job, _ = self.run_case({'agent': 'casey', 'allowed': False, 'reason': 'Analysis requires an equipped specialist.'}, repair)
        self.assertEqual(job['payload']['collaboration']['calledRoles'], [6])
        self.assertEqual(job['payload']['collaboration']['outcome'], 'complete')

    def test_malformed_scope_decision_does_not_release_unchecked_answer(self):
        job, _ = self.run_case({'agent': 'casey', 'allowed': 'true', 'reason': 'Not a boolean.'})
        self.assertEqual(job['payload']['collaboration']['outcome'], 'unavailable')
        self.assertNotIn('Direct answer.', job['result']['answer'])

    def test_delegating_rendering_does_not_skip_caseys_own_scope_check(self):
        proposed = {'summary': 'I calculated the rates and identified the riskiest inventory.',
            'tasks': [{'role': 5, 'agent': 'builtin',
                       'task': 'Render my computed risk ranking and my recommended action as HTML.'}]}
        job, calls = self.run_case({'agent': 'casey', 'allowed': False,
            'reason': 'Casey performed the analysis itself inside the plan.'}, proposed=proposed)
        plan = job['payload']['collaboration']
        self.assertEqual(plan['outcome'], 'unavailable')
        self.assertEqual(plan['calledRoles'], [])
        check = next(prompt for _, session, prompt in calls if session.endswith('-planning-captain-scope-check'))
        self.assertIn(proposed['tasks'][0]['task'], check)
        self.assertEqual(sum(s.endswith('-planning-input-repair') for _, s, _ in calls), 1)


if __name__ == '__main__':
    unittest.main()
