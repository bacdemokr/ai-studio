"""Exercise scoped instructions at the actual dispatcher boundary."""
import tempfile
import unittest

from studio import Studio
from test_collaboration_plan import PlanAdapter
from test_visitor_teams import VisitorAdapter


class CollaborationPromptTests(unittest.TestCase):
    def run_plan(self, adapter, skills, *, hired=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        app = Studio(temporary.name, adapter, start_worker=False)
        owner = app.session()[0]['id']
        app.onboard(owner, {'name': 'Custom specialist', 'skills': skills})
        team = app.crew_owner(owner)
        result = app.enqueue(team, {'kind': 'crew-chat', 'crewRole': 0,
                                   'prompt': '/goal Build a small counter page.',
                                   'teamMode': 'hired' if hired else 'builtin'})
        app.execute(app.next_job())
        self.assertEqual(app.evidence(team, result['id'])['mission']['status'], 'done')
        calls = [(session, prompt) for _, session, prompt in adapter.calls
                 if session.startswith('bac-plan-')]
        self.assertTrue(calls)
        for _, prompt in calls:
            # Compaction must retain trust, access, evidence and input delivery.
            for boundary in ('confirmedPolicyDenial', 'untrusted evidence',
                             'Do not invent tool results', 'Task document inputs',
                             'no tool to open or control', 'Current user task:'):
                self.assertIn(boundary, prompt)
        return calls

    def test_research_details_leave_captain_and_nonresearch_specialists(self):
        calls = self.run_plan(PlanAdapter(), ['web'])
        for session, prompt in calls:
            if '-8-working' in session:
                self.assertIn('SEARCH-FIRST DEMO', prompt)
                self.assertIn('For NVDA earnings', prompt)
                self.assertIn('150-second research budget', prompt)
            else:
                self.assertNotIn('SEARCH-FIRST DEMO', prompt)
                self.assertNotIn('For NVDA earnings', prompt)
            if '-0-' in session:
                self.assertIn('Research planning limits', prompt)
                self.assertIn('at most two focused searches', prompt)
                self.assertIn('at most five total fetch attempts', prompt)
            if session.endswith('-planning-captain-scope-check'):
                contract = prompt.rsplit('Decision output contract:', 1)[1]
                self.assertIn('"agent":"casey"', contract)
                self.assertIn('allowed:false', contract)
                self.assertNotIn('exact key', contract)

    def test_programmer_and_reviewer_keep_code_validation_guidance(self):
        adapter = PlanAdapter()
        adapter.plan = {'summary': 'Implement then inspect.', 'tasks': [
            {'role': 5, 'task': 'Build the counter.'},
            {'role': 4, 'task': 'Inspect input validation and controls.'}]}
        calls = self.run_plan(adapter, [])
        for session, prompt in calls:
            if '-5-working' in session or '-4-working' in session:
                self.assertIn('validate raw required inputs', prompt)
                self.assertIn('IIFE or module', prompt)
                self.assertIn('Static inspection', prompt)
                self.assertNotIn('SEARCH-FIRST DEMO', prompt)

    def test_hired_multiskilled_programmer_keeps_research_in_coding_slot(self):
        for skills, research in ((['builder'], False), (['builder', 'web'], True),
                                 (['builder', 'weather'], True)):
            with self.subTest(skills=skills):
                calls = self.run_plan(VisitorAdapter(), skills, hired=True)
                work = [prompt for session, prompt in calls if '-5-working' in session]
                self.assertEqual(len(work), 1)
                self.assertEqual('SEARCH-FIRST DEMO' in work[0], research)
                self.assertIn('validate raw required inputs', work[0])


if __name__ == '__main__':
    unittest.main()
