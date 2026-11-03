"""Only actual, current workspace files can appear in the chat policy history."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts'), str(Path(__file__).parent)]
from studio import Studio
from test_studio import Adapter


class PolicyChatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = Studio(self.temp.name, Adapter(), start_worker=False)
        self.owner = self.app.session()[0]['id']
        self.app.onboard(self.owner, {'name': 'Shield', 'skills': [], 'protection': 'openshell'})

    def complete(self, files, answer='Saved all files.'):
        job = self.app.enqueue(self.owner, {'kind': 'chat', 'prompt': 'Save a note.'})
        with self.app.db() as db:
            db.execute("UPDATE jobs SET status='done',result=? WHERE id=?", (json.dumps({'answer':answer, 'files':files}), job['id']))
        return job

    def save(self, path):
        file = self.app.workspace(self.owner) / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text('A real file, not a model claim.')
        return file

    def test_claims_missing_files_and_app_transcripts_are_not_evidence(self):
        self.complete(['artifacts/note.txt', 'artifacts/reply-auto.md', 'artifacts/missing.txt'])
        self.save('artifacts/note.txt')
        self.save('artifacts/reply-auto.md')
        self.assertEqual([r['path'] for r in self.app.policy_report(self.owner)['recentFiles']], ['artifacts/note.txt'])
        (self.app.workspace(self.owner) / 'artifacts/note.txt').unlink()
        self.assertEqual(self.app.policy_report(self.owner)['recentFiles'], [])

    def test_unrelated_old_files_and_other_agents_do_not_leak(self):
        self.save('artifacts/old.txt')
        time.sleep(.01)
        self.complete(['artifacts/old.txt'])
        self.assertEqual(self.app.policy_report(self.owner)['recentFiles'], [])
        other = self.app.add_agent(self.owner, {'name':'Other', 'skills':[], 'protection':'openshell'})['agentId']
        self.complete(['artifacts/nested/new.txt'])
        self.save('artifacts/nested/new.txt')
        self.assertEqual(len(self.app.policy_report(self.owner)['recentFiles']), 1)
        self.assertEqual(self.app.policy_report(other)['recentFiles'], [])

    def test_report_shares_live_evidence_only_during_the_matching_response(self):
        tracker = self.app.protection_activity
        native = self.app.profile(self.owner)['id']
        report = self.app.adapter.policy_status(native, 'openshell', [])
        report['logs'] = [{'time': time.time(), 'host': 'example.com', 'action': 'deny',
                           'reason': 'policy-denied', 'fingerprint': 'native-log'}]
        with patch.object(self.app.adapter, 'policy_status', return_value=report):
            self.app.policy_report(self.owner)
            self.assertEqual(tracker.snapshot({self.owner}, self.owner), [])
            with patch('protection_activity.threading.Thread'), tracker.watch(self.owner, None, native, lambda _: []):
                self.app.policy_report(self.owner)
                events = tracker.snapshot({self.owner}, self.owner)
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]['host'], 'example.com')
                tracker.forget(self.owner)

    def test_requested_url_alone_never_creates_a_shield_event(self):
        self.app.enqueue(self.owner, {'kind': 'chat', 'prompt': 'search google.com'})
        tracker = self.app.protection_activity
        native = self.app.profile(self.owner)['id']
        with patch('protection_activity.threading.Thread'), tracker.watch(self.owner, None, native, lambda _: []):
            report = self.app.policy_report(self.owner)
            self.assertTrue(any(e['host'] == 'google.com' for e in report['pendingAccess']))
            self.assertEqual(tracker.snapshot({self.owner}, self.owner), [])
            tracker.forget(self.owner)

if __name__ == '__main__': unittest.main()
