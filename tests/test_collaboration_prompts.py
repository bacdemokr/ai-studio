"""Exercise scoped instructions at the actual dispatcher boundary."""
import tempfile
import unittest

from studio import Studio
from test_collaboration_plan import PlanAdapter
from test_visitor_teams import VisitorAdapter
from collaboration_prompts import planning_output_contract


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
                self.assertIn('Research shares the overall demo time budget', prompt)
            else:
                self.assertNotIn('SEARCH-FIRST DEMO', prompt)
                self.assertNotIn('For NVDA earnings', prompt)
            if '-0-' in session and not session.endswith(('-planning-captain-scope-check', '-planning-scope-check')):
                self.assertIn('Research planning limits', prompt)
                self.assertIn('at most two focused searches', prompt)
                self.assertIn('at most five total fetch attempts', prompt)
            if session.endswith(('-planning-captain-scope-check', '-planning-scope-check')):
                self.assertNotIn('Research planning limits', prompt)
                self.assertNotIn('A final progress review may authorize', prompt)
                self.assertIn('equipped', prompt)
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
                self.assertIn('Number.isInteger on whole-count inputs', prompt)
                self.assertIn('visible, enabled start control', prompt)
                self.assertIn('IIFE or module', prompt)
                self.assertIn('Static inspection', prompt)
                self.assertNotIn('SEARCH-FIRST DEMO', prompt)
                self.assertEqual('Static review:' in prompt, '-4-working' in session)
                self.assertEqual('eight reads / 18000' in prompt, '-4-working' in session)
                # Saving must not trigger another read, while an independent
                # review still receives permission and guidance to inspect code.
                self.assertIn('successful write/edit results as save confirmation', prompt)
                self.assertNotIn('verify they exist before claiming', prompt)
                self.assertIn('reuse complete supplied previews and successful reads', prompt)
                self.assertIn('This inventory is not a reading checklist', prompt)
                self.assertIn('assigned independent review may need to read existing source', prompt)
                self.assertIn('confirms saving, not correctness or browser execution', prompt)

    def test_hired_multiskilled_programmer_keeps_research_in_coding_slot(self):
        for skills, research in ((['builder'], False), (['builder', 'web'], True),
                                 (['builder', 'weather'], True)):
            with self.subTest(skills=skills):
                calls = self.run_plan(VisitorAdapter(), skills, hired=True)
                work = [prompt for session, prompt in calls if '-5-working' in session]
                self.assertEqual(len(work), 1)
                self.assertEqual('SEARCH-FIRST DEMO' in work[0], research)
                self.assertIn('Number.isInteger on whole-count inputs', work[0])
                self.assertIn('visible, enabled start control', work[0])

    def test_hired_planning_has_one_complete_mode_specific_contract(self):
        calls = self.run_plan(VisitorAdapter(), ['builder'], hired=True)
        planning = next(p for s, p in calls if s.endswith('-planning'))
        self.assertIn(planning_output_contract('hired'), planning)
        self.assertEqual(planning.count('Decision output contract:'), 1)
        self.assertIn('reviewRequired (boolean)', planning)
        self.assertIn('role (integer assignment slot), agent (string)', planning)
        self.assertIn('Never use "builtin" or an agent name.', planning)
        self.assertNotIn('For a working webpage or code prototype, select Cody.', planning)
        self.assertNotIn('normally assign Cody alone', planning)
        self.assertNotIn('Return ONLY JSON {"summary":"short plan', planning)

    def test_builtin_and_mixed_contracts_describe_the_available_identity_types(self):
        calls = self.run_plan(PlanAdapter(), [])
        planning = next(p for s, p in calls if s.endswith('-planning'))
        self.assertIn(planning_output_contract('builtin'), planning)
        self.assertIn('agent must be "builtin"', planning)
        mixed = planning_output_contract('mixed')
        self.assertIn('exact available hired key, or "builtin"', mixed)
        for mode in ('builtin', 'mixed', 'hired'):
            contract = planning_output_contract(mode)
            for field in ('summary', 'reviewRequired', 'requestedAgents', 'excludedAgents',
                          'declinedAgents', 'requestedFormats', 'unassignedRequirements', 'tasks',
                          'roleFit', 'inputs', 'requiredFiles', 'outcome', 'nonempty answer'):
                self.assertIn(field, contract)


if __name__ == '__main__':
    unittest.main()
