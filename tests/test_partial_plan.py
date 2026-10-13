import json
import unittest
from unittest.mock import patch
from studio import Problem
from collaboration_plan import read_plan, read_checkpoint
import test_collaboration_plan as fixture


class PartialPlanTests(unittest.TestCase):
    setUp = fixture.CollaborationTests.setUp
    start = fixture.CollaborationTests.start
    job = fixture.CollaborationTests.job

    def test_connection_check_failure_after_delivery_keeps_preview_without_retry(self):
        self.adapter.plan['tasks'] = [{'role': 5, 'task': 'Build a counter.'}]
        respond = self.adapter.respond
        def write_page(agent, session, prompt, **kwargs):
            answer = respond(agent, session, prompt, **kwargs)
            if agent.endswith('-r5'):
                (self.adapter.agents[agent] / 'artifacts' / 'counter.html').write_text(
                    '<!doctype html><html><body><h1>Saved counter</h1><button>0</button></body></html>')
            return answer
        self.adapter.respond = write_page
        prepare = self.app.prepare_builtin_crew
        def disconnect_before_synthesis(owner, role, member):
            if role == 0 and any(call[0].endswith('-r5') for call in self.adapter.calls):
                raise Problem('Model not connected. Configure a Local model or API in Settings.', 503)
            return prepare(owner, role, member)
        result = self.start('/goal Build a counter.')
        with patch.object(self.app, 'prepare_builtin_crew', side_effect=disconnect_before_synthesis):
            self.app.execute(self.app.next_job())
        job = self.job(result)
        self.assertEqual(job['status'], 'done')
        self.assertEqual(job['payload']['collaboration']['outcome'], 'partial')
        self.assertIn('Model not connected', job['result']['answer'])
        pages = [f for f in job['result']['files'] if f.endswith('.html')]
        self.assertEqual(len(pages), 1)
        self.assertIn('Saved counter', self.app.available_file(self.owner, pages[0]).read_text())
        self.assertEqual(len(self.adapter.calls), 2, 'Do not repeat completed work or retry the model')
        self.assertEqual(self.adapter.reaction_calls, [])

    def test_connection_failure_before_any_contribution_is_not_a_partial_success(self):
        result = self.start()
        with patch.object(self.app, 'prepare_builtin_crew', side_effect=Problem('Not connected', 503)):
            with self.assertRaisesRegex(Problem, 'Not connected'):
                self.app.execute(self.app.next_job())
        self.assertEqual(self.adapter.calls, [])

    def test_partial_requires_specific_unfinished_work(self):
        for remaining in (None, [], [''], [True], 'More work', ['x'] * 9):
            with self.subTest(remaining=remaining), self.assertRaises(RuntimeError):
                read_checkpoint(json.dumps({'done': True, 'outcome': 'partial', 'reason': 'Budget reached',
                                            'answer': 'A useful draft', 'remaining': remaining}))
        with self.assertRaises(RuntimeError):
            read_checkpoint(json.dumps({'done': False, 'outcome': 'partial', 'reason': 'Continue', 'remaining': ['Testing']}))
        value = read_plan(json.dumps({'summary': 'Partial explanation', 'tasks': [], 'outcome': 'partial',
                                    'answer': 'Provided a manual plan; deployment remains.', 'remaining': ['Deployment']}))
        self.assertEqual(value['remaining'], ['Deployment'])

    def test_after_three_specialists_returns_partial_and_saved_file_without_fourth_call(self):
        self.adapter.plan['tasks'] = [{'role': 6, 'task': 'Analyze'}, {'role': 7, 'task': 'Design'}, {'role': 5, 'task': 'Build'}]
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            answer = original(agent, session, prompt, **kwargs)
            if agent.endswith('-r5'):
                (self.adapter.agents[agent] / 'artifacts' / 'prototype.html').write_text('<html><body>Useful prototype</body></html>')
            if session.endswith('-reviewing'):
                self.assertIn('no fourth specialist will be called', prompt)
                return json.dumps({'done': True, 'outcome': 'partial', 'reason': 'Prototype built; execution and deployment are unavailable.',
                                   'answer': 'The prototype is ready to preview. It has not been browser-tested or deployed.',
                                   'remaining': ['Browser-executed tests', 'Deployment with an authenticated service']})
            return answer
        self.adapter.respond = respond
        result = self.start('/plan Build and test a dashboard, then deploy it.')
        self.app.execute(self.app.next_job())
        job = self.job(result); plan = job['payload']['collaboration']
        self.assertEqual(len(self.adapter.calls), 7)
        self.assertEqual(plan['calledRoles'], [6, 7, 5])
        self.assertEqual(plan['outcome'], 'partial')
        self.assertEqual(plan['remaining'], plan['checks'][-1]['remaining'])
        self.assertEqual(job['status'], 'done')
        html = [path for path in job['result']['files'] if path.endswith('.html')]
        self.assertEqual(len(html), 1)
        self.assertIn('Useful prototype', self.app.available_file(self.owner, html[0]).read_text())

    def test_early_partial_keeps_outputs_and_identifies_uncalled_roles(self):
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            answer = original(agent, session, prompt, **kwargs)
            if '-checking-' in session:
                return json.dumps({'done': True, 'outcome': 'partial', 'reason': 'Research delivered; private-system access is unavailable.',
                                   'answer': 'Here is the verified research. Private data remains unverified.', 'remaining': ['Private-system validation']})
            return answer
        self.adapter.respond = respond
        result = self.start(); self.app.execute(self.app.next_job())
        plan = self.job(result)['payload']['collaboration']
        self.assertEqual(plan['calledRoles'], [8])
        self.assertEqual(plan['skippedRoles'], [6, 7])
        self.assertEqual(plan['remaining'], ['Private-system validation'])
        self.assertEqual(set(plan['outputs']), {'8'})


if __name__ == '__main__':
    unittest.main()
