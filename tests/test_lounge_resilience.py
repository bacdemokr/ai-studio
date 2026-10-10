"""User journeys across connection loss, startup delays and autonomous work."""
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import model_connections as connections
import runtime_settings as settings
import session_secrets
from studio import Studio
from test_tech_radar import RadarAdapter


class LoungeResilienceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, {'BAC_DATA_DIR': self.temp.name}); env.start(); self.addCleanup(env.stop)
        self.adapter = RadarAdapter()
        self.app = Studio(Path(self.temp.name)/'studio', self.adapter, start_worker=False)
        self.owner = self.app.session()[0]['id']
        self.app.heartbeat.presence(self.owner, 'exploration')
        self.lease = 'exploration-'+self.temp.name
        self.addCleanup(session_secrets.release, self.lease)
        with patch.object(settings, 'request', return_value={'data':[{'id':'fixture-model'}]}):
            for source, provider in [('local','local'),('api','nvidia')]:
                connections.configure(self.app, {'source':source,'provider':provider,'model':'fixture-model',
                    'apiKey':'fixture-key' if source=='api' else '', 'contextWindow':32768,
                    '_credentialSession':self.lease})
        self.profile = self.app.onboard(self.owner, {'name':'Mixed','skills':['radar','weather']})
        self.now = time.time()+30

    def tick(self, elapsed=0):
        with patch('studio_heartbeat.time.time', return_value=self.now+elapsed):
            self.app.heartbeat.tick()

    def next_job(self, elapsed=0):
        with patch("studio.time.time", return_value=self.now+elapsed):
            return self.app.next_job()

    def test_autonomous_agent_follows_local_api_fallback_and_recovery(self):
        self.app.execute(self.next_job()); self.tick()
        self.assertTrue(self.adapter.cadence[self.profile['id']])
        self.assertEqual(self.adapter.profiles[self.profile['id']]['_connectionConfig']['baseUrl'],
                         settings.PROVIDERS['local']['baseUrl'])
        original = connections.status
        def api_only(source, refresh=False):
            state = original(source, refresh)
            return {**state,'ready':False} if source=='local' else state
        with patch.object(connections, 'status', side_effect=api_only):
            self.tick()
            self.assertFalse(self.adapter.cadence[self.profile['id']], 'Stale local timer must stop before reconfiguration')
            job = self.next_job(); self.assertIsNotNone(job)
            self.app.execute(job); self.tick(30)
            self.assertTrue(self.adapter.cadence[self.profile['id']])
            self.assertIn('/provider/nvidia/', self.adapter.profiles[self.profile['id']]['_connectionConfig']['baseUrl'])
        self.tick(31)
        job = self.next_job(31); self.assertIsNotNone(job)
        self.app.execute(job); self.tick(60)
        self.assertEqual(self.adapter.profiles[self.profile['id']]['_connectionConfig']['baseUrl'],
                         settings.PROVIDERS['local']['baseUrl'])

    def test_api_ready_does_not_queue_preparation_when_gateway_is_down(self):
        # Discard initial onboarding work to model a browser returning after restart.
        with self.app.db() as db: db.execute("DELETE FROM jobs WHERE kind='prepare-agent'")
        with patch.object(self.adapter, 'status', return_value={'ready':False,'gateway':False,'model':True}):
            self.tick()
        self.assertIsNone(self.next_job())
        self.assertFalse(self.adapter.cadence.get(self.profile['id'], False))
        self.assertEqual(self.app.heartbeat.status(self.owner,self.profile)['state'], 'waiting for runtime')

    def test_repeated_preparation_failure_backs_off_then_recovers(self):
        attempts = 0
        with patch.object(self.adapter, 'register', side_effect=RuntimeError('Gateway still starting')):
            for elapsed in range(0,100,3):
                self.tick(elapsed)
                job=self.next_job(elapsed)
                if job:
                    attempts+=1
                    with self.assertRaises(RuntimeError):self.app.execute(job)
                    with patch('studio.time.time',return_value=self.now+elapsed):
                        self.app.event(job['id'],'Preparation failed','Gateway still starting',status='error')
        self.assertLessEqual(attempts,4, 'Failure must not create a new preparation every three seconds')
        self.assertGreaterEqual(attempts,2, 'A temporary failure must still recover automatically')
        self.tick(200);job=self.next_job(200);self.assertIsNotNone(job)
        self.app.execute(job);self.tick(230)
        self.assertEqual(self.app.heartbeat.status(self.owner,self.profile)['state'],'watching')

    def test_failed_preparation_cannot_enable_a_partially_registered_agent(self):
        job=self.next_job()
        with patch.object(self.app, 'check_protected_run', side_effect=RuntimeError('Policy not confirmed')):
            with self.assertRaises(RuntimeError):self.app.execute(job)
        self.app.event(job['id'],'Preparation failed','Policy not confirmed',status='error')
        self.tick()
        self.assertFalse(self.adapter.cadence[self.profile['id']])

    def test_other_agents_work_is_waiting_not_a_model_connection_failure(self):
        self.app.execute(self.next_job()); self.tick()
        other=self.app.add_agent(self.owner, {'name':'Researcher','skills':['web']})['agentId']
        job=self.app.enqueue(other, {'kind':'chat','prompt':'Research physical AI'})
        self.tick(150)
        self.assertTrue(self.adapter.cadence[self.profile['id']], 'Do not repeatedly rewrite the native timer')
        self.assertEqual(self.app.heartbeat.status(self.owner,self.profile)['state'], 'waiting for other agents')
        self.app.execute(self.next_job(150)); self.tick(151)
        self.assertEqual(self.app.heartbeat.status(self.owner,self.profile)['state'], 'watching')

    def test_slow_native_timer_update_does_not_block_browser_presence(self):
        self.app.execute(self.next_job())
        entered=threading.Event(); release=threading.Event(); returned=threading.Event()
        def slow_toggle(*args):
            entered.set(); release.wait(5); return True
        def browser_read():
            self.app.heartbeat.presence(self.owner,'another-tab'); returned.set()
        with patch.object(self.adapter,'set_radar_heartbeat',side_effect=slow_toggle):
            worker=threading.Thread(target=self.tick); worker.start()
            reader=None
            try:
                self.assertTrue(entered.wait(2))
                reader=threading.Thread(target=browser_read); reader.start()
                self.assertTrue(returned.wait(1), 'Every state request renews presence; native I/O must not stall the UI')
            finally:
                release.set(); worker.join(5)
                if reader:reader.join(5)


if __name__=='__main__':unittest.main()
