import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import team_models as team
import runtime_settings as settings
import agent_runtime as runtime
import session_secrets as vault
from studio import Studio, Problem
from test_studio import Adapter
from runtime_health import RuntimeHealth


class TeamModelTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        env=patch.dict(os.environ,{'BAC_DATA_DIR':self.temp.name});env.start();self.addCleanup(env.stop)
        self.app=Studio(Path(self.temp.name)/'studio',Adapter(),start_worker=False)
        self.cap='bac-'+'a'*24+'-r0';self.research='bac-'+'a'*24+'-r8'
        runtime.save_config(runtime.initial_config())
        self.key='fixture-team-key-not-real'

    def configure(self):
        with patch.object(settings,'request',return_value={'data':[{'id':m} for m in team.MODELS]}):
            return team.configure(self.app,{'apiKey':self.key,'_credentialSession':'team-session-'+self.temp.name})

    def test_team_independent_of_settings_and_session_release(self):
        config=runtime.initial_config();config['agents']['entries']={a:{'model':'old','tools':{'deny':['exec']}} for a in [self.cap,self.research,'bac-personal']};runtime.save_config(config)
        self.assertTrue(self.configure()['connected'])
        original=settings.read()
        settings.save(self.app,{'provider':'local','baseUrl':'http://127.0.0.1:8000/v1','model':'local-test','apiKey':'','_credentialSession':'general'})
        config=json.loads(runtime.config_path().read_text())
        self.assertEqual(config['agents']['entries'][self.cap]['model'],'bac-team/'+team.MODELS[0])
        self.assertEqual(config['agents']['entries'][self.research]['modelPolicy']['allow'],['bac-team/'+team.MODELS[1]])
        self.assertEqual(config['agents']['entries']['bac-personal']['model'],'bac-local/local-test')
        self.assertEqual(config['agents']['entries'][self.cap]['tools'],{'deny':['exec']})
        vault.release('general');self.assertTrue(team.public()['connected'])
        self.assertEqual(vault.get(settings.secret_key('team'))['apiKey'],self.key)
        for path in Path(self.temp.name).rglob('*'):
            if path.is_file():self.assertNotIn(self.key.encode(),path.read_bytes())
        vault.release('team-session-'+self.temp.name);self.assertFalse(team.public()['connected'])

    def test_missing_model_and_active_work_do_not_replace_key(self):
        self.configure()
        with patch.object(settings,'request',return_value={'data':[]}):
            with self.assertRaises(Problem):team.configure(self.app,{'apiKey':'other'})
        self.assertEqual(vault.get(settings.secret_key('team'))['apiKey'],self.key)
        owner=self.app.session()[0]['id'];self.app.onboard(owner,{'name':'Test','skills':['web']});self.app.enqueue(owner,{'kind':'chat','prompt':'Hello'})
        with patch.object(settings,'request',return_value={'data':[{'id':m} for m in team.MODELS]}):
            with self.assertRaises(Problem):team.configure(self.app,{'apiKey':'other'})
        self.assertEqual(vault.get(settings.secret_key('team'))['apiKey'],self.key)

    def test_runtime_readiness_and_routing_do_not_follow_local_model(self):
        h=RuntimeHealth();value=h.observe({'gatewayProbe':'ok','model':False,'teamModel':True},1)
        self.assertTrue(value['teamReady']);self.assertFalse(value['ready'])
        self.app.runtime_status=lambda: {'ready':False,'teamReady':True}
        owner=self.app.session()[0]['id']
        team_owner=self.app.crew_owner(owner)
        result=self.app.enqueue(team_owner,{'kind':'crew-chat','crewRole':0,'prompt':'Hello'})
        self.assertTrue(result['id'])
        self.app.runtime_status=lambda: {'ready':True,'teamReady':False}
        with self.assertRaises(Problem):self.app.enqueue(team_owner,{'kind':'crew-chat','crewRole':0,'prompt':'Hello'})

    def test_role_matching_does_not_capture_personal_agents(self):
        self.assertIsNone(team.model_for('bac-'+'a'*24))
        self.assertIsNone(team.model_for('bac-'+'a'*24+'-r99'))
        self.assertEqual(team.model_for(self.research),'bac-team/'+team.MODELS[1])
