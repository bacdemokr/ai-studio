import json
import sqlite3
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parent)]
import telemetry
import agent_runtime
from studio import Studio
from fixture_studio import BrowserAdapter

class TelemetryTests(unittest.TestCase):
    def test_model_endpoint_reports_external_and_local_routes_without_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'config.json'
            config={'agents':{'defaults':{'model':{'primary':'bac-team/model'}},'entries':{'external':{'model':'bac-team/model'},'local':{'model':'bac-team-local-a/model'}}},
                    'models':{'providers':{'bac-team':{'baseUrl':'http://127.0.0.1:3210/provider/team/v1'},
                                           'bac-team-local-a':{'baseUrl':'http://127.0.0.1:8000/v1'}}}}
            path.write_text(json.dumps(config))
            with patch('agent_runtime.config_path',return_value=path):
                self.assertEqual(agent_runtime.model_endpoint('external'),'External · NVIDIA Inference · https://inference-api.nvidia.com/v1')
                self.assertEqual(agent_runtime.model_endpoint('local'),'Local · Local model · http://127.0.0.1:8000/v1')

    def test_public_job_includes_updated_time_for_completed_run_duration(self):
        row={'id':'job','kind':'crew-chat','status':'done','payload':'{}','result':'{}','events':'[]',
             'created':100.0,'updated':125.5,'due':100.0}
        public=Studio.public_job(row)
        self.assertEqual(public['updated'],125.5)
        self.assertEqual(public['payload'],{})

    def test_speed_uses_output_only_and_elapsed_response_time(self):
        with tempfile.TemporaryDirectory() as folder:
            result={'usage':{'prompt_tokens':10000,'completion_tokens':240,'total_tokens':10240}}
            record=telemetry.measure(result,folder,'a','s',0,elapsed=12)
            self.assertEqual(record['outputTokensPerSecond'],20)
            self.assertEqual(record['runSeconds'],12)
            for duration in (None,0,-1,float('nan'),float('inf'),True):
                self.assertIsNone(telemetry.measure(result,folder,'a','s',0,elapsed=duration)['outputTokensPerSecond'])
            self.assertIsNone(telemetry.measure({},folder,'a','s',0,elapsed=12)['outputTokensPerSecond'])
            self.assertIsNone(telemetry.measure({'usage':{'total_tokens':240}},folder,'a','s',0,elapsed=12)['outputTokensPerSecond'])
            zero={'usage':{'prompt_tokens':100,'completion_tokens':0,'total_tokens':100}}
            self.assertEqual(telemetry.measure(zero,folder,'a','s',0,elapsed=12)['outputTokensPerSecond'],0)

    def native_session(self, folder, agent, session, entry):
        path=Path(folder)/'agents'/agent/'agent/openclaw-agent.sqlite'
        path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS session_nodes (session_key TEXT PRIMARY KEY,entry_json TEXT)')
            db.execute('INSERT OR REPLACE INTO session_nodes VALUES (?,?)',('agent:'+agent+':openai-user:'+session,json.dumps(entry)))
        return path

    def test_sqlite_context_scoping_freshness_and_legacy_precedence(self):
        with tempfile.TemporaryDirectory() as folder:
            started=time.time()
            entry={'updatedAt':(started+1)*1000,'totalTokens':1234,'contextTokens':32768,
                   'totalTokensFresh':True,'totalTokensVersion':1,'model':'bac-qwen'}
            path=self.native_session(folder,'a','s',entry)
            legacy=Path(folder)/'agents/a/sessions/sessions.json';legacy.parent.mkdir()
            legacy.write_text(json.dumps({'agent:a:openai-user:other':entry}))
            observed=telemetry.measure({'usage':{'total_tokens':90000}},folder,'a','s',started)
            self.assertEqual((observed['context'],observed['limit'],observed['model']),(1234,32768,'bac-qwen'))
            self.assertEqual(observed['total'],90000)
            self.assertEqual(observed['session'],'s')
            self.assertIsNone(telemetry.measure({},folder,'a','other',started)['context'])
            self.assertIsNone(telemetry.measure({},folder,'a','s',started+2)['context'])
            self.assertIsNone(telemetry.context_usage(folder,'a','s',started,started+.5)['context'])
            for change in ({'totalTokensFresh':False},{'totalTokensVersion':2},{'updatedAt':None}):
                self.native_session(folder,'a','s',{**entry,**change})
                self.assertIsNone(telemetry.measure({},folder,'a','s',started)['context'])
            with sqlite3.connect(path) as db:db.execute('DROP TABLE session_nodes')
            self.assertIsNone(telemetry.measure({},folder,'a','s',started)['context'])

    def test_missing_native_store_is_not_created(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(telemetry.measure({},folder,'a','s',0)['context'])
            self.assertEqual(list(Path(folder).iterdir()),[])

    def test_old_run_context_recovers_without_changing_cumulative_usage(self):
        with tempfile.TemporaryDirectory() as folder,patch('agent_runtime.root',return_value=Path(folder)),patch.object(telemetry,'host',return_value={}):
            studio=Studio(Path(folder)/'studio',BrowserAdapter(),start_worker=False)
            owner=studio.session()[0]['id'];agent='bac-'+owner
            studio.onboard(owner,{'name':'Agent','persona':'guide','skills':['weather']})
            job=studio.enqueue(owner,{'prompt':'Hello'})
            studio.decision(owner,job['id'],'cancel')
            measured=time.time()+1
            payload={'metrics':{'0':{'agent':agent,'name':'Agent','total':90000,'context':None,'limit':None,'measuredAt':measured}}}
            with studio.db() as db:db.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(payload),job['id']))
            entry={'updatedAt':measured*1000,'totalTokens':1234,'contextTokens':32768,'totalTokensFresh':True,'totalTokensVersion':1}
            self.native_session(Path(folder)/'state',agent,agent,entry)
            report=telemetry.report(studio,owner)
            self.assertEqual(report['agents'][0]['context'],1234)
            self.assertEqual(report['agents'][0]['limit'],32768)
            self.assertEqual(report['total'],90000)
            with studio.db() as db:
                self.assertEqual(json.loads(db.execute('SELECT payload FROM jobs WHERE id=?',(job['id'],)).fetchone()['payload']),payload)
            self.native_session(Path(folder)/'state',agent,agent,{**entry,'updatedAt':(measured+2)*1000})
            self.assertIsNone(telemetry.report(studio,owner)['agents'][0]['context'])

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
