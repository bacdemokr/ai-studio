import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import agent_runtime as runtime
from research_recovery import recovered_sources, evidence_note
from test_collaboration_plan import CollaborationTests
from agent_runtime import GatewayError


class SourceRecoveryTests(unittest.TestCase):
    def test_generic_http_failure_preserves_evidence_without_replay(self):
        sources=[{'url':'https://example.com/','text':'excerpt','truncated':False}]
        def gateway(route,*args,**kwargs):
            if route=='/v1/models':return {'data':[{'id':'openclaw/a'}]}
            raise GatewayError('HTTP 500','request_failed')
        with patch.object(runtime,'gateway',side_effect=gateway) as calls, \
             patch.object(runtime,'observed_activity',return_value={'calls':[]}), \
             patch('agent_activity.model_failure',return_value=None), \
             patch('agent_activity.context_failure',return_value=None), \
             patch('research_recovery.recovered_sources',return_value=sources), \
             patch('user_location.context',return_value=''):
            with self.assertRaises(GatewayError) as raised:runtime.respond('a','s','Research')
        self.assertEqual(raised.exception.reason,'request_failed')
        self.assertEqual(raised.exception.recovered_sources,sources)
        self.assertEqual(sum(c.args[0]=='/v1/chat/completions' for c in calls.call_args_list),1)

    def test_timeout_diagnosis_and_evidence_do_not_replay_model_request(self):
        sources=[{'url':'https://example.com/','text':'excerpt','truncated':False}]
        def gateway(route,*args,**kwargs):
            if route=='/v1/models':return {'data':[{'id':'openclaw/a'}]}
            raise GatewayError('Generic timeout','timeout')
        with patch.object(runtime,'gateway',side_effect=gateway) as calls, \
             patch.object(runtime,'observed_activity',return_value={'calls':[{'status':'completed'}]}), \
             patch('research_recovery.recovered_sources',return_value=sources), \
             patch('user_location.context',return_value=''):
            with self.assertRaises(GatewayError) as raised:runtime.respond('a','s','Research')
        self.assertEqual(raised.exception.recovered_sources,sources)
        self.assertIn('1 tool calls completed',str(raised.exception))
        self.assertIn('does not by itself mean the connection failed',str(raised.exception))
        self.assertEqual(sum(c.args[0]=='/v1/chat/completions' for c in calls.call_args_list),1)

    def test_only_matching_successful_fetches_and_bounded_text(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'agents/a/agent/openclaw-agent.sqlite';path.parent.mkdir(parents=True)
            with sqlite3.connect(path) as db:
                db.executescript('CREATE TABLE session_windows(session_id,session_key); CREATE TABLE transcript_events(session_id,seq,created_at,event_json);')
                db.execute('INSERT INTO session_windows VALUES(1,?)',('agent:a:openai-user:s',))
                db.execute('INSERT INTO session_windows VALUES(2,?)',('agent:a:openai-user:other',))
                def add(seq, message, sid=1,stamp=2000):db.execute('INSERT INTO transcript_events VALUES(?,?,?,?)',(sid,seq,stamp,json.dumps({'message':message})))
                add(1,{'role':'assistant','content':[{'type':'thinking','thinking':'PRIVATE'},{'type':'toolCall','name':'web_fetch','id':'ok'}]})
                def result(url='https://example.com/',status=200):return {'role':'toolResult','toolCallId':'ok','details':{'url':url,'status':status,'text':'X'*7000}}
                add(2,result(),sid=2)
                add(3,result(),stamp=0)
                add(4,result(status=403))
                add(5,result('https://secret:password@example.com/'))
                add(6,{**result(),'isError':True})
                add(7,result())
                add(8,result())
            sources=recovered_sources(folder,'a','s',1)
            self.assertEqual(len(sources),1)
            self.assertEqual(len(sources[0]['text']),6000)
            self.assertTrue(sources[0]['truncated'])
            self.assertNotIn('PRIVATE',evidence_note(sources))
            self.assertEqual(recovered_sources(folder,'a','missing',1),[])


class TimeoutPlanTests(CollaborationTests):
    def test_timeout_exports_evidence_without_retry_or_downstream_execution(self):
        self.check_failed_research('timeout')

    def test_http_failure_exports_evidence_without_retry_or_downstream_execution(self):
        self.check_failed_research('request_failed')

    def check_failed_research(self, reason):
        original=self.adapter.respond
        def respond(agent,session,prompt,**kwargs):
            if session.endswith('-working'):
                self.assertIn('Save after each useful read',prompt)
                self.assertIn('360 seconds',prompt)
                error=GatewayError('Research failed',reason)
                error.recovered_sources=[{'url':'https://example.com/','text':'UNTRUSTED_SOURCE','truncated':False}]
                raise error
            return original(agent,session,prompt,**kwargs)
        self.adapter.respond=respond
        result=self.start();self.app.execute(self.app.next_job())
        job=self.job(result);plan=job['payload']['collaboration']
        self.assertEqual(plan['outcome'],'partial')
        self.assertEqual(plan['failure']['reason'],reason)
        self.assertEqual(plan['calledRoles'],[8])
        self.assertTrue(plan['outputs']['8']['incomplete'])
        files=plan['outputs']['8']['files'];self.assertTrue(files)
        self.assertIn('UNTRUSTED_SOURCE',(self.app.workspace(self.app.crew_owner(self.owner))/files[0]).read_text())
        self.assertEqual(self.adapter.reaction_calls,[])
