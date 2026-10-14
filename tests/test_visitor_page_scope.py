"""Combined hired assignments export actual HTML without admitting unsolicited pages."""
import unittest

import test_visitor_teams as visitors
from studio import safe_file
from webpage_artifacts import PAGE_INSTRUCTIONS


class VisitorPageScopeTests(unittest.TestCase):
    setUp = visitors.VisitorTeamTests.setUp
    start = visitors.VisitorTeamTests.start
    execute = visitors.VisitorTeamTests.execute
    specialists = visitors.VisitorTeamTests.specialists

    def assign(self, role=6, required=None, write_page=True, page_path='artifacts/index.html', repair=False):
        self.adapter.auto_agents = False
        self.adapter.writes = False
        self.adapter.selection = {'summary': 'Pixel researches and builds the requested page.', 'tasks': [{
            'role': role, 'agent': self.owner, 'task': 'Complete the declared research and deliverables.',
            'expected': 'Cited findings and the requested saved files.', 'inputs': [],
            'requiredFiles': required if required is not None else ['artifacts/research-brief.md', 'artifacts/index.html']}]}
        original = self.adapter.respond

        def respond(agent, session, prompt, **kwargs):
            answer = original(agent, session, prompt, **kwargs)
            if '-working' in session or '-recovering' in session:
                workspace = self.adapter.agents[agent]
                safe_file(workspace, 'artifacts/research-brief.md').write_text('Fixture findings with limited evidence.')
                if write_page:
                    valid = not repair or '-recovering' in session
                    safe_file(workspace, page_path).write_text(
                        '<html><body><h1>Verified saved page</h1></body></html>' if valid else '<html>unfinished')
                return 'Completed research and saved artifacts/index.html.'
            return answer

        self.adapter.respond = respond

    def test_hired_analysis_design_and_research_can_deliver_declared_webpage(self):
        for role in (6, 7, 8):
            with self.subTest(role=role):
                self.assign(role)
                job = self.execute(self.start('/goal Pixel, research NVDA and build the webpage.', teamMode='hired'))
                plan = job['payload']['collaboration']
                self.assertEqual(plan['outcome'], 'complete')
                self.assertNotIn('handoffRecovery', plan)
                self.assertNotIn(str(role), plan.get('scopeWarnings', {}))
                self.assertCountEqual(plan['verifiedSources'][str(role)],
                                      ['artifacts/research-brief.md', 'artifacts/index.html'])
                self.assertEqual(len(plan['webpages'][str(role)]), 1)
                page = safe_file(self.app.workspace(self.manager), plan['webpages'][str(role)][0], True)
                self.assertIn('Verified saved page', page.read_text())
                prompt = self.specialists()[-1][2]
                self.assertIn(PAGE_INSTRUCTIONS, prompt)
                self.assertIn('Casey explicitly assigned webpage implementation', prompt)
                self.assertNotIn('report that mismatch and supply only', prompt)

    def test_research_only_assignment_still_rejects_unsolicited_html(self):
        self.assign(required=['artifacts/research-brief.md'])
        job = self.execute(self.start('/goal Pixel, research NVDA.', teamMode='hired'))
        plan = job['payload']['collaboration']
        self.assertEqual(plan['webpages']['6'], [])
        self.assertIn('6', plan['scopeWarnings'])
        self.assertNotIn(PAGE_INSTRUCTIONS, self.specialists()[0][2])
        self.assertTrue(safe_file(self.app.workspace(self.owner), 'artifacts/index.html', True).exists())

    def test_claim_without_file_remains_partial(self):
        self.assign(write_page=False)
        job = self.execute(self.start('/goal Pixel, research NVDA and build the webpage.', teamMode='hired'))
        plan = job['payload']['collaboration']
        self.assertEqual(plan['outcome'], 'partial')
        self.assertEqual(plan['handoffRecovery']['status'], 'failed')
        self.assertEqual(plan['webpages']['6'], [])

    def test_unrelated_page_does_not_satisfy_explicit_output(self):
        self.assign(page_path='artifacts/unassigned.html')
        job = self.execute(self.start('/goal Pixel, research NVDA and build the webpage.', teamMode='hired'))
        plan = job['payload']['collaboration']
        self.assertEqual(plan['outcome'], 'partial')
        self.assertEqual(plan['webpages']['6'], [])
        self.assertNotIn('artifacts/unassigned.html', plan['verifiedSources']['6'])

    def test_combined_page_repair_uses_fresh_code_session_and_keeps_brief(self):
        self.assign(repair=True)
        job = self.execute(self.start('/goal Pixel, research NVDA and build the webpage.', teamMode='hired'))
        plan = job['payload']['collaboration']
        self.assertEqual(plan['outcome'], 'complete')
        self.assertEqual(plan['handoffRecovery']['status'], 'delivered')
        self.assertTrue(self.specialists()[-1][1].endswith('-recovering'))
        self.assertCountEqual(plan['verifiedSources']['6'],
                              ['artifacts/research-brief.md', 'artifacts/index.html'])


if __name__ == '__main__':
    unittest.main()
