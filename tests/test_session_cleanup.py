"""Abandoned browsers must not leave native teams registered indefinitely."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts'), str(Path(__file__).parent)]
from studio import Studio
from studio_sessions import SESSION_IDLE_SECONDS
from test_studio import Adapter


class SessionCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.adapter = Adapter()
        self.studio = Studio(self.temp.name, self.adapter, start_worker=False)
        self.account, _ = self.studio.session()
        self.owner = self.account['id']
        self.studio.onboard(self.owner, {'name':'Fixture', 'persona':'maker', 'skills':['memory']})
        self.teams = [self.studio.crew_owner(self.owner, scenario) for scenario in ('plan', 'event-brief')]
        self.other, _ = self.studio.session()
        self.other_team = self.studio.crew_owner(self.other['id'], 'event-brief')
        self.adapter.register('bac-'+self.owner, self.studio.workspace(self.owner), self.studio.profile(self.owner))
        for team in self.teams + [self.other_team]:
            self.adapter.register(self.studio.crew_native_id(team, 0), self.studio.workspace(team, 0), {})

    def expire(self):
        with self.studio.db() as db:
            db.execute('UPDATE participants SET last_seen=? WHERE id=?', (time.time()-SESSION_IDLE_SECONDS-1, self.owner))

    def assert_retained(self):
        with self.studio.db() as db:
            self.assertEqual(db.execute('SELECT retiring FROM participants WHERE id=?', (self.owner,)).fetchone()['retiring'], 0)

    def test_expiry_removes_personal_and_both_teams_but_keeps_other_browser(self):
        self.expire()
        self.studio.clean_idle_sessions()
        with self.studio.db() as db:
            self.assertIsNone(db.execute('SELECT id FROM participants WHERE id=?', (self.owner,)).fetchone())
            for table, column in [('agents','participant'), ('crew_contexts','participant'), ('session_cleanup','participant'), ('session_cleanup_targets','participant')]:
                self.assertEqual(db.execute('SELECT count(*) FROM '+table+' WHERE '+column+'=?', (self.owner,)).fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT count(*) FROM crew_resources WHERE owner=?', (self.teams[0],)).fetchone()[0], 0)
        self.assertEqual(set(self.adapter.agents), {self.studio.crew_native_id(self.other_team, 0)})
        self.assertTrue(self.studio.workspace(self.other_team, 0).exists())
        for owner in [self.owner, *self.teams]:
            self.assertFalse(self.studio.workspace(owner).exists())
        renewed, created = self.studio.session(self.account['token'])
        self.assertTrue(created)
        self.assertNotEqual(renewed['id'], self.owner)

    def test_refresh_renewal_prevents_expiry(self):
        self.expire()
        self.assertTrue(self.studio.touch_session(self.owner))
        self.studio.retire_idle_sessions()
        self.assert_retained()
        self.expire()
        self.assertFalse(self.studio.session(self.account['token'])[1])
        self.studio.retire_idle_sessions()
        self.assert_retained()

    def test_running_work_and_final_writes_are_protected(self):
        self.studio.enqueue(self.owner, {'prompt':'Fixture work'})
        with self.studio.db() as db:
            db.execute("UPDATE jobs SET status='running' WHERE owner=?", (self.owner,))
        self.expire()
        self.studio.retire_idle_sessions()
        self.assert_retained()
        with self.studio.db() as db:
            db.execute("UPDATE jobs SET status='done' WHERE owner=?", (self.owner,))
        self.studio.executing_owners.add(self.owner)
        self.studio.retire_idle_sessions()
        self.assert_retained()
        self.studio.executing_owners.clear()
        self.studio.clean_idle_sessions()
        self.assertIsNone(self.studio.profile(self.owner))

    def test_policy_updates_are_protected(self):
        self.expire()
        with self.studio.db() as db:
            db.execute('INSERT OR REPLACE INTO agent_policies(owner,updating) VALUES (?,1)', (self.teams[0],))
        self.studio.retire_idle_sessions()
        self.assert_retained()

    def test_pending_work_is_cancelled_and_old_session_cannot_be_revived(self):
        self.expire()
        self.studio.retire_idle_sessions()
        self.assertFalse(self.studio.touch_session(self.owner))
        self.assertIsNone(self.studio.next_job())
        self.assertTrue(self.studio.session(self.account['token'])[1])
        with self.studio.db() as db:
            self.assertEqual(db.execute('SELECT deleting FROM agents WHERE id=?', (self.owner,)).fetchone()[0], 3)

    def test_partial_failure_resumes_after_restart_without_resurrecting_files(self):
        self.expire()
        original = self.adapter.remove
        calls = []
        def fail_selected(agent, workspace):
            calls.append(agent)
            if len(calls) == 3: raise RuntimeError('fixture storage unavailable')
            original(agent, workspace)
        with patch.object(self.adapter, 'remove', side_effect=fail_selected), self.assertLogs(level='ERROR'):
            self.studio.clean_idle_sessions()
        with self.studio.db() as db:
            done = db.execute('SELECT workspace_name FROM session_cleanup_targets WHERE participant=? AND done=1', (self.owner,)).fetchall()
            self.assertTrue(done)
        restarted = Studio(self.temp.name, self.adapter, start_worker=False, recover=True)
        for row in done:
            self.assertFalse((Path(self.temp.name)/'workspaces'/row['workspace_name']).exists())
        with restarted.db() as db:
            db.execute('UPDATE session_cleanup SET next_attempt=0')
        restarted.clean_idle_sessions()
        with restarted.db() as db:
            self.assertIsNone(db.execute('SELECT id FROM participants WHERE id=?', (self.owner,)).fetchone())

    def test_preserving_restart_gives_browser_reconnect_grace(self):
        self.expire()
        restarted = Studio(self.temp.name, self.adapter, start_worker=False, recover=True)
        restarted.retire_idle_sessions()
        self.assertFalse(restarted.session(self.account['token'])[1])

    def test_cleanup_uses_explicit_legacy_resource_ids(self):
        original = self.studio.crew_native_id(self.teams[0], 0)
        legacy = 'bac-' + 'a'*24 + '-r0'
        with self.studio.db() as db:
            db.execute('UPDATE crew_resources SET native_id=? WHERE owner=? AND role=0', (legacy,self.teams[0]))
        self.adapter.agents[legacy] = self.adapter.agents.pop(original)
        self.expire()
        self.studio.clean_idle_sessions()
        self.assertNotIn(legacy,self.adapter.agents)

    def test_unused_definitions_are_inspected_per_native_owner_family(self):
        def inspect(targets):
            self.assertEqual(len({native[:28] for native, _ in targets}), 1)
            return {native for native, _ in targets if native not in self.adapter.agents}
        self.expire()
        with patch.object(self.adapter,'unregistered_deletion_targets',side_effect=inspect,create=True), \
                patch.object(self.adapter,'remove',wraps=self.adapter.remove) as remove:
            self.studio.clean_idle_sessions()
        self.assertEqual(remove.call_count,3)

    def test_redirected_workspace_is_not_removed(self):
        target = Path(self.temp.name)/'unrelated'; target.mkdir()
        keep = target/'keep.txt'; keep.write_text('keep')
        path = self.studio.workspace(self.owner)
        import shutil
        shutil.rmtree(path); path.symlink_to(target, target_is_directory=True)
        self.expire()
        with self.assertLogs(level='ERROR'):
            self.studio.clean_idle_sessions()
        self.assertEqual(keep.read_text(),'keep')
        self.assertFalse(self.studio.touch_session(self.owner))


if __name__ == '__main__': unittest.main()
