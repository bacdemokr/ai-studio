import json
import unittest
from unittest.mock import patch
import test_collaboration_plan as fixture
from collaboration_plan import read_plan
from plan_handoff import required_files, missing_files


class PlanHandoffTests(unittest.TestCase):
    setUp = fixture.CollaborationTests.setUp
    start = fixture.CollaborationTests.start
    job = fixture.CollaborationTests.job

    def configure(self, repair='save', initial='missing'):
        self.adapter.plan['tasks'] = [
            {'role': 8, 'task': 'Research only', 'expected': 'Save artifacts/brief.md with sources.'},
            {'role': 5, 'task': 'Build from the research brief'}]
        original = self.adapter.respond
        self.research_sessions = []
        def respond(agent, session, prompt, **kwargs):
            result = original(agent, session, prompt, **kwargs)
            if agent.endswith('-r8'):
                self.research_sessions.append(session)
                path = self.adapter.agents[agent] / 'artifacts/brief.md'
                if len(self.research_sessions) == 1:
                    if initial == 'blank': path.write_text('  \n')
                    if initial == 'unrelated': path.with_name('unrelated.md').write_text('Unrelated data')
                    if initial == 'saved': path.write_text('Evidence: https://example.com/source - source says X; pricing unknown.')
                    return 'Research complete. Saved artifacts/brief.md.'
                self.assertIn('Do not research again', prompt)
                if repair == 'save':
                    path.write_text('Evidence: https://example.com/source - source says X; pricing unknown.')
                elif repair == 'error': raise RuntimeError('Tool failure')
                elif repair == 'cancel':
                    self.app.decision(self.app.crew_owner(self.owner), self.active_job['id'], 'cancel')
                return 'Saved cited evidence. Pricing remains unknown.'
            if agent.endswith('-r5'):
                copies = list((self.adapter.agents[agent] / 'inbox').glob('*.md'))
                self.assertTrue(any('https://example.com/source' in p.read_text() for p in copies))
            return result
        self.adapter.respond = respond

    def run_plan(self):
        self.active_job = self.start('/plan Compare the companies and build an HTML page.')
        self.app.execute(self.app.next_job())
        return self.job(self.active_job)

    def test_recovers_in_same_session_before_programmer(self):
        self.configure()
        job = self.run_plan(); plan = job['payload']['collaboration']
        self.assertEqual(self.research_sessions[0], self.research_sessions[1])
        self.assertEqual(len(self.research_sessions), 2)
        self.assertEqual(plan['calledRoles'], [8, 5])
        self.assertEqual(plan['handoffRecovery']['status'], 'delivered')
        self.assertEqual(plan['outputs']['8']['handoffStatus'], 'verified')
        self.assertIn('Pricing remains unknown', plan['outputs']['8']['answer'])
        self.assertIn('No further revision is allowed', self.adapter.calls[-1][2])
        for role in (8, 5):
            self.assertFalse(list((self.app.workspace(self.app.crew_owner(self.owner), role)/'inbox').glob('plan-*')))

    def test_unsaved_blank_unrelated_and_failed_repair_stop_dependents(self):
        for initial, repair in [('missing','missing'), ('blank','missing'), ('unrelated','missing'), ('missing','error')]:
            with self.subTest(initial=initial, repair=repair):
                self.configure(repair, initial)
                job = self.run_plan(); plan = job['payload']['collaboration']
                self.assertEqual(job['status'], 'done')
                self.assertEqual(plan['outcome'], 'partial')
                self.assertEqual(plan['calledRoles'], [8])
                self.assertEqual(plan['handoffRecovery']['status'], 'failed')
                self.assertEqual(plan['outputs']['8']['handoffStatus'], 'missing')
                self.assertNotIn('5', plan['outputs'])
                # Restore fixture for the next case to avoid wrapping responders.
                self.adapter.respond = fixture.PlanAdapter.respond.__get__(self.adapter)

    def test_real_saved_handoff_needs_no_recovery(self):
        self.configure(initial='saved')
        plan = self.run_plan()['payload']['collaboration']
        self.assertNotIn('handoffRecovery', plan)
        self.assertEqual(len(self.research_sessions), 1)

    def test_captain_blocks_unusable_evidence_even_when_file_exists(self):
        self.configure(initial='saved')
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            if '-checking-8' in session:
                return json.dumps({'done':False, 'readyForNext':False, 'reason':'The sources do not support the requested comparison.'})
            return original(agent, session, prompt, **kwargs)
        self.adapter.respond = respond
        plan = self.run_plan()['payload']['collaboration']
        self.assertEqual(plan['calledRoles'], [8])
        self.assertEqual(plan['outcome'], 'partial')
        self.assertEqual(plan['skippedRoles'], [5])

    def test_stale_existing_file_is_not_a_new_handoff(self):
        self.configure(repair='missing')
        workspace = self.app.workspace(self.app.crew_owner(self.owner), 8)
        (workspace/'artifacts').mkdir(parents=True, exist_ok=True)
        (workspace/'artifacts/brief.md').write_text('Evidence from an older task')
        plan = self.run_plan()['payload']['collaboration']
        self.assertEqual(plan['calledRoles'], [8])
        self.assertEqual(plan['outcome'], 'partial')

    def test_cancel_during_recovery_does_not_start_programmer(self):
        self.configure(repair='cancel')
        job = self.run_plan()
        self.assertEqual(job['status'], 'cancelled')
        self.assertEqual(job['payload']['collaboration']['calledRoles'], [8])

    def test_contract_rejects_unsafe_paths(self):
        for path in ['/tmp/brief.md', 'artifacts/../brief.md', 'artifacts/a.exe', 'artifacts/a\\b.md']:
            with self.subTest(path=path), self.assertRaises(RuntimeError):
                read_plan(json.dumps({'summary':'Test', 'tasks':[{'role':8,'task':'Research','requiredFiles':[path]}]}))
        self.assertEqual(required_files({'task':'Read artifacts/brief.md and review it.'}), [])
        self.assertEqual(missing_files({'requiredFiles':['artifacts/index.html']}, [], ['artifacts/page-job-r5.html']), [])
        self.assertEqual(missing_files({'requiredFiles':['artifacts/brief.md']}, [], ['artifacts/page-job-r5.html']), ['artifacts/brief.md'])

    def test_second_missing_handoff_does_not_start_another_repair(self):
        self.configure()
        self.adapter.plan['tasks'][1]['requiredFiles'] = ['artifacts/page.html']
        plan = self.run_plan()['payload']['collaboration']
        self.assertEqual(plan['outcome'], 'partial')
        self.assertEqual(len(self.research_sessions), 2)
        self.assertEqual(sum(a.endswith('-r5') for a, _, _ in self.adapter.calls), 1)
        self.assertEqual(plan['outputs']['5']['handoffStatus'], 'missing')

    def test_budget_expiry_prevents_repair_call(self):
        self.configure()
        clock = [0]
        def expire(role, prompt):
            if role == 8: clock[0] = 1000
        self.adapter.after_call = expire
        with patch('collaboration_plan.monotonic', side_effect=lambda:clock[0]):
            plan = self.run_plan()['payload']['collaboration']
        self.assertEqual(len(self.research_sessions), 1)
        self.assertEqual(plan['outcome'], 'partial')
        self.assertTrue(plan['budgetReached'])

    def test_text_only_assignment_remains_valid(self):
        self.adapter.plan['tasks'] = [{'role':3, 'task':'Write one welcome sentence', 'requiredFiles':[]}]
        plan = self.run_plan()['payload']['collaboration']
        self.assertNotIn('handoffRecovery', plan)


if __name__ == '__main__':
    unittest.main()
