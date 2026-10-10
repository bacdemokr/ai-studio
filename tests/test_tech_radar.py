import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).parent)]
import agent_runtime
import tech_radar
from radar_fixture_data import sample
import session_secrets
import telegram_notifications as telegram
from studio import Studio, Problem
from test_studio import Adapter


class RadarAdapter(Adapter):
    def __init__(self):super().__init__();self.cadence={}
    def set_radar_heartbeat(self,agent,enabled):self.cadence[agent]=enabled;return agent in self.agents


class HeartbeatRelayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.adapter=RadarAdapter();self.studio=Studio(self.temp.name,self.adapter,start_worker=False)
        self.owner=self.studio.session()[0]['id']
        self.studio.heartbeat.presence(self.owner, 'fixture-tab')
        self.profile=self.studio.onboard(self.owner,{'name':'Echo','skills':['radar']})
        self.studio.execute(self.studio.next_job())
        self.root=self.studio.workspace(self.owner)
        now=time.time()
        poll=tech_radar.run(self.root,'poll',lambda source,cache:(sample(source,now),{}),now)
        tech_radar.save(self.root,tech_radar.DRAFT,{'token':poll['token'],'articleId':poll['articles'][0]['id'],'answer':'A useful new inference SDK.'})
        tech_radar.run(self.root,'publish')
    def tick(self):
        # Existing relay tests model an already-started timer, not onboarding.
        with self.studio.db() as db:
            db.execute("UPDATE jobs SET created=MIN(created,?) WHERE kind='prepare-agent'", (time.time()-tech_radar.HEARTBEAT_SECONDS,))
        with patch('runtime_settings.model_available',return_value=True):self.studio.heartbeat.tick()
    def test_new_agent_starts_after_ten_seconds_and_keeps_twenty_second_cadence(self):
        (self.root/tech_radar.OUTBOX).unlink()
        hired_at=time.time()
        with self.studio.db() as db:
            db.execute("UPDATE jobs SET created=? WHERE owner=? AND kind='prepare-agent'", (hired_at,self.owner))
        with patch('runtime_settings.model_available',return_value=True), patch.object(telegram,'send') as send:
            for elapsed in (0, 5, 9.99):
                with self.subTest(elapsed=elapsed), patch('studio_heartbeat.time.time',return_value=hired_at+elapsed):
                    self.studio.heartbeat.tick()
                    self.assertFalse(self.adapter.cadence[self.profile['id']])
                    self.assertEqual(self.studio.heartbeat.status(self.owner,self.profile)['state'],'starting soon')
                    self.assertEqual(self.studio.state(self.owner)['jobs'],[])
            with patch('studio_heartbeat.time.time',return_value=hired_at+10):
                self.studio.heartbeat.tick()
                self.assertTrue(self.adapter.cadence[self.profile['id']])
                self.assertEqual(self.studio.heartbeat.status(self.owner,self.profile)['state'],'watching')
            send.assert_not_called()
        self.assertEqual(self.studio.heartbeat.status(self.owner,self.profile)['everySeconds'],20)
    def test_delay_does_not_claim_a_model_connection_failure(self):
        (self.root/tech_radar.OUTBOX).unlink()
        self.tick()
        self.studio.heartbeat.statuses[self.owner]['watchingSince'] = time.time()-101
        self.tick()
        self.assertEqual(self.studio.heartbeat.status(self.owner,self.profile)['state'],'check delayed')
        self.assertTrue(self.adapter.cadence[self.profile['id']])

    def test_native_cadence_and_single_chat_result_even_after_restart(self):
        with patch.object(telegram,'send',return_value='sent') as send:
            self.tick();self.tick()
            self.assertEqual(send.call_count,1)
        jobs=self.studio.state(self.owner)['jobs']
        self.assertEqual(len(jobs),1);self.assertEqual(jobs[0]['kind'],'heartbeat')
        self.assertEqual(jobs[0]['result']['answer'],'A useful new inference SDK.')
        self.assertTrue(self.adapter.cadence[self.profile['id']])
        again=Studio(self.temp.name,self.adapter,start_worker=False)
        with patch.object(telegram,'send') as send:
            again.heartbeat.tick();send.assert_not_called()
    def test_pause_resume_no_duplicate(self):
        self.studio.heartbeat.control(self.owner,{'paused':True});self.tick()
        self.assertFalse(self.adapter.cadence[self.profile['id']]);self.assertEqual(self.studio.state(self.owner)['jobs'],[])
        resumed=self.studio.heartbeat.control(self.owner,{'paused':False})
        self.assertEqual(resumed['state'],'resuming');self.assertFalse(resumed['paused']);self.tick()
        self.assertTrue(self.adapter.cadence[self.profile['id']]);self.assertEqual(len(self.studio.state(self.owner)['jobs']),1)
    def test_transport_timeout_keeps_chat_without_automatic_retry(self):
        with patch.object(telegram,'send',side_effect=RuntimeError('timeout')) as send:
            self.tick();self.tick();self.assertEqual(send.call_count,1)
        self.assertEqual(self.studio.state(self.owner)['jobs'][0]['result']['telegram'],'failed')
    def test_invalid_model_output_not_published(self):
        tech_radar.save(self.root,tech_radar.OUTBOX,{'events':[{'id':'a'*64,'answer':'unsafe','url':'https://attacker.example/blog/a/','created':time.time()}]})
        self.tick();self.assertEqual(self.studio.state(self.owner)['jobs'],[])
    def test_other_participant_never_receives_summary(self):
        second=self.studio.session()[0]['id'];self.studio.onboard(second,{'name':'Scout','skills':['writer']})
        with patch.object(telegram,'send',return_value='sent') as send:
            self.tick();self.assertEqual(send.call_args.args[0],self.owner)
        self.assertEqual(self.studio.state(second)['jobs'],[])
    def test_active_personal_work_suspends_heartbeat(self):
        self.studio.executing_owners.add(self.owner)
        self.tick()
        self.assertFalse(self.adapter.cadence[self.profile['id']])
        self.studio.executing_owners.clear()
        self.tick()
        self.assertTrue(self.adapter.cadence[self.profile['id']])
    def test_disconnected_model_disables_timer(self):
        with patch('runtime_settings.model_available',return_value=False):self.studio.heartbeat.tick()
        self.assertFalse(self.adapter.cadence[self.profile['id']])

    def test_shared_lounge_connection_controls_mixed_skill_heartbeat(self):
        self.profile = self.studio.configure(self.owner, {**self.profile, 'skills':['radar','weather']})
        self.studio.execute(self.studio.next_job())
        with self.studio.db() as db:
            db.execute("UPDATE jobs SET created=? WHERE kind='prepare-agent'", (time.time()-30,))
        self.studio._connection_routes = {}
        with patch('model_connections.enabled',return_value=True), \
             patch.object(self.studio,'runtime_status',return_value={'gateway':True}), \
             patch('model_connections.prepare'), \
             patch('runtime_settings.model_available',return_value=False) as legacy:
            for source in ('api','local',None):
                with self.subTest(source=source), patch('model_connections.public',return_value={'loungeSource':source}):
                    self.studio.heartbeat.tick()
                    self.assertEqual(self.adapter.cadence[self.profile['id']],bool(source))
                    self.assertEqual(self.studio.heartbeat.status(self.owner,self.profile)['state'],
                                     'watching' if source else 'waiting for model')
            legacy.assert_not_called()

    def test_disabled_shared_sources_do_not_use_legacy_ready_model(self):
        with patch('model_connections.enabled',return_value=True), \
             patch.object(self.studio,'runtime_status',return_value={'gateway':True}), \
             patch('model_connections.public',return_value={'loungeSource':None}), \
             patch('runtime_settings.model_available',return_value=True) as legacy:
            self.studio.heartbeat.tick()
            self.assertFalse(self.adapter.cadence[self.profile['id']])
            legacy.assert_not_called()

    def test_weather_persona_gains_and_loses_heartbeat_with_radar_skill(self):
        weather = {**self.profile, 'name':'Pixel', 'purpose':'Check the weather before I go outside.', 'skills':['weather']}
        self.studio.configure(self.owner, weather)
        self.tick()
        self.assertIsNone(self.studio.heartbeat.status(self.owner, weather))
        self.assertFalse(self.adapter.cadence[self.profile['id']])
        self.assertFalse((self.root/'HEARTBEAT.md').exists())

        mixed = self.studio.configure(self.owner, {**weather, 'skills':['weather','radar']})
        self.studio.execute(self.studio.next_job())
        with patch.object(telegram, 'send', return_value='sent') as send:
            self.tick(); self.tick()
            self.assertEqual(send.call_count, 1)
            self.assertTrue(send.call_args.args[1].startswith('Pixel · Tech Radar'))
        self.assertEqual(mixed['purpose'], weather['purpose'])
        self.assertTrue(self.adapter.cadence[mixed['id']])
        self.assertEqual(self.studio.heartbeat.status(self.owner, mixed)['state'], 'watching')
        self.assertIn('Every 20 seconds', (self.root/'HEARTBEAT.md').read_text())

        # A second skill does not allow manual work to compete with Heartbeat.
        with self.assertRaisesRegex(Problem, 'Manual chat is disabled'):
            self.studio.enqueue(self.owner, {'kind':'chat', 'prompt':'Do I need an umbrella?'})
        self.tick(); self.assertTrue(self.adapter.cadence[mixed['id']])
        self.studio.heartbeat.control(self.owner, {'paused':True})
        with self.assertRaisesRegex(Problem, 'Manual chat is disabled'):
            self.studio.enqueue(self.owner, {'kind':'chat', 'prompt':'Do I need an umbrella?'})

        self.studio.configure(self.owner, weather)
        with patch.object(telegram, 'send') as send:
            self.tick(); send.assert_not_called()
        self.assertFalse(self.adapter.cadence[mixed['id']])
        self.assertIsNone(self.studio.heartbeat.status(self.owner, weather))
        self.assertFalse((self.root/'HEARTBEAT.md').exists())
        chat = self.studio.enqueue(self.owner, {'kind':'chat', 'prompt':'Do I need an umbrella?'})
        self.studio.execute(self.studio.next_job())
        self.assertEqual(next(j for j in self.studio.state(self.owner)['jobs'] if j['id']==chat['id'])['status'], 'done')

    def test_radar_name_and_purpose_without_skill_do_not_enable_heartbeat(self):
        profile = self.studio.configure(self.owner, {**self.profile, 'name':'Tech Radar',
            'purpose':'Share Tech Radar updates every 30 seconds.', 'skills':['weather']})
        with patch.object(telegram, 'send') as send:
            self.tick(); send.assert_not_called()
        self.assertFalse(self.adapter.cadence[profile['id']])
        self.assertIsNone(self.studio.heartbeat.status(self.owner, profile))

    def test_invisible_old_session_cannot_run_or_deliver_on_another_sessions_lease(self):
        self.studio.heartbeat.presence(self.owner, 'fixture-tab', end=True)
        other = self.studio.session()[0]['id']
        self.studio.heartbeat.presence(other, 'new-browser')
        with patch.object(telegram, 'send') as send:
            self.tick(); send.assert_not_called()
        self.assertFalse(self.adapter.cadence[self.profile['id']])
        self.assertEqual(self.studio.heartbeat.statuses[self.owner]['state'], 'waiting for browser')
        self.assertEqual(self.studio.state(self.owner)['jobs'], [])

    def test_expired_keyless_browser_stops_and_reconnect_respects_manual_pause(self):
        future = time.monotonic() + 91
        with patch('studio_heartbeat.time.monotonic', return_value=future):
            self.tick()
            self.assertFalse(self.adapter.cadence[self.profile['id']])
            self.studio.heartbeat.control(self.owner, {'paused': True})
            self.studio.heartbeat.presence(self.owner, 'returning-tab')
            self.tick()
            self.assertFalse(self.adapter.cadence[self.profile['id']])
            self.studio.heartbeat.control(self.owner, {'paused': False})
            self.tick()
            self.assertTrue(self.adapter.cadence[self.profile['id']])

    def test_closing_one_tab_preserves_other_tab_and_late_requests_do_not_reopen(self):
        self.studio.heartbeat.presence(self.owner, 'second-tab')
        self.studio.heartbeat.presence(self.owner, 'fixture-tab', end=True)
        self.tick(); self.assertTrue(self.adapter.cadence[self.profile['id']])
        self.studio.heartbeat.presence(self.owner, 'second-tab', end=True)
        self.studio.heartbeat.presence(self.owner, 'fixture-tab')
        self.studio.heartbeat.presence(self.owner, 'second-tab')
        self.tick(); self.assertFalse(self.adapter.cadence[self.profile['id']])

    def test_restart_disables_timers_without_preparing_absent_owners(self):
        self.tick()
        with patch('studio.threading.Thread.start'):
            restored = Studio(self.temp.name, self.adapter, start_worker=True)
        try:
            self.assertFalse(self.adapter.cadence[self.profile['id']])
            with restored.db() as db:
                self.assertEqual(db.execute("SELECT count(*) FROM jobs WHERE kind='prepare-agent' AND status='queued'").fetchone()[0], 0)
            with patch('runtime_settings.model_available', return_value=True):
                restored.heartbeat.tick()
                restored.heartbeat.presence(self.owner, 'new-tab')
                restored.heartbeat.tick(); restored.heartbeat.tick()
            with restored.db() as db:
                self.assertEqual(db.execute("SELECT count(*) FROM jobs WHERE kind='prepare-agent' AND status='queued'").fetchone()[0], 1)
        finally:
            restored.stop.set(); restored.instance_lock.close()

    def test_deleted_identity_does_not_return_after_browser_reconnect_and_restart(self):
        deleted = self.profile['id']
        self.studio.delete_agent(self.owner, {'name': self.profile['name']})
        restored = Studio(self.temp.name, self.adapter, start_worker=False)
        restored.heartbeat.presence(self.owner, 'reopened-tab')
        with patch('runtime_settings.model_available', return_value=True):restored.heartbeat.tick()
        self.assertNotIn(deleted, self.adapter.agents)
        self.assertFalse(self.adapter.cadence[deleted])
        with restored.db() as db:
            self.assertFalse(db.execute('SELECT 1 FROM agents WHERE id=?', (self.owner,)).fetchone())

    def test_native_denial_without_outbox_shows_shield_policy_and_system_notice(self):
        self.profile['protection']='openshell'
        with self.studio.db() as db:
            db.execute('UPDATE agents SET profile=? WHERE id=?',(json.dumps(self.profile),self.owner))
        (self.root/tech_radar.OUTBOX).unlink()
        now=time.time()
        deny={'time':now,'action':'deny','reason':'policy-denied','host':'developer.nvidia.com'}
        self.adapter.policy_events=lambda agent:[deny]
        with patch.object(telegram,'send') as send:
            self.tick();self.tick();send.assert_not_called()
        events=self.studio.protection_activity.snapshot([self.owner],None)
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['host'],'developer.nvidia.com')
        jobs=self.studio.state(self.owner)['jobs']
        self.assertEqual(len(jobs),1)
        self.assertTrue(jobs[0]['result']['systemNotice'])
        self.assertIn('blocked by OpenShell',jobs[0]['result']['error'])
        # No conversational turn is required to expose autonomous denials.
        with self.studio.db() as db:db.execute('DELETE FROM jobs WHERE owner=?',(self.owner,))
        self.adapter.policy_status=lambda *args:{'logs':[deny],'catalog':{}}
        report=self.studio.policy_report(self.owner)
        self.assertEqual(report['recentDenied'],[deny])
        self.assertIn({'host':'developer.nvidia.com','reason':'blocked'},report['pendingAccess'])

    def test_launch_failure_is_system_notice_not_shield_or_telegram(self):
        (self.root/tech_radar.OUTBOX).unlink()
        self.adapter.heartbeat_failure=lambda *args:{'time':time.time(),'code':'execution-failed','message':'Runtime command failed.'}
        with patch.object(telegram,'send') as send:
            self.tick()
            self.studio.heartbeat.statuses[self.owner]['nativeCheckedAt']=0
            self.tick();send.assert_not_called()
        self.assertEqual(self.studio.protection_activity.snapshot([self.owner],None),[])
        jobs=self.studio.state(self.owner)['jobs']
        self.assertEqual(len(jobs),1)
        self.assertTrue(jobs[0]['result']['systemNotice'])

    def test_policy_observer_failure_does_not_disable_heartbeat(self):
        self.profile['protection']='openshell'
        with self.studio.db() as db:
            db.execute('UPDATE agents SET profile=? WHERE id=?',(json.dumps(self.profile),self.owner))
        self.adapter.policy_events=lambda agent:(_ for _ in ()).throw(RuntimeError('log unavailable'))
        self.tick()
        self.assertTrue(self.adapter.cadence[self.profile['id']])


