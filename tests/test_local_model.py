"""Host-service ownership and real HTTP readiness without a GPU."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import local_model as lm

class ModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        weights = self.root/'weights'; weights.mkdir(); (weights/'config.json').write_text('{}')
        self.model = lm.Model(self.root)
        self.model.directory.mkdir()
        self.spec = {'model_id': 'fixture/qwen', 'model_path': str(weights), 'base_url': 'http://127.0.0.1:8000/v1',
                     'context_window': 131072, 'argv': [sys.executable, '-c', 'pass'], 'env': {}, 'name': 'qwen', 'wait_seconds': 2}
        self.config = {'enabled': True, 'default_model': 'qwen', 'wait_seconds': 2,
                       'models': {'qwen': {k:v for k,v in self.spec.items() if k not in ('name','wait_seconds')}}}
        self.save_config()

    def save_config(self):
        (self.root/'local-model.json').write_text(json.dumps(self.config))

    def server(self, wrong=False, inference_failures=0, studio=False):
        calls=[]
        class H(BaseHTTPRequestHandler):
            def do_GET(h):
                calls.append(('GET',h.path))
                body = {'data':[{'id':'wrong' if wrong else 'fixture/qwen'}]}
                if h.path == '/api/session':
                    body={'csrf':'nonce','canConfigure':True}
                    h.send_response(200);h.send_header('Set-Cookie','bac_session=fixture; Path=/');h.end_headers();h.wfile.write(json.dumps(body).encode());return
                if h.path == '/api/runtime': body={'ready':True}
                h.send_response(200);h.end_headers();h.wfile.write(json.dumps(body).encode())
            def do_POST(h):
                payload=json.loads(h.rfile.read(int(h.headers['Content-Length'])))
                calls.append(('POST',h.path,payload,dict(h.headers)))
                failed=h.path == '/v1/chat/completions' and sum(c[0]=='POST' for c in calls) <= inference_failures
                h.send_response(503 if failed else 200);h.end_headers()
                h.wfile.write(json.dumps({'choices':[{'message':{'content':'OK'}}]}).encode())
            def log_message(*args): pass
        server=ThreadingHTTPServer(('127.0.0.1',0),H)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        self.spec['base_url']='http://127.0.0.1:'+str(server.server_port)+'/v1'
        self.spec['wait_seconds']=5
        self.config['wait_seconds']=5
        self.config['models']['qwen']['base_url']=self.spec['base_url'];self.save_config()
        return server,calls

    def test_external_model_is_verified_connected_and_never_stopped(self):
        _,calls=self.server(inference_failures=1)
        with patch.object(self.model,'properties',return_value={}), patch.object(lm.subprocess,'run') as run:
            self.model.start()
            self.model.stop()
            run.assert_not_called()
        self.assertGreaterEqual(sum(c[0]=='POST' for c in calls),2)
        saved=json.loads((self.model.directory/'connection.json').read_text())
        self.assertEqual(saved['model'],'fixture/qwen');self.assertEqual(saved['contextWindow'],131072)
        self.assertFalse(self.model.state_path.exists())

    def test_wrong_external_model_is_not_adopted_or_signalled(self):
        self.server(wrong=True)
        with patch.object(self.model,'properties',return_value={}), patch.object(lm.subprocess,'run') as run:
            with self.assertRaisesRegex(RuntimeError,'does not expose'):
                self.model.start()
            run.assert_not_called()

    def launch(self, fail_wait=False):
        props=[{}, {'InvocationID':'owned','ActiveState':'active'}]
        def wait(spec, managed):
            self.assertTrue(managed)
            if fail_wait:raise RuntimeError('fixture inference failure')
        with patch.object(self.model,'properties',side_effect=lambda:props.pop(0) if props else {'InvocationID':'owned','ActiveState':'active'}), \
             patch.object(self.model,'listening',return_value=False), patch.object(self.model,'wait',side_effect=wait), \
             patch.object(lm.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as run:
            if fail_wait:
                with self.assertRaisesRegex(RuntimeError,'fixture inference failure'):self.model.start()
            else:self.model.start()
        return run.call_args_list

    def test_owned_service_is_launched_and_rollback_stops_only_new_service(self):
        calls=self.launch()
        self.assertTrue(any(c.args[0][0]=='systemd-run' for c in calls))
        self.assertTrue((self.model.directory/'attempt.json').exists())
        with patch.object(self.model,'properties',return_value={'InvocationID':'owned','ActiveState':'active'}), \
             patch.object(lm.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as run:
            self.model.rollback()
            self.assertEqual(run.call_args.args[0],['systemctl','--user','stop',self.model.unit])
        self.assertFalse(self.model.state_path.exists())

    def test_failed_new_model_is_cleaned_up(self):
        calls=self.launch(fail_wait=True)
        self.assertTrue(any(c.args[0][:3]==['systemctl','--user','stop'] for c in calls))
        self.assertFalse(self.model.state_path.exists())

    def test_changed_service_identity_is_not_stopped(self):
        lm.write(self.model.state_path,{'unit':self.model.unit,'invocation_id':'old'})
        with patch.object(self.model,'properties',return_value={'InvocationID':'new','ActiveState':'active'}),patch.object(lm.subprocess,'run') as run:
            self.model.stop();run.assert_not_called()

    def test_unrecorded_or_changed_service_can_be_reused_without_ownership(self):
        _, calls = self.server()
        for receipt in ({}, {'unit': self.model.unit, 'invocation_id': 'old', 'spec': self.spec}):
            with self.subTest(receipt=bool(receipt)):
                self.model.state_path.unlink(missing_ok=True)
                if receipt: lm.write(self.model.state_path, receipt)
                with patch.object(self.model, 'properties', return_value={'InvocationID': 'new', 'ActiveState': 'active'}), \
                     patch.object(lm.subprocess, 'run') as run:
                    self.model.start()
                    self.assertEqual(self.model.state(), receipt)
                    self.assertFalse((self.model.directory/'attempt.json').exists())
                    self.model.stop()
                    run.assert_not_called()
                self.assertTrue((self.model.directory/'connection.json').exists())
        self.assertTrue(any(call[0] == 'POST' for call in calls))

    def test_unrecorded_service_wrong_model_is_rejected_without_stopping(self):
        self.server(wrong=True)
        with patch.object(self.model, 'properties', return_value={'InvocationID': 'new', 'ActiveState': 'active'}), \
             patch.object(lm.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'does not expose'):
                self.model.start()
            run.assert_not_called()
        self.assertFalse((self.model.directory/'connection.json').exists())
        self.assertFalse(self.model.state_path.exists())

    def test_unrecorded_service_not_ready_reports_recovery_without_launching(self):
        with patch.object(self.model, 'properties', return_value={'InvocationID': 'new', 'ActiveState': 'activating'}), \
             patch.object(self.model, 'probe', side_effect=OSError('not listening')), \
             patch.object(lm.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'if the model is still loading'):
                self.model.start()
            run.assert_not_called()

    def test_unrecorded_service_failed_inference_is_not_stopped(self):
        with patch.object(self.model, 'properties', return_value={'InvocationID': 'new', 'ActiveState': 'active'}), \
             patch.object(self.model, 'probe'), \
             patch.object(self.model, 'wait', side_effect=RuntimeError('inference failed')) as wait, \
             patch.object(self.model, 'stop') as stop, patch.object(lm.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'inference failed'):
                self.model.start()
            self.assertFalse(wait.call_args.args[1])
            stop.assert_not_called(); run.assert_not_called()
        self.assertFalse((self.model.directory/'connection.json').exists())

    def test_restart_with_stale_identity_refuses_before_signalling_processes(self):
        lm.write(self.model.state_path, {'unit': self.model.unit, 'invocation_id': 'old'})
        with patch.object(self.model, 'properties', return_value={'InvocationID': 'new', 'ActiveState': 'active'}), \
             patch.object(lm.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run, \
             patch.object(self.model, 'stop') as stop, patch.object(self.model, 'stop_configured_process') as external, \
             patch.object(self.model, 'start') as start:
            with self.assertRaisesRegex(RuntimeError, 'before stopping anything'):
                self.model.restart()
            stop.assert_not_called(); external.assert_not_called(); start.assert_not_called()
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0], ['systemctl', '--user', 'show-environment'])

    def test_owned_start_is_reused_and_configuration_change_requires_stop(self):
        lm.write(self.model.state_path,{'unit':self.model.unit,'invocation_id':'owned','spec':self.spec})
        with patch.object(self.model,'properties',return_value={'InvocationID':'owned','ActiveState':'active'}),patch.object(self.model,'wait') as wait,patch.object(lm.subprocess,'run') as run:
            self.model.start();wait.assert_called_once();run.assert_not_called()
            self.config['models']['qwen']['context_window']=32768;self.save_config()
            with self.assertRaisesRegex(RuntimeError,'before switching'):self.model.start()

    def test_readiness_timeout_and_dead_service_fail(self):
        spec={**self.spec,'wait_seconds':0.01}
        with patch.object(self.model,'probe',side_effect=OSError('not ready')):
            with self.assertRaisesRegex(RuntimeError,'timed out'):self.model.wait(spec)
        with patch.object(self.model,'properties',return_value={'ActiveState':'failed'}):
            with self.assertRaisesRegex(RuntimeError,'exited'):self.model.wait(self.spec,True)

    def test_connection_uses_normal_session_csrf_and_preserves_event_settings(self):
        server,calls=self.server(studio=True)
        lm.write(self.model.directory/'connection.json',{'provider':'local','baseUrl':self.spec['base_url'],
            'model':'fixture/qwen','contextWindow':131072,'apiKey':''})
        self.model.connect('http://127.0.0.1:'+str(server.server_port))
        post=next(c for c in calls if c[:2]==('POST','/api/settings'))
        self.assertEqual(post[2]['section'],'model');self.assertTrue(post[2]['verifyConnection'])
        self.assertNotIn('event',post[2]);self.assertEqual(post[3]['X-Bac-Csrf'],'nonce')
        self.assertIn('bac_session=fixture',post[3]['Cookie'])

    def test_restart_stops_owned_service_then_starts_and_waits(self):
        lm.write(self.model.state_path,{'unit':self.model.unit,'invocation_id':'owned'})
        with patch.object(self.model,'properties',return_value={'InvocationID':'owned','ActiveState':'active'}), \
             patch.object(lm.subprocess,'run',return_value=subprocess.CompletedProcess([],0)), \
             patch.object(self.model,'stop') as stop,patch.object(self.model,'start') as start, \
             patch.object(self.model,'commit') as commit,patch.object(self.model,'listening',return_value=False):
            self.model.restart()
            stop.assert_called_once();start.assert_called_once_with('qwen');commit.assert_called_once()

    def test_restart_never_kills_an_unmatched_listener(self):
        with patch.object(self.model,'process_matches',return_value=False), \
             patch.object(self.model,'listening',return_value=True),patch.object(lm.signal,'pidfd_send_signal',create=True) as signal, patch.object(lm.os,'pidfd_open',create=True), patch.object(Path,'iterdir',return_value=iter([Path('/proc/123')])):
            with self.assertRaisesRegex(RuntimeError,'Nothing was killed'):
                self.model.stop_configured_process(self.spec)
            signal.assert_not_called()

    def test_restart_validates_installation_before_stopping(self):
        self.config['models']['qwen']['argv']=['/missing/vllm'];self.save_config()
        with patch.object(self.model,'stop') as stop,patch.object(self.model,'stop_configured_process') as external:
            with self.assertRaisesRegex(RuntimeError,'Nothing was stopped'):self.model.restart()
            stop.assert_not_called();external.assert_not_called()

    def test_missing_installation_names_required_paths_and_recovery(self):
        spec={**self.spec,'argv':['/missing/build-a-claw/runtime/restored/vllm/bin/vllm'],
              'model_path':'/missing/build-a-claw/models/qwen'}
        with self.assertRaises(RuntimeError) as caught:self.model.require_installation(spec)
        message=str(caught.exception)
        self.assertIn(spec['argv'][0],message);self.assertIn(spec['model_path'],message)
        self.assertIn('local-model.json',message);self.assertIn('./bac start',message)
        self.assertIn('Nothing was stopped',message)

    def test_missing_configuration_explains_installation_requirement(self):
        (self.root/'local-model.json').unlink()
        with self.assertRaisesRegex(RuntimeError,'build-a-claw installation'):
            self.model.configuration('qwen')

    def parent_installation(self):
        parent = self.root / 'build-a-claw'
        studio = parent / 'ai-studio'
        studio.mkdir(parents=True)
        source = {k: v for k, v in self.spec.items() if k not in ('name', 'wait_seconds', 'model_path')}
        source.update(path='models/qwen', base_url='http://127.0.0.1:8000',
                      argv=[sys.executable, 'serve', '{model_path}', '--served-model-name', '{model_id}'])
        (parent / 'config.json').write_text(json.dumps({'models': {'qwen': source}}))
        return lm.Model(studio), parent

    def test_explicit_model_uses_adjacent_installation(self):
        model, parent = self.parent_installation()
        spec = model.configuration('qwen')
        self.assertEqual(spec['model_path'], str((parent / 'models/qwen').resolve()))
        self.assertEqual(spec['base_url'], 'http://127.0.0.1:8000/v1')
        self.assertEqual(spec['argv'][2], spec['model_path'])
        self.assertEqual(spec['argv'][-1], spec['model_id'])
        self.assertFalse((model.root / 'local-model.json').exists())
        self.assertIsNone(model.configuration())

    def test_local_configuration_overrides_parent_installation(self):
        model, _ = self.parent_installation()
        (model.root / 'local-model.json').write_text(json.dumps(self.config))
        self.assertEqual(model.configuration('qwen')['model_path'], self.spec['model_path'])

    def test_unconfigured_parent_model_has_clear_error(self):
        model, _ = self.parent_installation()
        with self.assertRaisesRegex(RuntimeError, 'not configured in build-a-claw: gemma'):
            model.configuration('gemma')

if __name__=='__main__':unittest.main()
