import json
from pathlib import Path
import unittest
import test_collaboration_plan as fixture
from test_studio import Problem
from plan_artifacts import snapshot_files, collect_files, MAX_BYTES


class DynamicPlanTests(unittest.TestCase):
    setUp = fixture.CollaborationTests.setUp
    start = fixture.CollaborationTests.start
    job = fixture.CollaborationTests.job

    def test_programmer_reviewer_receive_actual_files_and_only_selected_agents_run(self):
        self.adapter.plan = {'summary': 'Build then inspect.', 'tasks': [
            {'role': 5, 'task': 'Write a small calculator.'}, {'role': 4, 'task': 'Check the calculator against the requirements.'}]}
        original = self.adapter.respond
        received = []
        def respond(agent, session, prompt, **kwargs):
            workspace = self.adapter.agents[agent]
            if session.endswith('-working') and agent.endswith('-r5'):
                (workspace / 'artifacts/calc.py').write_text('def add(a, b): return a + b\n')
                (workspace / 'artifacts/requirements.json').write_text('{"add": true}')
            if session.endswith('-working') and agent.endswith('-r4'):
                for path in (workspace / 'inbox').glob('plan-*'):
                    received.append((path.suffix, path.read_text()))
                    self.assertIn(str(path.relative_to(workspace)), prompt)
            return original(agent, session, prompt, **kwargs)
        self.adapter.respond = respond
        result = self.start('/plan Build a calculator and inspect edge cases.')
        self.app.execute(self.app.next_job())
        job = self.job(result)
        self.assertEqual(job['status'], 'done')
        self.assertEqual([int(a.rsplit('-r', 1)[1]) for a, _, _ in self.adapter.calls], [0, 5, 0, 4, 0])
        self.assertEqual({ext for ext, _ in received}, {'.py', '.json'})
        self.assertTrue(any('return a + b' in text for _, text in received))
        team = self.app.crew_owner(self.owner)
        self.assertEqual(list((self.app.workspace(team, 4) / 'inbox').glob('plan-*')), [])
        paths = job['payload']['collaboration']['outputs']['5']['files']
        self.assertEqual(len(paths), 2)
        outsider = self.app.session()[0]['id']
        for path in paths:
            self.assertIn(path, job['result']['files'])
            self.app.available_file(self.owner, path)
            with self.assertRaises(Problem): self.app.available_file(outsider, path)
        self.app.reset_crew_chats(self.owner, reset_event=True)
        self.assertEqual(self.app.state(self.owner)['crewChats'], [])
        self.assertEqual(self.app.conversation_context(team, 5, float('inf'), ''), '')

    def test_default_definitions_do_not_force_event_deliverables(self):
        team = self.app.crew_owner(self.owner)
        workspace = self.app.workspace(team, 3)
        automatic = '\n'.join((workspace / name).read_text() for name in ('AGENTS.md', 'SOUL.md'))
        self.assertNotIn('LINKEDIN-FIRST', automatic)
        self.assertNotIn('Finish with at most 20 words', automatic)
        self.assertIn('requested format', automatic)
        event = (workspace / 'EVENT_WORKFLOW.md').read_text()
        self.assertIn('LINKEDIN-FIRST', event)
        self.assertIn('Finish with at most 20 words', event)

    def test_new_reserves_run_on_existing_team_without_changing_event_roster(self):
        from studio import Studio
        team = self.app.crew_owner(self.owner)
        original = self.app.crew_native_id(team, 1)
        # Simulate the previous six-role catalog, then upgrade twice.
        with self.app.db() as db:
            db.execute('DELETE FROM crew_resources WHERE owner=? AND role>=6', (team,))
        for _ in range(2):
            self.app = Studio(self.temp.name, self.adapter, start_worker=False)
            self.assertEqual(self.app.crew_owner(self.owner), team)
            self.assertEqual(self.app.crew_native_id(team, 1), original)
            with self.app.db() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM crew_resources WHERE owner=?', (team,)).fetchone()[0], 9)
        self.assertEqual(self.adapter.agents, {})
        self.adapter.plan['tasks'] = [{'role': 6, 'task': 'Interpret the table'}, {'role': 7, 'task': 'Design the display'}, {'role': 5, 'task': 'Implement the display'}]
        result = self.start('/plan Interpret this table and design a dashboard.')
        self.app.execute(self.app.next_job())
        self.assertEqual(self.job(result)['status'], 'done')
        self.assertEqual([int(a.rsplit('-r', 1)[1]) for a, _, _ in self.adapter.calls], [0, 6, 0, 7, 0, 5, 0])
        for role in (6, 7, 8):
            with self.assertRaises(Problem):
                self.app.enqueue(team, {'kind': 'crew', 'preset': True, 'brief': {'schema': 2}, 'enabledRoles': [0, role]})

    def test_only_changed_safe_text_is_shared_not_stale_or_symlink_content(self):
        team = self.app.crew_owner(self.owner)
        workspace = self.app.workspace(team, 5)
        (workspace / 'artifacts/old.txt').write_text('STALE')
        before = snapshot_files(workspace)
        external = Path(self.temp.name) / 'secret.txt'; external.write_text('EXTERNAL')
        (workspace / 'artifacts/link.txt').symlink_to(external)
        (workspace / 'artifacts/binary.txt').write_bytes(b'\xff\xfe')
        (workspace / 'artifacts/too-big.txt').write_bytes(b'x' * (MAX_BYTES + 1))
        (workspace / 'artifacts/new.csv').write_text('a,b\n1,2\n')
        paths = collect_files(self.app, team, 'qa', 5, before)
        self.assertEqual(len(paths), 1)
        self.assertEqual((self.app.workspace(team) / paths[0]).read_text(), 'a,b\n1,2\n')

    def test_stop_after_programmer_preserves_output_and_does_not_run_reviewer(self):
        self.adapter.plan['tasks'] = [{'role': 5, 'task': 'Implement'}, {'role': 4, 'task': 'Review'}]
        result = self.start()
        team = self.app.crew_owner(self.owner)
        self.adapter.after_call = lambda role, prompt: self.app.decision(team, result['id'], 'cancel') if role == 5 else None
        self.app.execute(self.app.next_job())
        self.assertEqual(self.job(result)['status'], 'cancelled')
        self.assertEqual(len(self.adapter.calls), 2)
