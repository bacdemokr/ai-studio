import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import scenario_models as models
import team_models
import runtime_settings
from studio import Studio, Problem
from test_studio import Adapter

class ScenarioModelsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        env=patch.dict(os.environ,{'BAC_DATA_DIR':self.temp.name});env.start();self.addCleanup(env.stop)
        self.app=Studio(Path(self.temp.name)/'studio',Adapter(),start_worker=False)
        self.owner=self.app.session()[0]['id']
        self.local={'provider':'local','baseUrl':'http://127.0.0.1:8000/v1','model':'qwen/test','contextWindow':32768}

    def configure(self):
        with patch.object(runtime_settings,'request',return_value={'data':[{'id':'qwen/test'}]}) as request:
            result=models.configure(self.app,self.owner,self.local)
            self.assertEqual(request.call_args.args[1]['apiKey'],'')
            return result

    def test_source_is_scoped_and_restores_api(self):
        self.assertEqual(models.connection(self.app,self.owner),{'provider':'api'})
        self.configure()
        self.assertEqual(models.connection(self.app,'another-scenario'),{'provider':'api'})
        result=models.configure(self.app,self.owner,{'provider':'api'})
        self.assertEqual(result['teamConnection']['local']['model'],'qwen/test')
        self.assertNotIn('apiKey',json.dumps(result))

    def test_failed_probe_keeps_previous_source(self):
        with patch.object(runtime_settings,'request',return_value={'data':[]}):
            with self.assertRaises(Problem):models.configure(self.app,self.owner,self.local)
        self.assertEqual(models.connection(self.app,self.owner),{'provider':'api'})
        with self.assertRaises(Problem):models.local_profile({**self.local,'baseUrl':'https://example.com/v1'})

    def test_local_pin_survives_api_configuration(self):
        self.configure()
        agent={'id':'bac-'+'a'*24+'-r0'}
        models.prepare(self.app,self.owner,agent)
        config={'agents':{'entries':{agent['id']:{'model':agent['_teamModel']}}}}
        team_models.apply(config,selected=agent['_teamModel'],local=agent['_teamLocal'],agent_id=agent['id'])
        team_models.apply(config)
        self.assertEqual(config['agents']['entries'][agent['id']]['model'],agent['_teamModel'])
        provider=config['models']['providers'][team_models.local_provider(agent['id'])]
        self.assertEqual(provider['baseUrl'],self.local['baseUrl'])
        self.assertNotIn('qwen/test',[m['id'] for m in config['models']['providers']['bac-team']['models']])

    def test_local_readiness_requires_gateway(self):
        self.configure()
        self.app.runtime_status=lambda:{'gateway':False,'teamReady':True}
        self.assertFalse(models.readiness(self.app,self.owner)['teamReady'])
        self.app.runtime_status=lambda:{'gateway':True,'teamReady':False}
        self.assertTrue(models.readiness(self.app,self.owner)['teamReady'])

    def test_busy_rejected_before_network(self):
        with patch.object(self.app,'require_team_idle',side_effect=Problem('Busy')),patch.object(runtime_settings,'request') as request:
            with self.assertRaises(Problem):models.configure(self.app,self.owner,self.local)
            request.assert_not_called()
