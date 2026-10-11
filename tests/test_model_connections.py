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
        for name, empty in [('_checks', {}), ('_pending', set()), ('_discovered', {})]:
            cache = patch.object(connections, name, empty)
            cache.start(); self.addCleanup(cache.stop)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        env=patch.dict(os.environ,{'BAC_DATA_DIR':self.temp.name});env.start();self.addCleanup(env.stop)
        # Connection fixtures must not discover a real host model in the background.
        background = patch.object(connections, 'threading')
        background.start(); self.addCleanup(background.stop)
        self.app=Studio(Path(self.temp.name)/'studio',Adapter(),start_worker=False)
        self.owner=self.app.session()[0]['id']
        self.lease='connections-'+self.temp.name
        self.addCleanup(session_secrets.release,self.lease)

    def connect(self,source='local',provider='local'):
        data={'source':source,'provider':provider,'model':'test-model','baseUrl':settings.PROVIDERS[provider]['baseUrl'],'contextWindow':32768,'_credentialSession':self.lease}
        if source=='api':data['apiKey']='fixture-secret'
        with patch.object(settings,'request',return_value={'data':[{'id':'test-model'}]}):return connections.configure(self.app,data)

    def test_upgrade_keeps_the_previously_selected_provider(self):
        for provider in settings.PROVIDERS:
            with self.subTest(provider=provider):
                connections.path().unlink(missing_ok=True)
                settings.persist({'provider':provider,'profiles':{provider:{'model':'previous-model','contextWindow':65536}}})
                connections.initialize()
                saved=connections.read()
                self.assertEqual(saved['lounge'],'local' if provider=='local' else 'api')
                if provider!='local':self.assertEqual(saved['apiProvider'],provider)
                self.assertEqual(settings.read()['profiles'][provider]['contextWindow'],65536)

    def test_initialize_preserves_current_preferences_and_fresh_defaults(self):
        connections.initialize()
        self.assertEqual(connections.read(),{'apiProvider':'nvidia','lounge':'auto','disabled':[]})
        existing={'apiProvider':'anthropic','lounge':'api','disabled':['local']}
        connections.persist(existing)
        settings.persist({'provider':'local','profiles':{'local':{'model':'old-model'}}})
        connections.initialize()
        self.assertEqual(connections.read(),existing)

    def test_output_budget_reserves_input_across_connection_paths(self):
        for context, expected in [(8192,4096),(16384,8192),(32768,16384),(131072,16384)]:
            profile={'model':'test-model','baseUrl':'http://127.0.0.1:8000/v1','apiKey':'','contextWindow':context}
            for provider in settings.PROVIDERS:
                native=connections.native(dict(profile,_provider=provider))
                self.assertEqual(native['models'][0]['maxTokens'],expected)
            config={'agents':{'defaults':{},'entries':{}}}
            settings.apply_to_config(config,'local',profile)
            self.assertEqual(config['models']['providers']['bac-local']['models'][0]['maxTokens'],expected)
            team_models.apply(config,local=profile,agent_id='bac-0123456789abcdef01234567-r0')
            for model in config['models']['providers']['bac-team']['models']:
                self.assertEqual(model['maxTokens'],16384)
            local=team_models.local_provider('bac-0123456789abcdef01234567-r0')
            self.assertEqual(config['models']['providers'][local]['models'][0]['maxTokens'],expected)

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

    def test_host_key_runs_mixed_skill_heartbeat_without_legacy_session_key(self):
        from test_tech_radar import RadarAdapter
        import time
        self.app.adapter = RadarAdapter()
        settings.persist({'provider':'nvidia','profiles':{'nvidia':{
            'model':'test-model','baseUrl':settings.PROVIDERS['nvidia']['baseUrl'],'contextWindow':32768}}})
        team_models.save_connection('fixture-host-key',[])
        connections.persist(connections.read())
        with patch.object(settings,'request',return_value={'data':[{'id':'test-model'}]}):
            connections.probe('api',connections.profile('api'))
        self.assertFalse(settings.model_available())
        self.assertEqual(connections.public()['loungeSource'],'api')
        profile=self.app.onboard(self.owner,{'name':'Jinny','skills':['radar','weather'],'model':'api/nvidia/test-model'})
        self.app.execute(self.app.next_job())
        self.app.heartbeat.presence(self.owner,'fixture-tab')
        with self.app.db() as db:
            db.execute("UPDATE jobs SET created=? WHERE kind='prepare-agent'",(time.time()-30,))
        self.app.heartbeat.tick()
        self.assertTrue(self.app.adapter.cadence[profile['id']])
        self.assertEqual(self.app.heartbeat.status(self.owner,profile)['state'],'watching')

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

    def test_model_change_and_search_keep_session_key_over_host_key(self):
        team_models.save_connection('fixture-old-host',[],source='api.cfg')
        self.connect('api','nvidia')
        request={'source':'api','provider':'nvidia','model':'test-model','baseUrl':settings.PROVIDERS['nvidia']['baseUrl'],'_credentialSession':self.lease}
        with patch.object(settings,'request',return_value={'data':[{'id':'test-model'}]}) as call:
            connections.models(request)
            self.assertEqual(call.call_args.args[1]['apiKey'],'fixture-secret')
            connections.configure(self.app,request)
            self.assertEqual(call.call_args.args[1]['apiKey'],'fixture-secret')
        self.assertEqual(connections.profile('api')['_keySource'],'session')
        self.assertEqual(team_models.credentials()['apiKey'],'fixture-old-host')

    def test_credential_origin_and_no_cross_endpoint_reuse(self):
        team_models.save_connection('fixture-imported',[],source='api.cfg')
        self.assertEqual(connections.profile('api')['_keySource'],'api.cfg')
        team_models.save_connection('fixture-imported',[])
        self.assertEqual(team_models.saved_connection()['source'],'api.cfg')
        team_models.save_connection('fixture-replacement',[])
        self.assertEqual(connections.profile('api')['_keySource'],'host')
        request={'provider':'nvidia','baseUrl':'https://untrusted.example/v1'}
        self.assertNotIn('apiKey',connections.with_nvidia_key(request))
        with patch.object(settings,'request') as call:
            with self.assertRaises(Problem):connections.models(request)
            call.assert_not_called()

    def test_session_catalog_drives_per_agent_selection_and_runtime(self):
        self.connect('api','nvidia')
        owner=self.app.crew_owner(self.owner,'plan')
        selected=team_models.select(self.app,owner,{'role':0,'model':'test-model'})
        self.assertEqual(selected['teamSelections'][0]['id'],'test-model')
        self.assertEqual(self.app.runtime_status()['teamModels'][0]['id'],'test-model')
        member={'id':'bac-'+'a'*24+'-r0','_teamModel':'test-model'}
        connections.prepare(self.app,member)
        self.assertEqual(member['_connectionConfig']['models'][0]['id'],'test-model')
        with self.assertRaises(Problem):team_models.select(self.app,owner,{'role':0,'model':'not-offered'})
        member['_teamModel']='not-offered'
        with self.assertRaisesRegex(Problem,'selected model is unavailable'):connections.prepare(self.app,member)


class LocalDiscoveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        env = patch.dict(os.environ, {'BAC_DATA_DIR':temp.name})
        env.start(); self.addCleanup(env.stop)
        for name, empty in [('_checks', {}), ('_pending', set()), ('_discovered', {})]:
            cache = patch.object(connections, name, empty)
            cache.start(); self.addCleanup(cache.stop)
        connections.initialize()
        background = patch.object(connections, 'threading')
        self.thread = background.start().Thread; self.addCleanup(background.stop)

    def probe(self, rows):
        with patch.object(settings, 'request', return_value={'data':rows}) as request:
            state = connections.probe('local', connections.profile('local'))
        self.assertEqual(request.call_args.args[2], '/models')
        return state

    def test_running_vllm_discovered_without_saved_profile_or_launch_config(self):
        self.assertFalse(connections.status('local')['ready'])
        self.thread.assert_called_once()
        self.probe([{'id':'nvidia/test-model','owned_by':'vllm','max_model_len':262144}])
        state = connections.status('local')
        self.assertTrue(state['ready'])
        self.assertEqual(state['model'], 'nvidia/test-model')
        self.assertEqual(state['contextWindow'], 32768)
        self.assertEqual(connections.resolve('local', 'lounge')[1]['model'], 'nvidia/test-model')
        self.assertNotIn('local', settings.read().get('profiles', {}))

    def test_late_start_rechecks_and_respects_server_context(self):
        with patch.object(settings, 'request', side_effect=OSError('not listening')):
            self.assertFalse(connections.probe('local', connections.profile('local'))['ready'])
        connections.status('local', refresh=True)
        self.thread.assert_called_once()
        self.probe([{'id':'small-model','max_model_len':16384}])
        self.assertEqual(connections.status('local')['contextWindow'], 16384)
        self.assertTrue(connections.status('local')['ready'])

    def test_model_replacement_refreshes_detected_profile(self):
        self.probe([{'id':'old-model'}])
        self.probe([{'id':'new-model'}])
        self.assertEqual(connections.status('local')['model'], 'new-model')
        self.assertTrue(connections.status('local')['ready'])

    def test_ambiguous_empty_and_too_small_catalogs_do_not_connect(self):
        for rows in ([], [{'id':'one'},{'id':'two'}], [{'id':'tiny','max_model_len':4096}]):
            self.probe([{'id':'previous'}])
            self.assertFalse(self.probe(rows)['ready'])
            self.assertFalse(connections.status('local')['ready'])
            self.assertFalse(connections.profile('local').get('model'))

    def test_explicit_model_and_disabled_connection_are_preserved(self):
        settings.persist({'provider':'local','profiles':{'local':{'model':'chosen','baseUrl':'http://127.0.0.1:8000/v1','contextWindow':32768}}})
        self.assertFalse(self.probe([{'id':'different'}])['ready'])
        self.assertEqual(connections.profile('local')['model'], 'chosen')
        settings.persist({'profiles':{}})
        connections.persist({**connections.read(), 'disabled':['local']})
        self.assertEqual(connections.status('local')['message'], 'Disabled')
        self.thread.assert_not_called()

    def test_queued_discovery_cannot_assign_old_model_to_new_endpoint(self):
        stale = connections.profile('local')
        connections._pending.add(connections.signature(stale))
        settings.persist({'profiles':{'local':{'baseUrl':'http://127.0.0.1:9000/v1','contextWindow':32768}}})
        with patch.object(settings, 'request') as request:
            self.assertFalse(connections.probe('local', stale)['ready'])
            request.assert_not_called()
        self.assertNotIn(connections.signature(stale), connections._pending)
        self.assertFalse(connections.profile('local').get('model'))
        self.probe([{'id':'replacement-model'}])
        self.assertEqual(connections.profile('local')['model'], 'replacement-model')
        self.assertEqual(connections.profile('local')['baseUrl'], 'http://127.0.0.1:9000/v1')

    def test_inflight_discovery_cannot_change_new_endpoint(self):
        stale = connections.profile('local')
        def response(*args, **kwargs):
            settings.persist({'profiles':{'local':{'baseUrl':'http://127.0.0.1:9000/v1','contextWindow':32768}}})
            return {'data':[{'id':'old-model'}]}
        with patch.object(settings, 'request', side_effect=response):
            connections.probe('local', stale)
        self.assertFalse(connections.profile('local').get('model'))
        self.assertFalse(connections.status('local')['ready'])