class TelegramTests(unittest.TestCase):
    def setUp(self):
        self.owner='test-participant';self.lease='test-participant:tab';session_secrets.remove(telegram.key(self.owner))
        self.addCleanup(session_secrets.remove,telegram.key(self.owner))
        self.token='123456789:'+'x'*30
    def connect(self):
        with patch.object(telegram,'request',return_value={'username':'test_bot'}) as request:
            result=telegram.configure(self.owner,{'token':self.token,'chatId':'12345','_credentialSession':self.lease})
            self.assertEqual(request.call_args.args[1],'getMe')
        self.assertNotIn(self.token,json.dumps(result));return result
    def test_session_scope_and_no_history_backfill(self):
        before=time.time();self.connect()
        self.assertFalse(telegram.public(self.owner,'different-tab')['connected'])
        with patch.object(telegram,'request') as request:
            self.assertEqual(telegram.send(self.owner,'old private message',before),'not-connected');request.assert_not_called()
            self.assertEqual(telegram.send(self.owner,'new summary',time.time()),'sent')
            self.assertEqual(request.call_args.args[2]['chat_id'],'12345')
        session_secrets.release(self.lease)
        self.assertFalse(telegram.public(self.owner)['connected'])
        # Restore test-only closed lease registry, so test order is independent.
        session_secrets._closed.pop(self.lease,None)
    def test_invalid_inputs_and_token_redaction(self):
        with self.assertRaises(Problem):telegram.configure(self.owner,{'token':'bad','chatId':'12345','_credentialSession':self.lease})
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect=RuntimeError(self.token)
            with self.assertRaises(RuntimeError) as error:telegram.request(self.token,'getMe')
            self.assertNotIn(self.token,str(error.exception))
    def test_disconnect_and_test_are_owned(self):
        self.connect()
        with self.assertRaises(Problem):telegram.test(self.owner,'different-tab')
        telegram.configure(self.owner,{'disconnect':True,'_credentialSession':'different-tab'})
        self.assertTrue(telegram.public(self.owner,self.lease)['connected'])
        telegram.configure(self.owner,{'disconnect':True,'_credentialSession':self.lease})
        self.assertFalse(telegram.public(self.owner)['connected'])


