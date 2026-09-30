import json
import unittest

import agent_runtime
import test_collaboration_plan as fixture
from collaboration_plan import read_plan
from plan_inputs import requested_inputs
from studio import CREW_CATALOG, Problem


class PlanInputs(unittest.TestCase):
    setUp = fixture.CollaborationTests.setUp
    start = fixture.CollaborationTests.start
    job = fixture.CollaborationTests.job

    def test_every_phase_knows_team_capabilities_and_exec_scope(self):
        self.start()
        self.app.execute(self.app.next_job())
        self.assertEqual(len(self.adapter.calls), 7)
        for _, _, prompt in self.adapter.calls:
            self.assertIn('Team capabilities (valid at every stage', prompt)
            self.assertIn('web_fetch can attempt public URLs', prompt)
            self.assertIn('No command execution', prompt)
            self.assertIn('Writing source files is not executing or testing them', prompt)

    def prepare_inputs(self):
        self.app.upload(self.owner, {'name': 'sales (1).csv', 'content': 'month,sales\nJan,3\nFeb,5'})
        self.app.upload(self.owner, {'name': 'private.txt', 'content': 'PRIVATE_NOT_REQUESTED'})
        self.adapter.plan['tasks'] = [
            {'role': 6, 'task': 'Analyze sales', 'inputs': ['document-0']},
            {'role': 4, 'task': 'Independently check sales', 'inputs': ['document-0']}]

    def test_original_reaches_analyst_reviewer_and_captain_then_is_removed(self):
        self.prepare_inputs()
        original = self.adapter.respond
        checked = []
        def respond(agent, session, prompt, **kwargs):
            if session.startswith('bac-plan-') and not session.endswith('-planning'):
                paths = list((self.adapter.agents[agent] / 'inbox').glob('plan-input-*'))
                self.assertEqual(len(paths), 1)
                self.assertEqual(paths[0].read_text(), 'month,sales\nJan,3\nFeb,5')
                self.assertIn('sales (1).csv', prompt)
                self.assertNotIn('private.txt', prompt)
                checked.append(session)
            return original(agent, session, prompt, **kwargs)
        self.adapter.respond = respond
        self.start('/plan Analyze sales (1).csv and independently verify it.')
        self.app.execute(self.app.next_job())
        self.assertEqual(len(checked), 4)
        team = self.app.crew_owner(self.owner)
        for role in (0, 6, 4):
            self.assertEqual(list(self.app.workspace(team, role).glob('inbox/plan-input-*')), [])
        self.assertTrue((self.app.workspace(self.owner) / 'inbox/sales (1).csv').exists())

    def test_other_agents_files_are_never_candidates(self):
        self.prepare_inputs()
        other = self.app.session()[0]['id']
        self.app.onboard(other, {'name': 'Other', 'skills': ['web']})
        self.app.upload(other, {'name': 'outsider.txt', 'content': 'PRIVATE_OTHER_AGENT'})
        values = requested_inputs(self.app, {'owner': self.owner, 'role': None}, 'Use uploaded documents')
        self.assertEqual({v['name'] for v in values}, {'sales (1).csv', 'private.txt'})
        self.assertFalse(any(b'PRIVATE_OTHER_AGENT' in v['data'] for v in values))

    def test_filename_followed_by_sentence_punctuation(self):
        self.prepare_inputs()
        origin = {'owner': self.owner, 'role': None}
        for task in ('Read sales (1).csv.', 'Read "sales (1).csv".', 'Read inbox/sales (1).csv, please.'):
            with self.subTest(task=task):
                self.assertEqual([v['name'] for v in requested_inputs(self.app, origin, task)], ['sales (1).csv'])
        for task in ('Read sales (1).csv.txt', 'Read secret-sales (1).csv'):
            self.assertEqual(requested_inputs(self.app, origin, task), [])

    def test_binary_document_uses_its_extracted_companion(self):
        inbox = self.app.workspace(self.owner) / 'inbox'
        (inbox / 'sheet.XLSX').write_bytes(b'BINARY')
        (inbox / 'sheet.XLSX.txt').write_text('Sheet1\nA1:3')
        values = requested_inputs(self.app, {'owner': self.owner, 'role': None}, 'Read uploaded sheet.xlsx.')
        self.assertEqual(len(values), 1)
        self.assertTrue(values[0]['extractedText'])
        self.assertEqual(values[0]['data'], b'Sheet1\nA1:3')

    def test_unavailable_and_malformed_selections_fail_before_specialist(self):
        for selection in ('bad', [True], ['x', 'x']):
            with self.subTest(selection=selection), self.assertRaises(RuntimeError):
                read_plan(json.dumps({'summary': 'Test', 'tasks': [{'role': 6, 'task': 'Read', 'inputs': selection}]}))
        self.adapter.plan['tasks'] = [{'role': 6, 'task': 'Read', 'inputs': ['../../private.txt']}]
        self.start()
        with self.assertRaisesRegex(RuntimeError, 'unavailable document'):
            self.app.execute(self.app.next_job())
        self.assertEqual(len(self.adapter.calls), 1)

    def test_input_copies_removed_on_failure(self):
        self.prepare_inputs()
        self.adapter.fail_role = 6
        self.start('/plan Analyze sales (1).csv')
        with self.assertRaises(RuntimeError):
            self.app.execute(self.app.next_job())
        self.assertEqual(list(self.app.workspace(self.app.crew_owner(self.owner), 6).glob('inbox/plan-input-*')), [])

    def test_symlink_cannot_be_used_as_document(self):
        inbox = self.app.workspace(self.owner) / 'inbox'
        (inbox / 'linked.txt').symlink_to(inbox / 'elsewhere.txt')
        with self.assertRaises(Problem):
            requested_inputs(self.app, {'owner': self.owner, 'role': None}, 'Read linked.txt')

    def test_only_visual_assignee_gets_attached_images(self):
        raw = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9V8AAAAASUVORK5CYII='
        self.adapter.plan['tasks'] = [{'role': 7, 'task': 'Inspect design', 'useImages': True}, {'role': 4, 'task': 'Review copy'}]
        original = self.adapter.respond
        seen = {}
        def respond(agent, session, prompt, **kwargs):
            if session.startswith('bac-plan-'):
                seen[int(agent.rsplit('-r', 1)[1])] = bool(kwargs.get('images'))
            return original(agent, session, prompt, **kwargs)
        self.adapter.respond = respond
        self.app.enqueue(self.owner, {'kind': 'chat', 'prompt': '/plan Improve this screenshot and draft copy',
                         'images': [{'dataUrl': 'data:image/png;base64,' + raw}]})
        self.app.execute(self.app.next_job())
        self.assertEqual(seen, {0: True, 7: True, 4: False})

    def test_all_crew_definitions_keep_general_capabilities_explicit(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            for role, member in enumerate(CREW_CATALOG):
                workspace = Path(directory) / str(role)
                agent_runtime.write_workspace(workspace, member, member['role'])
                instructions = (workspace / 'AGENTS.md').read_text()
                self.assertIn('Actual capabilities and limits', instructions)
                self.assertIn('Writing source files is not executing or testing them', instructions)
                self.assertIn('Do not load them for unrelated work', instructions)
                self.assertIn(member['collaboration']['title'], (workspace / 'IDENTITY.md').read_text())
                if member['collaboration'].get('scope'):
                    soul = (workspace / 'SOUL.md').read_text()
                    self.assertIn(member['collaboration']['scope'], soul)
                    self.assertIn('Captain-delegated /plan work', soul)
                for path in (workspace / 'skills').glob('bac-*/SKILL.md'):
                    if path.parent.name in ('bac-event-page', 'bac-nvidia-webpage', 'bac-nvidia-social', 'bac-nvidia-research', 'bac-event-scheduling', 'bac-event-tools'):
                        self.assertIn('SCOPE: Use this skill only', path.read_text())


if __name__ == '__main__':
    unittest.main()
