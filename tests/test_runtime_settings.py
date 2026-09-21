import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch,MagicMock
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parent)]
import runtime_settings as s
import agent_runtime as r
from studio import Studio,Problem
from test_studio import Adapter
from serve import Handler

class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.env=patch.dict(os.environ,{'BAC_DATA_DIR':self.temp.name});self.env.start();self.addCleanup(self.env.stop)
        self.studio=Studio(Path(self.temp.name)/'studio',Adapter(),start_worker=False)
    def data(self,provider='nvidia',key='test-not-a-real-key'):
        return {'provider':provider,'apiKey':key,'model':'test-model','baseUrl':s.PROVIDERS[provider]['baseUrl'],'event':{'city':'Boston','region':'Americas','language':'English','venue':'Example hall'}}
    def test_event_can_save_without_model_and_region_is_optional(self):
        result=s.save(self.studio,{'section':'event','event':{'city':'Boston','language':'English','region':'','venue':''}})
        self.assertEqual(result['event']['region'],'')
        self.assertEqual(result['profiles'],{})
        self.assertFalse(r.config_path().exists())
        import event_planner
        brief,capacity=event_planner.plan({'region':'','city':'Boston'})
        self.assertEqual(brief['region'],'')
        self.assertGreater(capacity['boothCount'],0)

    def test_switch_updates_every_agent_without_changing_tools_and_masks_keys(self):
        config=r.initial_config();config['agents']['entries']['bac-test']={'model':r.MODEL,'tools':{'deny':['exec']},'sandbox':{'mode':'off'}};r.save_config(config)
        for provider in s.PROVIDERS:
            result=s.save(self.studio,self.data(provider))
            self.assertNotIn('test-not-a-real-key',json.dumps(result))
            config=json.loads(r.config_path().read_text());entry=config['agents']['entries']['bac-test']
            self.assertEqual(entry['model'],'bac-'+provider+'/test-model')
            self.assertEqual(entry['modelPolicy']['allow'],[entry['model']])
            self.assertEqual(entry['tools'],{'deny':['exec']})
            self.assertEqual(config['models']['providers']['bac-'+provider]['api'],s.PROVIDERS[provider]['api'])
        self.assertEqual(s.event()['city'],'Boston')
        self.assertEqual(s.path().stat().st_mode&0o777,0o600)
        self.assertEqual(r.config_path().stat().st_mode&0o777,0o600)
    def test_blank_key_retains_only_same_provider_and_destination(self):
        s.save(self.studio,self.data())
        self.assertEqual(s.validate(self.data(key=''))[1]['apiKey'],'test-not-a-real-key')
        with self.assertRaises(Problem):s.validate(self.data('openai',key=''))
        changed=self.data(key='');changed['baseUrl']='https://inference.nvidia.com/v1'
        with self.assertRaises(Problem):s.validate(changed)
        for endpoint in ['https://evil.example/v1','https://api.openai.com@evil.example/v1','https://api.openai.com/v1?x=1']:
            d=self.data('openai');d['baseUrl']=endpoint
            with self.assertRaises(Problem):s.validate(d)
    def test_pending_work_blocks_global_switch(self):
        owner=self.studio.session()[0]['id'];self.studio.enqueue(owner,{'kind':'crew','preset':True,'brief':{'schema':2}})
        with self.assertRaises(Problem):s.save(self.studio,self.data())
        self.assertFalse(s.path().exists())
    def test_connect_bypasses_failed_badge_cache_and_seeds_verified_status(self):
        data=self.data();s.save(self.studio,data)
        provider,profile=s.validate(data)
        s._availability=(s.availability_signature(provider,profile),time.monotonic(),False)
        with patch.object(s,'request',return_value={'data':[{'id':'test-model'}]}) as request:
            s.save(self.studio,{**data,'verifyConnection':True})
            self.assertTrue(s.model_available())
        self.assertEqual(request.call_count,1)
        self.assertEqual(request.call_args.kwargs['timeout'],25)

    def test_failed_verification_preserves_previous_settings_and_credential(self):
        s.save(self.studio,self.data())
        before=s.path().read_bytes();config=r.config_path().read_bytes()
        for result in [{'data':[]},{'data':'invalid'},[]]:
            with self.subTest(result=result),patch.object(s,'request',return_value=result):
                with self.assertRaises(Problem):s.save(self.studio,{**self.data(key='replacement-key'),'verifyConnection':True})
            self.assertEqual(s.path().read_bytes(),before);self.assertEqual(r.config_path().read_bytes(),config)
            self.assertEqual(s.validate(self.data(key=''))[1]['apiKey'],'test-not-a-real-key')
        with patch.object(s,'request',side_effect=Problem('Authentication failed (HTTP 401).',502)):
            with self.assertRaisesRegex(Problem,'HTTP 401'):s.save(self.studio,{**self.data(),'verifyConnection':True})

    def test_slow_old_probe_cannot_replace_successful_connect(self):
        s.save(self.studio,self.data());provider,profile=s.validate(self.data());signature=s.availability_signature(provider,profile)
        s._availability=(signature,time.monotonic()-61,False)
        def old_probe(*args,**kwargs):
            s._availability=(signature,time.monotonic(),True)
            raise TimeoutError()
        with patch.object(s,'request',side_effect=old_probe):self.assertTrue(s.model_available())
        self.assertTrue(s._availability[2])

    def test_transient_failure_is_rechecked_after_five_seconds(self):
        s.save(self.studio,self.data());provider,profile=s.validate(self.data())
        s._availability=(s.availability_signature(provider,profile),time.monotonic()-6,False)
        with patch.object(s,'request',return_value={'data':[{'id':'test-model'}]}) as request:self.assertTrue(s.model_available())
        request.assert_called_once()
    def test_native_auth_headers_and_model_discovery(self):
        response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps({'data':[{'id':'real-provider-id','display_name':'Provider model'}]}).encode()
        opener=MagicMock();opener.open.return_value=response
        for provider in ['nvidia','openai','anthropic']:
            with patch('urllib.request.build_opener',return_value=opener):
                result=s.models(self.data(provider));req=opener.open.call_args.args[0]
            self.assertEqual(result['models'][0]['id'],'real-provider-id')
            if provider=='anthropic':
                self.assertEqual(req.get_header('X-api-key'),'test-not-a-real-key');self.assertIn('/v1/models',req.full_url)
            else:self.assertEqual(req.get_header('Authorization'),'Bearer test-not-a-real-key')
        self.assertIsNone(s.NoRedirect().redirect_request(None,None,None,None,None,None))
    def test_operator_is_loopback_connection_and_host(self):
        handler=object.__new__(Handler)
        for client,host,allowed in [('127.0.0.1','localhost:8080',True),('127.0.0.1','127.0.0.1:8080',True),('192.168.1.2','localhost:8080',False),('127.0.0.1','192.168.1.2:8080',False)]:
            handler.client_address=(client,10);handler.headers={'Host':host}
            self.assertEqual(handler.is_operator(),allowed)

if __name__=='__main__':unittest.main()
