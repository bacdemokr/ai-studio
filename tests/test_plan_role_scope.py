"""Scope regressions: a research-and-build request must not become researcher-only."""
import json
import unittest
import test_collaboration_plan as collaboration
from webpage_artifacts import PAGE_INSTRUCTIONS


class PlanRoleScopeTests(unittest.TestCase):
    setUp = collaboration.CollaborationTests.setUp
    start = collaboration.CollaborationTests.start
    job = collaboration.CollaborationTests.job

    def test_researcher_page_cannot_shortcut_programmer_or_reach_handoff(self):
        self.adapter.plan['tasks'] = [
            {'role': 8, 'task': 'Research AMD only', 'expected': 'Cited evidence brief'},
            {'role': 5, 'task': 'Implement the webpage', 'expected': 'A working HTML file'},
            {'role': 4, 'task': 'Review the HTML', 'expected': 'Static findings'}]
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            if session.endswith('-working') and agent.endswith('-r8'):
                original(agent, session, prompt, **kwargs)
                (self.adapter.agents[agent] / 'artifacts/research.md').write_text('Verified AMD source brief')
                (self.adapter.agents[agent] / 'artifacts/unassigned.html').write_text('<html><body>OUT_OF_SCOPE</body></html>')
                return 'Research completed. I also built the entire webpage in artifacts/unassigned.html.'
            if '-checking-8' in session:
                original(agent, session, prompt, **kwargs)
                # Even an incorrect model checkpoint cannot accept rejected HTML.
                return json.dumps({'done': True, 'reason': 'Avery already built everything.', 'answer': 'Done'})
            if session.endswith('-working') and agent.endswith('-r5'):
                original(agent, session, prompt, **kwargs)
                workspace = self.adapter.agents[agent]
                self.assertEqual(list((workspace / 'inbox').glob('*.html')), [])
                self.assertTrue(any('Verified AMD source brief' in f.read_text() for f in (workspace / 'inbox').glob('*.md')))
                self.assertIn('scopeWarning', prompt)
                (workspace / 'artifacts/implementation.html').write_text('<html><body>WADE_IMPLEMENTATION</body></html>')
                return 'Implemented the page from the research brief.'
            if session.endswith('-working') and agent.endswith('-r4'):
                pages = list((self.adapter.agents[agent] / 'inbox').glob('*.html'))
                self.assertEqual(len(pages), 1)
                self.assertIn('WADE_IMPLEMENTATION', pages[0].read_text())
            return original(agent, session, prompt, **kwargs)
        self.adapter.respond = respond
        result = self.start('/plan Investigate AMD latest blogs and build a webpage.')
        self.app.execute(self.app.next_job())
        plan = self.job(result)['payload']['collaboration']
        self.assertEqual(plan['calledRoles'], [8, 5, 4])
        self.assertFalse(plan['checks'][0]['done'])
        self.assertEqual(plan['webpages']['8'], [])
        self.assertEqual(len(plan['webpages']['5']), 1)
        self.assertEqual(plan['outputs']['8']['task'], 'Research AMD only')
        self.assertEqual(plan['outputs']['8']['expected'], 'Cited evidence brief')
        team = self.app.crew_owner(self.owner)
        self.assertFalse(list((self.app.workspace(team) / 'artifacts').glob('page-*-r8-*.html')))
        self.assertTrue((self.app.workspace(team, 8) / 'artifacts/unassigned.html').exists())

    def test_only_programmer_gets_page_creation_instruction(self):
        for roles in ([8, 5, 4], [2, 3, 6], [7]):
            self.adapter.plan['tasks'] = [{'role': role, 'task': 'Perform your scoped contribution'} for role in roles]
            self.adapter.calls.clear()
            result = self.start('/plan Research AMD and build a webpage.')
            self.app.execute(self.app.next_job())
            self.assertEqual(self.job(result)['status'], 'done')
            for agent, session, prompt in self.adapter.calls:
                role = int(agent.rsplit('-r', 1)[1])
                if session.endswith('-working'):
                    self.assertEqual(PAGE_INSTRUCTIONS in prompt, role == 5)
                    self.assertIn('Complete ONLY the contribution Casey assigned', prompt)
                    self.assertNotIn('This run can call at most three specialists', prompt)
                    self.assertIn('Your /plan role boundary:', prompt)
                elif role == 0:
                    self.assertIn('This run can call at most three specialists', prompt)

    def test_legitimate_early_finish_without_out_of_scope_page_still_allowed(self):
        self.adapter.plan['tasks'] = [{'role':8, 'task':'Research'}, {'role':4, 'task':'Optional review'}]
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            result = original(agent, session, prompt, **kwargs)
            if '-checking-' in session:
                return json.dumps({'done':True, 'reason':'The requested cited brief is complete.', 'answer':'The cited brief is sufficient; Riley is not needed.'})
            return result
        self.adapter.respond = respond
        result = self.start('/plan Research AMD and give me a cited brief.')
        self.app.execute(self.app.next_job())
        self.assertEqual(self.job(result)['payload']['collaboration']['calledRoles'], [8])


if __name__ == '__main__':
    unittest.main()
