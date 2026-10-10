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

    def test_config_patch_uses_stdin_and_accepts_only_acknowledged_success(self):
        result=SimpleNamespace(returncode=0,stdout='{"ok":true}',stderr='')
        with patch.object(runtime.subprocess,'run',return_value=result) as run:
            runtime.gateway_config_patch({'private':'credential'},['agents.entries'])
        self.assertNotIn('credential',' '.join(run.call_args.args[0]))
        self.assertEqual(json.loads(run.call_args.kwargs['input']),
                         {'patch':{'private':'credential'},'replacePaths':['agents.entries']})
        self.assertEqual(run.call_args.kwargs['timeout'],130)

    def test_config_patch_failure_is_sanitized_and_never_replayed(self):
        for result in [SimpleNamespace(returncode=1,stdout='private-credential',stderr='private-credential'),
                       SimpleNamespace(returncode=0,stdout='{}',stderr=''),
                       SimpleNamespace(returncode=0,stdout='invalid',stderr='')]:
            with self.subTest(result=result), patch.object(runtime.subprocess,'run',return_value=result) as run:
                with self.assertRaises(RuntimeError) as caught:runtime.gateway_config_patch({},[])
                self.assertNotIn('private-credential',str(caught.exception))
                self.assertEqual(run.call_count,1)

    def test_native_transport_failure_is_classified_without_exposing_output(self):
        binary=runtime.root()/'package/node_modules/.bin/openclaw'
        binary.parent.mkdir(parents=True); binary.touch()
        result=SimpleNamespace(returncode=1,stdout='private-credential',stderr='Gateway call failed: gateway closed (1006) private-credential')
        with patch.object(runtime.subprocess,'run',return_value=result):
            with self.assertRaises(runtime.GatewayConnectionUnavailable) as caught:runtime.cli('gateway','call','config.get')
        self.assertNotIn('private-credential',str(caught.exception))