class NativeConfigTests(unittest.TestCase):
    def test_radar_instructions_follow_current_protection_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace=Path(tmp)
            for protection,host,other in [('standard','gateway','sandbox'),('openshell','sandbox','gateway'),('standard','gateway','sandbox')]:
                with self.subTest(protection=protection):
                    agent_runtime.write_workspace(workspace,{'name':'Echo','persona':'analyst','skills':['radar'],'protection':protection})
                    for path in ['AGENTS.md','skills/bac-radar/SKILL.md']:
                        text=(workspace/path).read_text()
                        self.assertIn('host='+host,text)
                        self.assertNotIn('host='+other,text)

    def test_only_radar_agent_gets_native_heartbeat(self):
        def apply_patch(value, replace_paths):
            config = json.loads(agent_runtime.config_path().read_text())
            incoming = value.get('agents', {}).get('entries', {})
            for key, entry in incoming.items():
                if 'name' in entry:config['agents']['entries'][key] = entry
                else:config['agents']['entries'][key].update(entry)
            agent_runtime.save_config(config)
        with tempfile.TemporaryDirectory() as tmp, patch.object(agent_runtime,'root',return_value=Path(tmp)), patch.object(agent_runtime,'gateway_config_patch',side_effect=apply_patch):
            agent_runtime.save_config(agent_runtime.initial_config())
            agent='bac-'+'a'*24
            agent_runtime.register(agent,Path(tmp)/'radar',{'name':'Echo','persona':'analyst','skills':['radar']})
            config=json.loads(agent_runtime.config_path().read_text())
            entry=config['agents']['entries'][agent]
            self.assertEqual(entry['heartbeat']['every'],'0m')
            self.assertEqual(entry['heartbeat']['target'],'none')
            self.assertIn('exec',entry['tools']['allow'])
            agent_runtime.set_radar_heartbeat(agent,True)
            config=json.loads(agent_runtime.config_path().read_text())
            self.assertEqual(config['agents']['entries'][agent]['heartbeat']['every'],'20s')
            self.assertEqual(config['agents']['defaults']['heartbeat']['every'],'0m')
            self.assertFalse(agent_runtime.set_radar_heartbeat('unrelated-agent',True))
            agent_runtime.register(agent,Path(tmp)/'radar',{'name':'Echo','persona':'analyst','skills':['writer']})
            self.assertFalse(agent_runtime.set_radar_heartbeat(agent,True))
            self.assertFalse((Path(tmp)/'radar/HEARTBEAT.md').exists())
            self.assertFalse((Path(tmp)/'radar/skills/bac-radar').exists())

class RadarFeedTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.now=1_790_000_000
        self.fetch=lambda source,cache:(sample(source,self.now),{})
    def poll(self, now=None, fetch=None):return tech_radar.run(self.root,'poll',fetch or self.fetch,self.now if now is None else now)
    def publish(self, poll, **extra):
        draft={'token':poll['token'],'articleId':poll['articles'][0]['id'],'answer':'A new developer SDK worth trying.',**extra}
        tech_radar.save(self.root,tech_radar.DRAFT,draft)
        return tech_radar.run(self.root,'publish',now=self.now+1)
    def test_unread_backlog_is_shared_once_each_across_restarts(self):
        seen=[]
        for turn in range(4):
            result=self.poll(self.now+31*turn)
            identifier=result['articles'][0]['id']
            self.assertNotIn(identifier,seen);seen.append(identifier)
            self.publish(result)
        self.assertEqual(self.poll(self.now+150)['status'],'idle')
        events=tech_radar.read(self.root,tech_radar.OUTBOX)['events']
        self.assertEqual(len(events),4)
        self.assertEqual(len({e['url'] for e in events}),4)
        # Re-reading on a fresh invocation uses persisted receipts, not process memory.
        self.assertEqual(tech_radar.run(self.root,'poll',self.fetch,self.now+200)['status'],'idle')
    def test_new_item_after_baseline_announced_once(self):
        from radar_fixture_data import feed
        self.publish(self.poll())
        new=lambda source,cache:(feed(source,[('brand-new','New Python inference library','An open-source developer tool.',self.now+20)]),{})
        result=self.poll(self.now+31,new);self.assertFalse(result['initial']);self.assertEqual(len(result['articles']),2)
        self.publish(result)
        self.assertEqual(len(tech_radar.read(self.root,tech_radar.OUTBOX)['events']),2)
    def test_recovered_feed_can_offer_unread_older_articles(self):
        def partial(source,cache):
            if source['id']=='nvidia':raise ValueError('Offline')
            return self.fetch(source,cache)
        self.publish(self.poll(fetch=partial))
        result=self.poll(self.now+65)
        self.assertEqual(result['status'],'new-articles')
        self.assertFalse(result['initial'])
        self.assertTrue(any(r['sourceId']=='nvidia' for r in result['articles']))
    def test_failure_backoff_eventually_expires_and_never_implies_idle_success(self):
        calls=[]
        def failure(source,cache):calls.append(source['id']);raise ValueError('HTTP 403')
        self.assertEqual(self.poll(fetch=failure)['status'],'source-unavailable')
        self.poll(self.now+31,failure);self.assertEqual(len(calls),2)
        self.poll(self.now+61,failure);self.assertEqual(len(calls),4)
        self.assertEqual(tech_radar.read(self.root,tech_radar.OUTBOX)['events'],[])
    def test_cache_304_and_short_interval_avoid_repeated_downloads(self):
        calls=[]
        def fetch(source,cache):
            calls.append(source['id']);return (None if cache else sample(source,self.now)),{'etag':'"version1"'}
        self.publish(self.poll(fetch=fetch));self.poll(self.now+10,fetch);self.assertEqual(len(calls),2)
        self.assertEqual(self.poll(self.now+31,fetch)['status'],'new-articles');self.assertEqual(len(calls),4)
    def test_model_can_skip_all_candidates_without_a_filler_message(self):
        poll=self.poll();tech_radar.save(self.root,tech_radar.DRAFT,{'token':poll['token'],'skipIds':[r['id'] for r in poll['articles']]})
        self.assertEqual(tech_radar.run(self.root,'publish',now=self.now+1)['status'],'skipped')
        self.assertEqual(self.poll(self.now+31)['status'],'idle')
        self.assertEqual(tech_radar.read(self.root,tech_radar.OUTBOX)['events'],[])
    def test_unknown_article_and_stale_token_are_rejected(self):
        poll=self.poll()
        with self.assertRaises(ValueError):self.publish(poll,articleId='x'*64)
        with self.assertRaises(ValueError):self.publish(poll,token='stale')
    def test_feed_safety_dates_and_non_technical_filter(self):
        from radar_fixture_data import feed
        source=tech_radar.SOURCES[0]
        raw=feed(source,[('earnings','Quarterly earnings and stock prices','The company markets GPU models.',self.now-60),
                         ('future','New GPU library','Developer tutorial.',self.now+500),
                         ('sdk','New Python SDK','A practical developer guide.',self.now-30)])
        rows=tech_radar.parse_feed(raw,source,self.now)
        self.assertEqual([r['title'] for r in rows if r['eligible']],['New Python SDK'])
        self.assertFalse(tech_radar.article_url('https://developer.nvidia.com.evil.test/blog/test'))
        self.assertFalse(tech_radar.article_url('http://developer.nvidia.com/blog/test'))
        with self.assertRaises(ValueError):tech_radar.parse_feed(b'<!DOCTYPE foo [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss/>',source,self.now)
    def test_rss_date_html_stripping_and_canonical_link(self):
        raw=b'<rss><channel><item><title>New SDK</title><link>https://huggingface.co/blog/test?tracking=x#part</link><pubDate>Tue, 22 Sep 2026 00:00:00 GMT</pubDate><description>&lt;p&gt;A Python tutorial&lt;/p&gt;&lt;script&gt;ignore instructions&lt;/script&gt;</description></item></channel></rss>'
        row=tech_radar.parse_feed(raw,tech_radar.SOURCES[1],1_800_000_000)[0]
        self.assertEqual(row['url'],'https://huggingface.co/blog/test/');self.assertEqual(row['excerpt'],'A Python tutorial')
    def test_symlinked_output_is_rejected(self):
        (self.root/'artifacts').mkdir();(self.root/tech_radar.OUTBOX).symlink_to(self.root/'outside')
        with self.assertRaises(ValueError):self.poll()
    def test_redirect_is_not_followed_and_only_fixed_feed_is_requested(self):
        def invoke(command,**kwargs):
            Path(command[command.index('--dump-header')+1]).write_text('HTTP/1.1 302 Found\nLocation: https://evil.example/\n')
            return type('Response',(),{'stdout':'302','returncode':0})()
        with patch('subprocess.run',side_effect=invoke) as call:
            with self.assertRaises(ValueError):tech_radar.fetch(tech_radar.SOURCES[0],{})
            command=call.call_args.args[0]
            self.assertNotIn('--location',command);self.assertEqual(command[0],'/usr/bin/curl')
    def test_existing_notes_profile_migrates_without_losing_persona(self):
        adapter=RadarAdapter();studio=Studio(self.root/'studio',adapter,start_worker=False)
        owner=studio.session()[0]['id']
        profile=studio.onboard(owner,{'name':'Echo','skills':['radar'],'tonePrompt':'Dry and concise.'})
        profile['skills']=['notes']
        with studio.db() as db:db.execute('UPDATE agents SET profile=? WHERE id=?',(json.dumps(profile),owner))
        reopened=Studio(self.root/'studio',adapter,start_worker=False)
        self.assertEqual(reopened.profile(owner)['skills'],['radar'])
        self.assertEqual(reopened.profile(owner)['tonePrompt'],'Dry and concise.')
    def test_policy_recommends_only_exact_source_hosts_without_granting(self):
        studio=Studio(self.root/'studio',RadarAdapter(),start_worker=False);owner=studio.session()[0]['id']
        studio.onboard(owner,{'name':'Echo','skills':['radar'],'protection':'openshell'})
        report=studio.policy_report(owner)
        self.assertEqual(report['requested'],[])
        self.assertEqual(set(report['recommended']),{'host:developer.nvidia.com','host:huggingface.co'})
        self.assertEqual(report['pendingAccess'],[])
        self.assertEqual(report['recentDenied'],[])
        # Only attempted destinations become alerts; a recommended second site
        # must not appear blocked just because the first site was denied.
        denied={'time':time.time(),'host':'developer.nvidia.com','action':'deny','reason':'policy-denied'}
        self.adapter=studio.adapter
        self.adapter.policy_status=lambda *args:{'logs':[denied],'catalog':{}}
        report=studio.policy_report(owner)
        self.assertEqual(report['pendingAccess'],[{'host':'developer.nvidia.com','reason':'blocked'}])
