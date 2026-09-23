import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).parent)]
import agent_runtime
import notes_watch
import session_secrets
import telegram_notifications as telegram
from studio import Studio, Problem
from test_studio import Adapter


class NotesToolTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'inbox').mkdir();(self.root/'artifacts').mkdir()
        (self.root/'inbox/meeting.txt').write_text('Launch moved to Friday. Pat will revise the slides.')
        notes_watch.save(self.root,notes_watch.MANIFEST,['inbox/meeting.txt'])
    def publish(self):
        result=notes_watch.run(self.root,'poll')
        notes_watch.save(self.root,'artifacts/notes-draft.json',{'token':result['token'],'answer':'Pat will revise slides before Friday.'})
        return notes_watch.run(self.root,'publish')
    def test_changed_upload_and_durable_dedup(self):
        self.publish()
        self.assertEqual(notes_watch.run(self.root,'poll')['status'],'idle')
        self.assertEqual(notes_watch.run(self.root,'publish')['status'],'idle')
        (self.root/'inbox/meeting.txt').write_text('Launch moved to Monday.')
        self.publish()
        self.assertEqual(len(notes_watch.read(self.root,notes_watch.OUTBOX)['events']),2)
    def test_publish_rejects_document_changed_after_model_read(self):
        result=notes_watch.run(self.root,'poll')
        notes_watch.save(self.root,'artifacts/notes-draft.json',{'token':result['token'],'answer':'stale'})
        (self.root/'inbox/meeting.txt').write_text('Changed')
        with self.assertRaisesRegex(ValueError,'changed'):notes_watch.run(self.root,'publish')
    def test_paths_and_symlinks_never_read_outside_uploads(self):
        notes_watch.save(self.root,notes_watch.MANIFEST,['../secret.txt'])
        with self.assertRaises(ValueError):notes_watch.run(self.root,'poll')
        target=self.root/'outside.txt';target.write_text('secret')
        (self.root/'inbox/link.txt').symlink_to(target)
        notes_watch.save(self.root,notes_watch.MANIFEST,['inbox/link.txt'])
        self.assertEqual(notes_watch.run(self.root,'poll')['documents'],[])
    def test_draft_and_outbox_symlinks_rejected(self):
        (self.root/'artifacts/heartbeat-notes.json').symlink_to(self.root/'outside')
        with self.assertRaises(ValueError):notes_watch.run(self.root,'poll')
    def test_empty_uploads_are_quiet(self):
        notes_watch.save(self.root,notes_watch.MANIFEST,[])
        self.assertEqual(notes_watch.run(self.root,'poll')['status'],'idle')


class NotesAdapter(Adapter):
    def __init__(self):super().__init__();self.cadence={}
    def set_notes_heartbeat(self,agent,enabled):self.cadence[agent]=enabled;return agent in self.agents


class HeartbeatRelayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.adapter=NotesAdapter();self.studio=Studio(self.temp.name,self.adapter,start_worker=False)
        self.owner=self.studio.session()[0]['id']
        self.profile=self.studio.onboard(self.owner,{'name':'Echo','skills':['notes']})
        self.studio.execute(self.studio.next_job())
        self.root=self.studio.workspace(self.owner)
        self.studio.upload(self.owner,{'name':'meeting.txt','content':'Review design tomorrow.'})
        poll=notes_watch.run(self.root,'poll')
        notes_watch.save(self.root,'artifacts/notes-draft.json',{'token':poll['token'],'answer':'Review design tomorrow.'})
        notes_watch.run(self.root,'publish')
    def tick(self):
        with patch('runtime_settings.model_available',return_value=True):self.studio.notes.tick()
    def test_native_cadence_and_single_chat_result_even_after_restart(self):
        with patch.object(telegram,'send',return_value='sent') as send:
            self.tick();self.tick()
            self.assertEqual(send.call_count,1)
        jobs=self.studio.state(self.owner)['jobs']
        self.assertEqual(len(jobs),1);self.assertEqual(jobs[0]['kind'],'heartbeat')
        self.assertEqual(jobs[0]['result']['answer'],'Review design tomorrow.')
        self.assertTrue(self.adapter.cadence[self.profile['id']])
        again=Studio(self.temp.name,self.adapter,start_worker=False)
        with patch.object(telegram,'send') as send:
            again.notes.tick();send.assert_not_called()
    def test_pause_resume_no_duplicate(self):
        self.studio.notes.control(self.owner,{'paused':True});self.tick()
        self.assertFalse(self.adapter.cadence[self.profile['id']]);self.assertEqual(self.studio.state(self.owner)['jobs'],[])
        self.studio.notes.control(self.owner,{'paused':False});self.tick()
        self.assertTrue(self.adapter.cadence[self.profile['id']]);self.assertEqual(len(self.studio.state(self.owner)['jobs']),1)
    def test_transport_timeout_keeps_chat_without_automatic_retry(self):
        with patch.object(telegram,'send',side_effect=RuntimeError('timeout')) as send:
            self.tick();self.tick();self.assertEqual(send.call_count,1)
        self.assertEqual(self.studio.state(self.owner)['jobs'][0]['result']['telegram'],'failed')
    def test_invalid_model_output_not_published(self):
        notes_watch.save(self.root,notes_watch.OUTBOX,{'events':[{'id':'a'*64,'answer':'unsafe','files':['../../secret'],'created':time.time()}]})
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
        with patch('runtime_settings.model_available',return_value=False):self.studio.notes.tick()
        self.assertFalse(self.adapter.cadence[self.profile['id']])


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
    def test_only_notes_agent_gets_native_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(agent_runtime,'root',return_value=Path(tmp)):
            agent_runtime.save_config(agent_runtime.initial_config())
            agent='bac-'+'a'*24
            agent_runtime.register(agent,Path(tmp)/'notes',{'name':'Echo','persona':'analyst','skills':['notes']})
            config=json.loads(agent_runtime.config_path().read_text())
            entry=config['agents']['entries'][agent]
            self.assertEqual(entry['heartbeat']['every'],'0m')
            self.assertEqual(entry['heartbeat']['target'],'none')
            self.assertIn('exec',entry['tools']['allow'])
            agent_runtime.set_notes_heartbeat(agent,True)
            config=json.loads(agent_runtime.config_path().read_text())
            self.assertEqual(config['agents']['entries'][agent]['heartbeat']['every'],'30s')
            self.assertEqual(config['agents']['defaults']['heartbeat']['every'],'0m')
            self.assertFalse(agent_runtime.set_notes_heartbeat('unrelated-agent',True))
            agent_runtime.register(agent,Path(tmp)/'notes',{'name':'Echo','persona':'analyst','skills':['writer']})
            self.assertFalse(agent_runtime.set_notes_heartbeat(agent,True))
            self.assertFalse((Path(tmp)/'notes/HEARTBEAT.md').exists())
            self.assertFalse((Path(tmp)/'notes/skills/bac-notes').exists())
