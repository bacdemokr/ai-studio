"""Twelve-agent capacity scenarios. Real Studio/SQLite/files; simulated native/LLM I/O."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts'), str(Path(__file__).parent)]
from studio import Studio, Problem
from test_hiring_preparation import ProtectedAdapter
import runtime_settings
import tech_radar
import telegram_notifications as telegram
from radar_fixture_data import sample


class CapacityAdapter(ProtectedAdapter):
    def __init__(self):
        super().__init__()
        self.cadence = {}

    def set_radar_heartbeat(self, agent, enabled):
        self.cadence[agent] = enabled
        return agent in self.agents


class TwelveAgentTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='bac-twelve-agents-')
        self.addCleanup(folder.cleanup)
        env = patch.dict(os.environ, {'BAC_DATA_DIR': folder.name})
        env.start(); self.addCleanup(env.stop)
        self.adapter = CapacityAdapter()
        self.studio = Studio(Path(folder.name) / 'studio', self.adapter, start_worker=False)
        self.account = self.studio.session()[0]
        self.owner = self.account['id']
        self.studio.onboard(self.owner, self.profile(0))
        with ThreadPoolExecutor(max_workers=6) as pool:
            self.owners = [self.owner] + list(pool.map(
                lambda i: self.studio.add_agent(self.owner, self.profile(i))['agentId'], range(1, 12)))

    @staticmethod
    def profile(i):
        return {'name': 'Agent %02d' % i, 'skills': ['radar', 'weather'],
                'protection': 'openshell' if i % 2 == 0 else 'standard'}

    def drain(self):
        while (row := self.studio.next_job()) is not None:
            self.studio.execute(row)

    def publish(self, owner):
        root = self.studio.workspace(owner)
        now = time.time()
        poll = tech_radar.run(root, 'poll', lambda source, cache: (sample(source, now), {}), now)
        tech_radar.save(root, tech_radar.DRAFT, {'token': poll['token'], 'articleId': poll['articles'][0]['id'],
                        'answer': 'Technical summary for ' + owner})
        tech_radar.run(root, 'publish')

    def test_concurrent_hiring_limit_and_unique_names_after_slot_reuse(self):
        self.assertEqual(len(self.studio.state(self.owner)['agents']), 12)
        def hire(_):
            try: return self.studio.add_agent(self.owner, self.profile(0))
            except Problem as error: return error.status
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(list(pool.map(hire, range(8))), [409] * 8)
        victim = self.owners[-1]
        self.studio.delete_agent(victim, {'name': self.studio.profile(victim)['name']})
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(hire, range(8)))
        self.assertEqual(sum(isinstance(r, dict) for r in results), 1)
        agents = self.studio.state(self.owner)['agents']
        self.assertEqual(len({a['name'] for a in agents}), 12)
        self.assertNotIn(victim, [a['key'] for a in agents])

    def test_concurrent_requests_keep_three_slot_limit_and_every_agent_can_run(self):
        def submit(owner):
            try: return self.studio.enqueue(owner, {'prompt': 'Hello ' + owner})
            except Problem as error: return error.status
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(submit, self.owners))
        self.assertEqual(sum(isinstance(r, dict) for r in results), 3)
        self.assertEqual(results.count(429), 9)
        self.drain()
        for owner, result in zip(self.owners, results):
            if result == 429:
                self.studio.enqueue(owner, {'prompt': 'Hello ' + owner})
                self.drain()
        self.assertEqual(len(self.adapter.calls), 12)
        for owner in self.owners:
            jobs = self.studio.state(owner)['jobs']
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]['status'], 'done')
            self.assertIn(owner, jobs[0]['result']['answer'])
        self.assertEqual(len(self.adapter.prepares), 6)

    def test_policy_grants_and_revokes_stay_with_one_of_twelve_agents(self):
        self.drain()
        protected = [o for o in self.owners if self.studio.profile(o)['protection'] == 'openshell']
        for owner in protected:
            self.studio.policy_change(owner, {'permission': 'weather', 'allow': True})
        victim = protected[-1]
        self.studio.policy_change(victim, {'permission': 'weather', 'allow': False})
        for owner in protected:
            requested = self.studio.policy_report(owner)['requested']
            self.assertEqual('host:api.open-meteo.com' in requested, owner != victim)
        for owner in set(self.owners) - set(protected):
            self.assertEqual(self.studio.policy_report(owner)['mode'], 'standard')

    def test_location_updates_all_sixty_workspaces_without_losing_notes(self):
        for owner in self.owners:
            (self.studio.workspace(owner) / 'MEMORY.md').write_text('private ' + owner)
        self.studio.enqueue(self.owner, {'prompt': 'Hello'})
        runtime_settings.save(self.studio, {'section': 'location', 'location': {'city': 'Seoul'}})
        for owner in self.owners:
            for role in (None, 0, 1, 2, 3):
                self.assertIn('Seoul', (self.studio.workspace(owner, role) / 'USER.md').read_text())
            self.assertEqual((self.studio.workspace(owner) / 'MEMORY.md').read_text(), 'private ' + owner)
        self.assertEqual(self.studio.state(self.owner)['jobs'][0]['status'], 'queued')

    def test_restart_interrupts_running_work_without_replaying_it_and_keeps_queue(self):
        for owner in self.owners[:3]:
            self.studio.enqueue(owner, {'prompt': 'Hello'})
        running = self.studio.next_job()
        self.studio = Studio(self.studio.directory, self.adapter, start_worker=False, recover=True)
        self.drain()
        with self.studio.db() as db:
            self.assertEqual(db.execute('SELECT status FROM jobs WHERE id=?', (running['id'],)).fetchone()[0], 'error')
        self.assertEqual(len(self.adapter.calls), 2)
        self.assertEqual(len(self.studio.state(self.owner)['agents']), 12)

    def test_twelve_deletions_clear_workspaces_and_allow_a_fresh_agent(self):
        self.drain()
        for owner in self.owners:
            self.publish(owner)
        with patch.object(runtime_settings, 'model_available', return_value=True), patch.object(telegram, 'send', return_value='not-connected'):
            self.studio.heartbeat.tick()
        for owner in self.owners:
            result = self.studio.delete_agent(owner, {'name': self.studio.profile(owner)['name']})
            for role in (None, 0, 1, 2, 3):
                self.assertFalse(self.studio.workspace(owner, role).exists())
        self.assertEqual(self.adapter.agents, {})
        with self.studio.db() as db:
            for table in ('jobs', 'agent_policies', 'heartbeat_receipts', 'heartbeat_controls'):
                self.assertEqual(db.execute('SELECT count(*) FROM ' + table).fetchone()[0], 0)
        fresh = result['agentId']
        self.assertNotIn(fresh, self.owners)
        self.studio.onboard(fresh, self.profile(0))
        self.assertEqual(len(self.studio.state(fresh)['agents']), 1)

    def test_heartbeat_isolation_pause_busy_and_restart_do_not_duplicate(self):
        self.drain()
        for owner in self.owners:
            self.publish(owner)
        paused, busy = self.owners[:2]
        self.studio.heartbeat.control(paused, {'paused': True})
        self.studio.executing_owners.add(busy)
        with patch.object(runtime_settings, 'model_available', return_value=True), patch.object(telegram, 'send', return_value='sent') as send:
            self.studio.heartbeat.tick()
            self.assertEqual(send.call_count, 11)
            self.assertFalse(self.adapter.cadence['bac-' + paused])
            self.assertFalse(self.adapter.cadence['bac-' + busy])
            self.studio.heartbeat.control(paused, {'paused': False})
            self.studio.executing_owners.clear()
            self.studio.heartbeat.tick()
            self.assertEqual(send.call_count, 12)
            self.studio = Studio(self.studio.directory, self.adapter, start_worker=False, recover=True)
            self.studio.heartbeat.tick()
            self.assertEqual(send.call_count, 12)
        for owner in self.owners:
            jobs = self.studio.state(owner)['jobs']
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]['result']['answer'], 'Technical summary for ' + owner)

    def test_slow_telegram_does_not_hold_pause_or_other_agents_chat_summaries(self):
        self.drain()
        for owner in self.owners:
            self.publish(owner)
        entered, release = threading.Event(), threading.Event()
        def slow_send(*args):
            entered.set()
            if not release.wait(5): raise RuntimeError('fixture timeout')
            return 'sent'
        with patch.object(runtime_settings, 'model_available', return_value=True), patch.object(telegram, 'send', side_effect=slow_send):
            worker = threading.Thread(target=self.studio.heartbeat.tick)
            worker.start()
            pause_done = threading.Event()
            pauser = threading.Thread(target=lambda: (self.studio.heartbeat.control(self.owners[-1], {'paused': True}), pause_done.set()))
            try:
                self.assertTrue(entered.wait(5))
                pauser.start()
                self.assertTrue(pause_done.wait(1), 'Slow Telegram must not lock Pause for another agent')
                for owner in self.owners:
                    self.assertEqual(len(self.studio.state(owner)['jobs']), 1, 'Import every chat summary before external delivery')
            finally:
                release.set(); worker.join(5)
                if pauser.ident is not None: pauser.join(5)
            self.assertFalse(worker.is_alive())

    def test_telegram_failure_does_not_disable_radar_or_duplicate_delivery(self):
        self.drain()
        for owner in self.owners:
            self.publish(owner)
        outcomes = [RuntimeError('fixture timeout')] + ['sent'] * 11
        with patch.object(runtime_settings, 'model_available', return_value=True), patch.object(telegram, 'send', side_effect=outcomes) as send:
            self.studio.heartbeat.tick()
            self.studio.heartbeat.tick()
            self.assertEqual(send.call_count, 12)
        results = [self.studio.state(owner)['jobs'][0]['result']['telegram'] for owner in self.owners]
        self.assertEqual(results.count('failed'), 1)
        self.assertEqual(results.count('sent'), 11)
        self.assertTrue(all(self.adapter.cadence['bac-' + owner] for owner in self.owners))

    def test_deleted_or_reset_agent_is_skipped_while_delivery_is_waiting(self):
        self.drain()
        for owner in self.owners:
            self.publish(owner)
        # DB insertion order is deliberately independent of concurrent hiring order.
        with self.studio.db() as db:
            ordered = [row[0] for row in db.execute('SELECT id FROM agents')]
        delivered = []
        retired = []
        def send(participant, message, created):
            delivered.append(message)
            if len(delivered) == 1:
                # Choose two summaries that have not begun delivery yet.
                retired.extend(owner for owner in ordered if owner not in message)
                del retired[2:]
                victim, reset = retired
                self.studio.delete_agent(victim, {'name': self.studio.profile(victim)['name']})
                self.studio.reset_board(reset)
            return 'sent'
        with patch.object(runtime_settings, 'model_available', return_value=True), patch.object(telegram, 'send', side_effect=send):
            self.studio.heartbeat.tick()
        self.assertEqual(len(delivered), 10)
        self.assertTrue(all(owner not in message for owner in retired for message in delivered))

    def test_running_deletion_fences_one_agent_while_other_eleven_survive(self):
        self.drain()
        victim = self.owners[-1]
        self.studio.enqueue(victim, {'prompt': 'Hello'})
        row = self.studio.next_job()
        entered, release = threading.Event(), threading.Event()
        original = self.adapter.respond
        def respond(*args):
            entered.set()
            if not release.wait(5): raise RuntimeError('fixture timeout')
            return original(*args)
        with patch.object(self.adapter, 'respond', side_effect=respond):
            worker = threading.Thread(target=self.studio.execute, args=(row,))
            worker.start()
            try:
                self.assertTrue(entered.wait(5))
                self.assertEqual(self.studio.delete_agent(victim, {'name': self.studio.profile(victim)['name']})['deleting'], victim)
                with self.assertRaises(Problem):
                    self.studio.enqueue(victim, {'prompt': 'Must not run'})
                self.studio.enqueue(self.owner, {'prompt': 'Other agent still accepts work'})
            finally:
                release.set(); worker.join(5)
        self.assertFalse(worker.is_alive())
        self.studio.finish_pending_deletions()
        self.drain()
        self.assertIsNone(self.studio.profile(victim))
        self.assertEqual(len(self.studio.state(self.owner)['agents']), 11)
        self.assertEqual(self.studio.state(self.owner)['jobs'][0]['status'], 'done')


if __name__ == '__main__':
    unittest.main()
