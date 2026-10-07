import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import model_connections as connections
import runtime_settings as settings
import team_models
import session_secrets
from studio import Studio, Problem
from test_studio import Adapter

class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        env=patch.dict(os.environ,{'BAC_DATA_DIR':self.temp.name});env.start();self.addCleanup(env.stop)
        self.app=Studio(Path(self.temp.name)/'studio',Adapter(),start_worker=False)
        self.owner=self.app.session()[0]['id']
        self.lease='connections-'+self.temp.name
        self.addCleanup(session_secrets.release,self.lease)

    def connect(self,source='local',provider='local'):
        data={'source':source,'provider':provider,'model':'test-model','baseUrl':settings.PROVIDERS[provider]['baseUrl'],'contextWindow':32768,'_credentialSession':self.lease}
        if source=='api':data['apiKey']='fixture-secret'
        with patch.object(settings,'request',return_value={'data':[{'id':'test-model'}]}):return connections.configure(self.app,data)

    def test_all_readiness_combinations(self):
        for local in (False,True):
            for api in (False,True):
                states={'local':{'ready':local},'api':{'ready':api}}
                self.assertEqual(connections.choose('auto','lounge',states),'local' if local else 'api' if api else None)
                self.assertEqual(connections.choose('auto','team',states),'api' if api else 'local' if local else None)
                self.assertEqual(connections.choose('api','lounge',states),'api' if api else 'local' if local else None)

    def test_connect_disable_and_atomic_stage_choices(self):
        self.connect();state=self.connect('api','openai')
        self.assertEqual(state['loungeSource'],'local')
        state=connections.preferences(self.app,{'lounge':'api','team':'local'},self.owner)
        self.assertEqual(state['loungeSource'],'api');self.assertEqual(state['teamConnection']['effectiveSource'],'local')
        state=connections.preferences(self.app,{'lounge':'api','disable':'api'},self.owner)
        self.assertEqual(state['loungeSource'],'local')
        state=connections.preferences(self.app,{'lounge':'api','disable':'local'},self.owner)
        self.assertIsNone(state['loungeSource']);self.assertFalse(state['teamConnection']['ready'])
        self.assertNotIn('fixture-secret',str(state))
        for file in Path(self.temp.name).rglob('*.json'):self.assertNotIn('fixture-secret',file.read_text())

    def test_provider_protocol_and_session_expiry(self):
        for provider,protocol in [('openai','openai-responses'),('anthropic','anthropic-messages')]:
            self.connect('api',provider)
            member={'id':'bac-'+'a'*24+'-r0'}
            connections.prepare(self.app,member)
            self.assertEqual(member['_connectionConfig']['api'],protocol)
            self.assertNotIn('fixture-secret',str(member))
        session_secrets.release(self.lease)
        self.assertFalse(connections.public()['connections']['api']['ready'])

    def test_failed_connect_retains_working_profile(self):
        self.connect()
        with patch.object(settings,'request',side_effect=Problem('Endpoint unreachable')):
            with self.assertRaises(Problem):connections.configure(self.app,{'source':'api','provider':'openai','apiKey':'fixture-secret','model':'bad','contextWindow':32768})
        self.assertEqual(connections.public()['loungeSource'],'local')

    def test_busy_changes_rejected_without_probe(self):
        with patch.object(connections,'idle',side_effect=Problem('Busy')),patch.object(settings,'request') as request:
            with self.assertRaises(Problem):connections.configure(self.app,{'source':'local'})
            request.assert_not_called()

    def test_api_cfg_available_without_reentering_key(self):
        team_models.save_connection('fixture-imported',[{'id':team_models.MODELS[0]}])
        p=connections.profile('api')
        self.assertEqual(p['_credentialProvider'],'team')
        with patch.object(settings,'request',return_value={'data':[{'id':p['model']}]}) as request:
            connections.probe('api',p)
            self.assertEqual(request.call_args.args[1]['apiKey'],'fixture-imported')
        self.assertTrue(connections.public()['connections']['api']['ready'])

    def test_native_registration_pins_each_provider_for_personal_and_team(self):
        import agent_runtime as runtime
        runtime.save_config(runtime.initial_config())
        self.connect('api','anthropic')
        for agent in ('bac-'+'b'*24, 'bac-'+'c'*24+'-r0'):
            member={'id':agent,'name':'Fixture','persona':'guide','skills':['documents']}
            connections.prepare(self.app,member,'api','lounge' if agent.endswith('b') else 'team')
            with patch.object(runtime,'gateway_config_patch') as apply:
                runtime.register(agent,Path(self.temp.name)/agent,member)
            config=apply.call_args.args[0];provider=connections.provider_id(agent)
            self.assertEqual(config['models']['providers'][provider]['api'],'anthropic-messages')
            self.assertEqual(config['agents']['entries'][agent]['model'],provider+'/test-model')
            self.assertEqual(config['agents']['entries'][agent]['modelPolicy']['allow'],[provider+'/test-model'])

    def test_independent_scenarios_keep_preferences_on_reset(self):
        self.connect();self.connect('api','openai')
        event=self.app.crew_owner(self.owner,'event-brief');plan=self.app.crew_owner(self.owner,'plan')
        connections.preferences(self.app,{'team':'local'},event)
        connections.preferences(self.app,{'team':'api'},plan)
        import scenario_models
        self.assertEqual(scenario_models.connection(self.app,event)['effectiveSource'],'local')
        self.assertEqual(scenario_models.connection(self.app,plan)['effectiveSource'],'api')
        self.app.reset_crew_chats(event,reset_event=True)
        self.assertEqual(scenario_models.connection(self.app,event)['provider'],'local')
        self.assertEqual(scenario_models.connection(self.app,plan)['provider'],'api')

    def test_settings_can_save_both_scenarios_without_switching(self):
        self.connect();self.connect('api','openai')
        self.assertEqual(connections.public_for(self.app,self.owner)['scenarioPreferences'],{'event-brief':'auto','plan':'auto'})
        self.assertIsNone(self.app.existing_crew_owner(self.owner,'event-brief'))
        connections.preferences(self.app,{'lounge':'local','scenarios':{'event-brief':'local','plan':'api'}},participant=self.owner)
        self.assertEqual(connections.public_for(self.app,self.owner)['scenarioPreferences'],{'event-brief':'local','plan':'api'})
        other=self.app.session()[0]['id']
        self.assertEqual(connections.public_for(self.app,other)['scenarioPreferences'],{'event-brief':'auto','plan':'auto'})
        with self.assertRaises(Problem):connections.preferences(self.app,{'scenarios':{'unknown':'local'}},participant=self.owner)
        with patch.object(connections,'idle',side_effect=Problem('Busy')):
            with self.assertRaises(Problem):connections.preferences(self.app,{'scenarios':{'event-brief':'api','plan':'local'}},participant=self.owner)
        self.assertEqual(connections.public_for(self.app,self.owner)['scenarioPreferences'],{'event-brief':'local','plan':'api'})
