"""Cold runtime reads may recover; model requests must never be replayed."""
import tempfile
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import agent_runtime as runtime


class RuntimeStartupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.clock = 0
        self.agent = 'bac-' + 'a'*24
        self.posts = 0
        for name, value in [('root', lambda: Path(self.tmp.name)),
                            ('observed_activity', lambda *a: {'calls':[]}),
                            ('model_endpoint', lambda *a: None)]:
            p = patch.object(runtime, name, side_effect=value); p.start(); self.addCleanup(p.stop)
        for name, value in [('agent_runtime.time.monotonic', lambda: self.clock),
                            ('agent_runtime.time.sleep', self.advance),
                            ('user_location.context', lambda: ''),
                            ('telemetry.measure', lambda *a, **k: {})]:
            p = patch(name, side_effect=value); p.start(); self.addCleanup(p.stop)
        p = patch.dict(runtime._expected_identity, {self.agent:'current'}, clear=True)
        p.start(); self.addCleanup(p.stop)

    def advance(self, seconds):
        self.clock += seconds

    def gateway(self, path, payload=None, **kwargs):
        if payload is not None:
            self.posts += 1
            return {'choices':[{'message':{'content':'Done'}}]}
        return {'data':[{'id':'openclaw/'+self.agent}]}

    def identity(self, **kwargs):
        return {'agents':[{'id':self.agent,'identity':{'theme':'current'}}]}

    def test_cold_identity_read_recovers_after_more_than_twenty_seconds(self):
        def discovery(**kwargs):
            if self.clock < 25:
                self.advance(13)
                raise RuntimeError('Gateway still initializing')
            return self.identity()
        with patch.object(runtime,'live_agents',side_effect=discovery), patch.object(runtime,'gateway',side_effect=self.gateway):
            self.assertEqual(runtime.respond(self.agent,'test','hello'), 'Done')
        self.assertEqual(self.posts, 1)

    def test_transient_model_discovery_timeout_recovers_without_replaying_post(self):
        def gateway(path, payload=None, **kwargs):
            if payload is None and self.clock < 5:
                self.advance(3)
                raise runtime.GatewayError('Discovery timed out', 'timeout')
            return self.gateway(path, payload, **kwargs)
        with patch.object(runtime,'live_agents',side_effect=self.identity), patch.object(runtime,'gateway',side_effect=gateway):
            self.assertEqual(runtime.respond(self.agent,'test','hello'), 'Done')
        self.assertEqual(self.posts, 1)

    def test_caller_deadline_stops_discovery_before_any_model_request(self):
        def discovery(**kwargs):
            self.advance(min(2, kwargs.get('timeout',2)))
            return {'agents':[]}
        with patch.object(runtime,'live_agents',side_effect=discovery), patch.object(runtime,'gateway',side_effect=self.gateway):
            with self.assertRaises(RuntimeError):runtime.respond(self.agent,'test','hello',timeout=5)
        self.assertLessEqual(self.clock, 5)
        self.assertEqual(self.posts, 0)

    def test_failed_model_request_is_not_replayed(self):
        def gateway(path,payload=None,**kwargs):
            if payload is not None:
                self.posts += 1
                raise runtime.GatewayError('Request timed out', 'timeout')
            return self.gateway(path,payload,**kwargs)
        with patch.object(runtime,'live_agents',side_effect=self.identity), patch.object(runtime,'gateway',side_effect=gateway):
            with self.assertRaises(RuntimeError):runtime.respond(self.agent,'test','hello')
        self.assertEqual(self.posts,1)

    def test_permanently_unready_gateway_has_bounded_wait(self):
        with patch.object(runtime,'live_agents',return_value={'agents':[]}), patch.object(runtime,'gateway',side_effect=self.gateway):
            with self.assertRaises(RuntimeError):runtime.respond(self.agent,'test','hello')
        self.assertLessEqual(self.clock,60)
        self.assertEqual(self.posts,0)

    def test_slow_configuration_rpc_uses_explicit_timeout_without_replaying_write(self):
        writes=[]
        def cli(*args):
            # Model the native CLI's independent, much shorter default timeout.
            if '--timeout' not in args or int(args[args.index('--timeout')+1]) < 30000:
                raise RuntimeError('RPC timed out while gateway initialized')
            if args[2]=='config.get':return json.dumps({'hash':'current'})
            writes.append(json.loads(args[args.index('--params')+1]))
            return json.dumps({'ok':True})
        with patch.object(runtime,'cli',side_effect=cli):runtime.gateway_config_patch({'agents':{}},[])
        self.assertEqual(len(writes),1)
        self.assertEqual(writes[0]['baseHash'],'current')
        with patch.object(runtime,'cli',side_effect=['{"hash":"current"}',RuntimeError('Uncertain write')]) as call:
            with self.assertRaises(RuntimeError):runtime.gateway_config_patch({'agents':{}},[])
        self.assertEqual(call.call_count,2)

    def test_config_read_recovers_from_interrupted_connection_but_write_never_replays(self):
        with patch.object(runtime,'cli',side_effect=[runtime.GatewayConnectionUnavailable('temporary'), '{"hash":"current"}', '{"ok":true}']) as call:
            runtime.gateway_config_patch({'agents':{}},[])
        self.assertEqual([c.args[2] for c in call.call_args_list], ['config.get','config.get','config.patch'])
        with patch.object(runtime,'cli',side_effect=['{"hash":"current"}',runtime.GatewayConnectionUnavailable('uncertain')]) as call:
            with self.assertRaises(RuntimeError):runtime.gateway_config_patch({'agents':{}},[])
        self.assertEqual(call.call_count,2)

    def test_native_transport_failure_is_classified_without_exposing_output(self):
        binary=runtime.root()/'package/node_modules/.bin/openclaw'
        binary.parent.mkdir(parents=True); binary.touch()
        result=SimpleNamespace(returncode=1,stdout='private-credential',stderr='Gateway call failed: gateway closed (1006) private-credential')
        with patch.object(runtime.subprocess,'run',return_value=result):
            with self.assertRaises(runtime.GatewayConnectionUnavailable) as caught:runtime.cli('gateway','call','config.get')
        self.assertNotIn('private-credential',str(caught.exception))
