"""Polling reuses bounded file listings without hiding native writes or resets."""
from collections import Counter
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_studio import Adapter, Studio
from studio import safe_file


class StateInventoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.app = Studio(temporary.name, Adapter(), start_worker=False)
        self.owner = self.app.session()[0]['id']
        self.app.onboard(self.owner, {'name': 'Reader', 'skills': []})
        self.team = self.app.crew_owner(self.owner)

    def test_each_listing_once_per_poll_but_native_writes_are_fresh(self):
        with patch.object(self.app, 'files', wraps=self.app.files) as listing:
            before = self.app.state(self.owner)
        counts = Counter((call.args, tuple(call.kwargs.items())) for call in listing.call_args_list)
        self.assertTrue(counts)
        self.assertEqual(max(counts.values()), 1)
        self.assertFalse(before['scenarios'][0]['hasWork'])
        path = self.app.workspace(self.team, 8) / 'artifacts/nested/brief.md'
        path.parent.mkdir(parents=True)
        path.write_text('Native tool wrote this without an HTTP mutation.')
        after = self.app.state(self.owner)
        self.assertTrue(after['scenarios'][0]['hasWork'])
        self.assertIn('8', after['fileWorkspaces'])
        path.unlink()
        cleared = self.app.state(self.owner)
        self.assertFalse(cleared['scenarios'][0]['hasWork'])
        self.assertNotIn('8', cleared['fileWorkspaces'])

    def test_bounded_listing_preserves_order_and_rejects_unsafe_paths(self):
        base = self.app.workspace(self.owner)
        (base/'inbox/000-unsafe.md').symlink_to(Path(self.app.directory)/'missing')
        (base/'inbox/001-directory').mkdir()
        expected = []
        for index in range(120):
            name = 'inbox/%03d.md' % (index+2)
            (base/name).write_text('fixture')
            expected.append(name)
        with patch('studio.safe_file', wraps=safe_file) as checked:
            rows = self.app.files(self.owner)
        self.assertEqual([row['path'] for row in rows], expected[:100])
        self.assertEqual(checked.call_count, 102)

    def test_retired_role_history_is_retained_but_not_loaded_into_open_task(self):
        job = self.app.enqueue(self.team, {'kind': 'crew-chat', 'crewRole': 0, 'prompt': 'Hello'})
        with self.app.db() as db:
            db.execute("UPDATE jobs SET payload=?,status='done' WHERE id=?",
                       (json.dumps({'crewRole': 2, 'prompt': 'Archived event'}), job['id']))
        self.assertEqual(self.app.state(self.owner)['crewChats'], [])
        with self.app.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs WHERE id=?', (job['id'],)).fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
