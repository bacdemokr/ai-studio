"""Real Studio/SQLite lifecycle with isolated credentials and controlled Telegram I/O."""
import json
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import test_tech_radar as fixtures
import session_secrets
import telegram_notifications as telegram
import tech_radar
from studio import Studio, Problem


class HeartbeatDeletionTests(unittest.TestCase):
    protection = 'standard'
    tick = fixtures.HeartbeatRelayTests.tick

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.adapter = fixtures.RadarAdapter()
        self.studio = Studio(self.temp.name, self.adapter, start_worker=False)
        self.owner = self.studio.session()[0]['id']
        self.studio.heartbeat.presence(self.owner, 'fixture-tab')
        self.profile = self.studio.onboard(self.owner, {'name': 'Echo', 'skills': ['radar'],
            'protection': self.protection})
        self.studio.execute(self.studio.next_job())
        self.root = self.studio.workspace(self.owner)
        now = time.time()
        poll = tech_radar.run(self.root, 'poll', lambda source, cache: (fixtures.sample(source, now), {}), now)
        tech_radar.save(self.root, tech_radar.DRAFT, {'token': poll['token'],
            'articleId': poll['articles'][0]['id'], 'answer': 'A useful new inference SDK.'})
        tech_radar.run(self.root, 'publish')

    def connect(self):
        self.lease = self.owner + ':telegram-fixture'
        self.addCleanup(session_secrets.remove, telegram.key(self.owner))
        with patch.object(telegram, 'request', return_value={'username': 'fixture_bot'}):
            telegram.configure(self.owner, {'token': '123456789:' + 'x'*30,
                'chatId': '12345', '_credentialSession': self.lease})
        box = tech_radar.read(self.root, tech_radar.OUTBOX)
        for event in box['events']:event['created'] = time.time()
        tech_radar.save(self.root, tech_radar.OUTBOX, box)

    def pending(self):
        deliveries = []
        self.studio.heartbeat.statuses[self.owner] = {'state': 'watching'}
        self.studio.heartbeat.import_events(self.owner, self.owner, self.profile, deliveries)
        self.assertEqual(len(deliveries), 1)
        return deliveries

    def delete(self):
        return self.studio.delete_agent(self.owner, {'name': self.profile['name']})

    def assert_retired(self):
        with self.studio.db() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM agents WHERE id=?', (self.owner,)).fetchone())
            for table in ('jobs', 'heartbeat_receipts', 'heartbeat_controls', 'agent_deletions'):
                self.assertEqual(db.execute('SELECT count(*) FROM '+table+' WHERE owner=?', (self.owner,)).fetchone()[0], 0)
        self.assertFalse(self.root.exists())
        self.assertNotIn(self.profile['id'], self.adapter.agents)
        self.assertFalse(self.adapter.cadence[self.profile['id']])
        self.assertNotIn(self.owner, self.studio.heartbeat.statuses)

    def test_deleted_queued_summary_never_reaches_telegram(self):
        self.connect(); queued = self.pending()
        self.delete()
        with patch.object(telegram, 'request') as transport:
            self.studio.heartbeat.deliver_events(queued); self.tick()
            transport.assert_not_called()
        self.assert_retired()

    def test_late_native_output_after_delete_request_is_not_imported(self):
        self.connect()
        result = self.studio.delete_agent(self.owner, {'name': self.profile['name']}, enqueue_only=True)
        self.assertIn('deleting', result)
        # Simulate a native run publishing its final output after the UI request.
        box = tech_radar.read(self.root, tech_radar.OUTBOX)
        box['events'][0]['created'] = time.time()
        tech_radar.save(self.root, tech_radar.OUTBOX, box)
        with patch.object(telegram, 'request') as send:
            self.tick(); send.assert_not_called()
            with self.studio.db() as db:
                self.assertEqual(db.execute("SELECT count(*) FROM jobs WHERE kind='heartbeat'").fetchone()[0], 0)
        self.studio.finish_pending_deletions(); self.assert_retired()

    def test_failed_cleanup_stays_fenced_until_retry(self):
        self.connect(); queued = self.pending()
        with patch.object(self.adapter, 'remove', side_effect=RuntimeError('Fixture cleanup failure')):
            with self.assertLogs(level='ERROR'), self.assertRaises(Problem):self.delete()
        with patch.object(telegram, 'request') as send:
            self.studio.heartbeat.deliver_events(queued); self.tick(); send.assert_not_called()
        self.delete(); self.assert_retired()

    def test_deletion_before_preparation_never_starts_heartbeat(self):
        self.connect()
        added = self.studio.add_agent(self.owner, {'name': 'Fresh radar', 'skills': ['radar'],
            'protection': self.protection})
        self.studio.delete_agent(added['agentId'], {'name': added['profile']['name']})
        self.assertIsNone(self.studio.next_job())
        self.assertNotIn(added['profile']['id'], self.adapter.agents)
        self.assertFalse(self.adapter.cadence[added['profile']['id']])
        self.delete(); self.assert_retired()

    def test_restart_after_uncertain_claim_does_not_resend(self):
        self.connect(); queued = self.pending()
        job = queued[0][2]
        with self.studio.db() as db:
            value = json.loads(db.execute('SELECT result FROM jobs WHERE id=?', (job,)).fetchone()[0])
            value['telegram'] = 'sending'
            db.execute('UPDATE jobs SET result=? WHERE id=?', (json.dumps(value), job))
        restored = Studio(self.temp.name, self.adapter, start_worker=False)
        restored.heartbeat.presence(self.owner, 'restored-tab')
        with patch.object(telegram, 'request') as send, patch('runtime_settings.model_available', return_value=True):
            restored.heartbeat.deliver_events(queued); restored.heartbeat.tick()
            send.assert_not_called()
        self.delete(); self.assert_retired()

    def test_in_flight_send_must_settle_before_deletion_completes(self):
        self.check_in_flight()

    def test_in_flight_timeout_releases_deletion_without_retry(self):
        self.check_in_flight(RuntimeError('Uncertain network timeout'))

    def check_in_flight(self, failure=None):
        self.connect(); queued = self.pending()
        box = tech_radar.read(self.root, tech_radar.OUTBOX)
        box['events'].append({**box['events'][0], 'id': 'c'*64, 'answer': 'Must not be sent after deletion.'})
        tech_radar.save(self.root, tech_radar.OUTBOX, box)
        self.studio.heartbeat.import_events(self.owner, self.owner, self.profile, queued)
        self.assertEqual(len(queued), 2)
        started, release = threading.Event(), threading.Event()
        errors = []
        def transport(*args):
            started.set()
            if not release.wait(5):raise RuntimeError('Fixture barrier timed out')
            if failure:raise failure
            return {'message_id': 1}
        def deliver():
            try:self.studio.heartbeat.deliver_events(queued)
            except Exception as error:errors.append(error)
        with patch.object(telegram, 'request', side_effect=transport) as send:
            thread = threading.Thread(target=deliver); thread.start()
            try:
                self.assertTrue(started.wait(3))
                result = self.delete()
                self.assertIn('deleting', result)
                self.assertIn(self.profile['id'], self.adapter.agents)
                # A duplicate dispatcher must not send the already claimed event.
                self.studio.heartbeat.deliver_events(queued)
                self.assertEqual(send.call_count, 1)
                # Waiting for this send does not freeze Pause or other agents.
                self.assertTrue(self.studio.heartbeat.lock.acquire(blocking=False))
                self.studio.heartbeat.lock.release()
            finally:
                release.set(); thread.join(5)
            self.assertEqual(send.call_count, 1)
        self.assertFalse(thread.is_alive()); self.assertEqual(errors, [])
        self.studio.finish_pending_deletions()
        self.assert_retired()

    def test_repeated_dispatch_of_same_event_is_at_most_once(self):
        self.connect(); queued = self.pending()
        with patch.object(telegram, 'request', return_value={'message_id': 1}) as send:
            self.studio.heartbeat.deliver_events(queued)
            self.studio.heartbeat.deliver_events(queued)
            self.tick()
            self.assertEqual(send.call_count, 1)
        self.delete(); self.assert_retired()

    def test_failed_send_not_retried_after_delete_or_restart(self):
        self.connect()
        with patch.object(telegram, 'request', side_effect=RuntimeError('Uncertain timeout')) as send:
            self.tick(); self.tick()
            self.assertEqual(send.call_count, 1)
            with self.studio.db() as db:
                result = json.loads(db.execute("SELECT result FROM jobs WHERE kind='heartbeat'").fetchone()[0])
            self.assertEqual(result['telegram'], 'failed')
            self.delete(); self.assert_retired()
            restored = Studio(self.temp.name, self.adapter, start_worker=False)
            restored.heartbeat.presence(self.owner, 'reopened')
            with patch('runtime_settings.model_available', return_value=True):restored.heartbeat.tick()
            self.assertEqual(send.call_count, 1)

    def test_disconnect_and_expiry_drop_pending_delivery(self):
        for expired in (False, True):
            with self.subTest(expired=expired):
                self.connect(); queued = self.pending()
                if expired:
                    with patch('session_secrets.time.monotonic', return_value=time.monotonic()+100):
                        self.assertFalse(telegram.public(self.owner)['connected'])
                else:telegram.configure(self.owner, {'disconnect': True, '_credentialSession': self.lease})
                with patch.object(telegram, 'request') as send:
                    self.studio.heartbeat.deliver_events(queued); send.assert_not_called()
                # Reset only this test event to exercise the other credential state.
                with self.studio.db() as db:
                    db.execute('DELETE FROM jobs WHERE owner=?', (self.owner,))
                    db.execute('DELETE FROM heartbeat_receipts WHERE owner=?', (self.owner,))
        self.delete(); self.assert_retired()

    def test_delete_preserves_other_agent_and_connection_rehire_has_no_old_delivery(self):
        self.connect(); queued = self.pending()
        other = self.studio.add_agent(self.owner, {'name': 'Other radar', 'skills': ['radar'], 'protection': 'openshell'})
        self.studio.execute(self.studio.next_job())
        self.delete(); self.assert_retired()
        self.assertTrue(telegram.public(self.owner, self.lease)['connected'])
        self.assertIsNotNone(self.studio.profile(other['agentId']))
        fresh = self.studio.add_agent(self.owner, {'name': self.profile['name'], 'skills': ['radar']})
        self.studio.execute(self.studio.next_job())
        self.assertNotEqual(fresh['agentId'], self.owner)
        root = self.studio.workspace(fresh['agentId'])
        with patch.object(telegram, 'request') as send:
            self.studio.heartbeat.deliver_events(queued); self.tick()
            send.assert_not_called()
        self.assertFalse((root/tech_radar.OUTBOX).exists())
        now = time.time()
        poll = tech_radar.run(root, 'poll', lambda source, cache: (fixtures.sample(source, now), {}), now)
        tech_radar.save(root, tech_radar.DRAFT, {'token': poll['token'],
            'articleId': poll['articles'][0]['id'], 'answer': 'Only the new agent sends this summary.'})
        tech_radar.run(root, 'publish')
        with patch.object(telegram, 'request', return_value={'message_id': 2}) as send:
            self.tick(); self.tick()
            self.assertEqual(send.call_count, 1)
            self.assertIn('Only the new agent', send.call_args.args[2]['text'])
        for agent in (other, fresh):
            self.studio.delete_agent(agent['agentId'], {'name': agent['profile']['name']})


class ProtectedHeartbeatDeletionTests(HeartbeatDeletionTests):
    # Uses the policy-aware adapter, never a real bot or existing user workspace.
    protection = 'openshell'


if __name__ == '__main__':unittest.main()
