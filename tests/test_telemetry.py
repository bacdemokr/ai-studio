import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parent)]
import telemetry
from studio import Studio
from fixture_studio import BrowserAdapter

class TelemetryTests(unittest.TestCase):
    def test_context_is_not_aggregate_and_stale_context_is_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'agents/a/sessions/sessions.json';path.parent.mkdir(parents=True)
            started=time.time();entry={'updatedAt':(started+1)*1000,'totalTokens':1234,'contextTokens':32768,'totalTokensFresh':True,'totalTokensVersion':1}
            path.write_text(json.dumps({'agent:a:openai-user:s':entry}))
            result={'usage':{'prompt_tokens':50000,'completion_tokens':2000,'total_tokens':52000}}
            observed=telemetry.measure(result,folder,'a','s',started)
            self.assertEqual(observed['context'],1234);self.assertEqual(observed['total'],52000)
            self.assertIsNone(telemetry.measure(result,folder,'a','other',started)['context'])
            self.assertIsNone(telemetry.measure(result,folder,'a','s',started+5)['context'])
            self.assertIsNone(telemetry.measure({'usage':{'total_tokens':0}},folder,'a','s',started)['total'])
    def test_persisted_usage_scoped_to_participant_and_not_double_counted(self):
        class Adapter(BrowserAdapter):
            def respond(self,*args):return telemetry.Reply(super().respond(*args),{'total':150,'input':100,'output':50,'context':100,'limit':1000})
        with tempfile.TemporaryDirectory() as folder,patch.object(telemetry,'host',return_value={'cpu':12,'memory':34}):
            studio=Studio(folder,Adapter(),start_worker=False)
            owner=studio.session()[0]['id'];other=studio.session()[0]['id']
            studio.enqueue(owner,{'kind':'crew','preset':True,'brief':{'schema':2}})
            studio.execute(studio.next_job())
            first=telemetry.report(studio,owner);second=telemetry.report(studio,owner)
            self.assertEqual(first['total'],900);self.assertEqual(first,second)
            self.assertEqual(len(first['agents']),6);self.assertEqual(first['agents'][0]['context'],100)
            self.assertIsNone(telemetry.report(studio,other)['total'])
            restored=Studio(folder,Adapter(),start_worker=False)
            self.assertEqual(telemetry.report(restored,owner)['total'],900)
