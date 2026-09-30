import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import agent_runtime as runtime
from agent_activity import unexecuted_write,text_tool_write_path

LEAK='<tool_call>\n<function=write>\n<parameter=path>artifacts/demo.html</parameter>\n<parameter=content>PRIVATE_HTML</parameter>'

class UnexecutedWriteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);path=self.root/'agents/a/agent/openclaw-agent.sqlite'
        path.parent.mkdir(parents=True)
        self.db=sqlite3.connect(path);self.addCleanup(self.db.close)
        self.db.executescript('CREATE TABLE session_windows(session_id TEXT, session_key TEXT); CREATE TABLE transcript_events(session_id TEXT,seq INTEGER,created_at INTEGER,event_json TEXT);')
        self.db.execute('INSERT INTO session_windows VALUES (?,?)',('one','agent:a:openai-user:s'))
        self.seq=0
    def add(self,message):
        self.seq+=1
        self.db.execute('INSERT INTO transcript_events VALUES (?,?,?,?)',('one',self.seq,1000+self.seq,json.dumps({'message':message})))
        self.db.commit()
    def leak(self):
        self.add({'role':'assistant','stopReason':'length','content':[]})
        self.add({'role':'assistant','content':[{'type':'text','text':LEAK}]})
        self.add({'role':'assistant','content':[{'type':'text','text':'Saved the page successfully.'}]})
    def test_hidden_leak_survives_later_completion_claim(self):
        self.leak()
        self.assertTrue(unexecuted_write(self.root,'a','s',1))
        self.assertFalse(unexecuted_write(self.root,'a','other',1))
        self.assertFalse(unexecuted_write(self.root,'a','s',2))
    def test_successful_real_write_clears_only_matching_failure(self):
        self.leak()
        for path in ['artifacts/other.html','artifacts/demo.html']:
            self.add({'role':'assistant','content':[{'type':'toolCall','name':'write','id':path,'arguments':{'path':path}}]})
            self.add({'role':'toolResult','toolCallId':path,'isError':True})
            self.assertTrue(unexecuted_write(self.root,'a','s',1))
            self.add({'role':'toolResult','toolCallId':path,'isError':False})
            self.assertEqual(unexecuted_write(self.root,'a','s',1),path!='artifacts/demo.html')
    def test_quoted_example_and_source_read_do_not_trigger(self):
        self.assertIsNone(text_tool_write_path('Example:\n'+LEAK))
        self.add({'role':'toolResult','content':[{'type':'text','text':LEAK}]})
        self.assertFalse(unexecuted_write(self.root,'a','s',1))
    def test_runtime_rejects_success_claim_after_hidden_leak(self):
        def gateway(path,*args,**kwargs):
            if path=='/v1/models':return {'data':[{'id':'openclaw/a'}]}
            return {'choices':[{'finish_reason':'stop','message':{'content':'Saved successfully'}}]}
        with patch.object(runtime,'gateway',side_effect=gateway),patch('agent_activity.unexecuted_write',return_value=True),patch.object(runtime,'observed_activity',return_value={'calls':[]}),patch('user_location.context',return_value=''):
            with self.assertRaises(runtime.GatewayError) as error:runtime.respond('a','s','build')
        self.assertEqual(error.exception.reason,'unexecuted-tool-call')
        self.assertNotIn('PRIVATE_HTML',str(error.exception))
    def test_runtime_rejects_direct_leak_without_transcript(self):
        def gateway(path,*args,**kwargs):
            if path=='/v1/models':return {'data':[{'id':'openclaw/a'}]}
            return {'choices':[{'message':{'content':LEAK}}]}
        with patch.object(runtime,'gateway',side_effect=gateway),patch.object(runtime,'observed_activity',return_value={'calls':[]}),patch('user_location.context',return_value=''):
            with self.assertRaises(runtime.GatewayError) as error:runtime.respond('a','s','build')
        self.assertEqual(error.exception.reason,'unexecuted-tool-call')
