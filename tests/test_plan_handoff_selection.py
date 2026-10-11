"""Malformed planner file declarations are corrected before any specialist runs."""
import json
import unittest
import test_collaboration_plan as fixture
from collaboration_plan import read_plan
from plan_handoff import PlanHandoffError


class HandoffSelectionTests(unittest.TestCase):
    setUp = fixture.CollaborationTests.setUp
    start = fixture.CollaborationTests.start
    job = fixture.CollaborationTests.job

    def run_case(self, invalid, corrected, fails=False):
        self.adapter.plan = {'summary': 'Build a Naver page', 'tasks': [
            {'role': 5, 'agent': 'builtin', 'task': 'Build a Naver page', 'inputs': [], 'requiredFiles': invalid}]}
        original = self.adapter.respond
        repairs = []
        def respond(agent, session, prompt, **kwargs):
            if session.endswith('-planning-input-repair'):
                self.assertFalse(any(not a.endswith('-r0') for a, _, _ in self.adapter.calls))
                self.assertIn('No tools are available during this decision.', prompt)
                self.assertIn('artifacts/index.html', prompt)
                self.assertIn('selected agent identities', prompt)
                repairs.append(session)
                return json.dumps({'summary': 'Build a Naver page', 'tasks': [
                    {'role': 5, 'agent': 'builtin', 'task': 'Build a Naver page', 'inputs': [], 'requiredFiles': corrected}]})
            answer = original(agent, session, prompt, **kwargs)
            if agent.endswith('-r5'):
                (self.adapter.agents[agent] / 'artifacts/index.html').write_text(
                    '<!doctype html><html><head><title>Naver</title></head><body><h1>Naver</h1></body></html>')
            return answer
        self.adapter.respond = respond
        result = self.start('/plan Build a Naver page')
        if fails:
            with self.assertRaises(PlanHandoffError):
                self.app.execute(self.app.next_job())
        else:
            self.app.execute(self.app.next_job())
        self.assertEqual(len(repairs), 1)
        return self.job(result)

    def test_root_html_is_corrected_before_dispatch(self):
        job = self.run_case(['index.html'], ['artifacts/index.html'])
        self.assertEqual(job['status'], 'done')
        plan = job['payload']['collaboration']
        self.assertEqual(plan['handoffSelectionRecovery']['status'], 'corrected')
        self.assertEqual(plan['calledRoles'], [5])
        self.assertEqual(plan['tasks'][0]['requiredFiles'], ['artifacts/index.html'])
        self.assertTrue(plan['outputs']['5']['files'])
        self.assertNotIn('handoffRecovery', plan)

    def test_second_invalid_plan_stops_without_specialists(self):
        job = self.run_case(['index.html'], ['artifacts/../index.html'], fails=True)
        self.assertEqual(job['payload']['collaboration']['handoffSelectionRecovery']['status'], 'failed')
        self.assertFalse(any(not a.endswith('-r0') for a, _, _ in self.adapter.calls))

    def test_malformed_list_is_recoverable(self):
        job = self.run_case(None, ['artifacts/index.html'])
        self.assertEqual(job['payload']['collaboration']['handoffSelectionRecovery']['status'], 'corrected')

    def test_invalid_paths_remain_rejected(self):
        for value in (None, 'index.html', ['index.html'], ['/artifacts/index.html'],
                      ['artifacts/../index.html'], ['artifacts/./index.html'],
                      ['artifacts//index.html'], ['artifacts\\index.html'],
                      ['artifacts/page.exe'], ['artifacts/'], [123], ['artifacts/a.md'] * 13):
            with self.subTest(value=value), self.assertRaises(PlanHandoffError):
                read_plan(json.dumps({'summary':'Build', 'tasks':[{'role':5,'task':'Build', 'requiredFiles':value}]}))

    def test_supported_paths_still_validate(self):
        for ext in ('md', 'txt', 'csv', 'json', 'py', 'js', 'css', 'html'):
            path = 'artifacts/subdir/file.' + ext
            with self.subTest(ext=ext):
                plan = read_plan(json.dumps({'summary':'Build', 'tasks':[{'role':5,'task':'Build', 'requiredFiles':[path]}]}))
                self.assertEqual(plan['tasks'][0]['requiredFiles'], [path])


if __name__ == '__main__':
    unittest.main()
