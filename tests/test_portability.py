"""Portable host paths and real HTTP protocol checks; no model downloads or keys."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts'), str(Path(__file__).resolve().parent)]
import agent_runtime as runtime
import manage
import ops_common as common
import ops_deploy as deploy
import ops_llm as llm
import ops_runtime
import runtime_settings as settings
import session_secrets as vault
from studio import Studio
from test_studio import Adapter


class PortabilityTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.home = Path(folder.name)
        env = patch.dict(os.environ, {'BAC_DATA_DIR': str(self.home)})
        env.start(); self.addCleanup(env.stop)
        self.studio = Studio(self.home / 'studio', Adapter(), start_worker=False)

    def server(self, handler):
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        return 'http://127.0.0.1:%s/v1' % server.server_port

    def test_local_model_discovery_and_stream_bypass_environment_proxy(self):
        calls = []
        class Upstream(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                calls.append((self.path, self.headers.get('Authorization')))
                self.send_response(200); self.end_headers()
                self.wfile.write(b'{"data":[{"id":"local-model:latest"}]}')
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                calls.append((self.path, self.headers.get('Authorization'), payload))
                self.send_response(200); self.send_header('Content-Type', 'text/event-stream'); self.end_headers()
                self.wfile.write(b'data: {"choices":[{"delta":{"content":"Local reply"}}]}\n\ndata: [DONE]\n\n')
        base = self.server(Upstream)
        profile = {'provider':'local', 'baseUrl':base, 'model':'local-model:latest', 'apiKey':'', 'contextWindow':32768}
        # A deterministic rejecting proxy, even on platforms that exempt localhost.
        with patch.dict(os.environ, {'http_proxy':'http://127.0.0.1:1', 'https_proxy':'http://127.0.0.1:1', 'no_proxy':''}), \
             patch('urllib.request.proxy_bypass', return_value=False):
            self.assertEqual(settings.models(profile)['models'][0]['id'], 'local-model:latest')
            settings.save(self.studio, {**profile, 'verifyConnection':True})
            config = common.read_json(runtime.config_path())['models']['providers']['bac-local']
            self.assertEqual(config['baseUrl'], base)
            self.assertEqual(config['api'], 'openai-completions')
            self.assertEqual(config['apiKey'], 'local-only')
            settings.save(self.studio, {**profile, 'apiKey':'fixture-private-key', '_credentialSession':'local-wire'})
            config = common.read_json(runtime.config_path())['models']['providers']['bac-local']
            payload = {'model':'local-model:latest','stream':True,'messages':[{'role':'user','content':'Hello'}],
                       'tools':[{'type':'function','function':{'name':'read','parameters':{'type':'object'}}}]}
            request = urllib.request.Request(config['baseUrl']+'/chat/completions', data=json.dumps(payload).encode(), headers={'Authorization':'Bearer session-only'})
            direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with direct.open(request, timeout=5) as response:
                self.assertIn(b'Local reply', response.read())
            self.assertEqual(calls[-1], ('/v1/chat/completions','Bearer fixture-private-key',payload))
        vault.release('local-wire')

    def test_proxy_preserves_provider_failure_without_leaking_key(self):
        class Upstream(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(429); self.end_headers()
                self.wfile.write(b'{"error":{"message":"Busy; key=fixture-private-key. Try again later."}}')
        base = self.server(Upstream)
        settings.save(self.studio, {'provider':'local','baseUrl':base,'model':'fixture','apiKey':'fixture-private-key','_credentialSession':'error-wire'})
        proxy = common.read_json(runtime.config_path())['models']['providers']['bac-local']['baseUrl']
        req = urllib.request.Request(proxy+'/chat/completions', data=b'{}', headers={'Authorization':'Bearer session-only'})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=5)
        error = caught.exception
        self.addCleanup(error.close)
        self.assertEqual(error.code, 429)
        message = error.read().decode()
        self.assertIn('HTTP 429', message); self.assertIn('Try again later', message)
        self.assertNotIn('fixture-private-key', message)
        self.assertNotIn('expired', message)
        vault.release('error-wire')

    def test_external_start_never_restarts_previous_managed_model(self):
        common.write_json(self.home/'llm.json', {'profile':'qwen'})
        with patch.object(deploy,'validate_start'), patch.object(runtime,'gateway'), \
             patch.object(ops_runtime,'require_installed'), patch.object(ops_runtime,'start'), \
             patch.object(ops_runtime,'check'), patch.object(deploy,'start'), \
             patch.object(llm,'start') as model, patch.object(llm,'check') as check:
            manage.start_stack(SimpleNamespace(model='external',wait=0,host=None,port=None))
        model.assert_not_called(); check.assert_not_called()
        self.assertEqual(common.read_json(self.home/'llm.json'), {'profile':'qwen'})

    def test_setup_without_systemd_still_installs_for_foreground_use(self):
        with patch.object(ops_runtime,'setup') as install, patch.object(common,'systemd_available',return_value=False), \
             patch.object(common,'require_systemd',side_effect=AssertionError('Setup must not require services')):
            manage.setup_stack()
        install.assert_called_once()

    def prepare_runtime_files(self):
        binary = runtime.root()/'package/node_modules/.bin/openclaw'
        binary.parent.mkdir(parents=True); binary.touch()
        runtime.save_config(runtime.initial_config())

    def test_linux_settings_starts_the_managed_service(self):
        self.prepare_runtime_files()
        with patch.object(runtime,'gateway',side_effect=RuntimeError('Offline')), \
             patch.object(settings.sys,'platform','linux'), patch.object(common,'systemd_available',return_value=True), \
             patch.object(ops_runtime,'start') as start, patch.object(settings.subprocess,'Popen') as detached:
            self.assertTrue(settings.start_gateway()['started'])
        start.assert_called_once(); detached.assert_not_called()

    def test_overlapping_foreground_starts_reuse_pending_process(self):
        self.prepare_runtime_files()
        process = SimpleNamespace(poll=lambda:None)
        with patch.object(runtime,'gateway',side_effect=RuntimeError('Starting')), \
             patch.object(common,'systemd_available',return_value=False), patch.object(settings,'_gateway_process',None), \
             patch.object(settings.socket,'socket') as socket, patch.object(settings.subprocess,'Popen',return_value=process) as spawn:
            socket.return_value.__enter__.return_value.connect_ex.return_value = 111
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda _:settings.start_gateway(), range(4)))
            self.assertTrue(all(item['started'] for item in results))
            spawn.assert_called_once()

    def test_service_environment_keeps_paths_and_excludes_credentials(self):
        with patch.dict(os.environ, {'PATH':'/opt/local/bin:/usr/bin', 'XDG_CONFIG_HOME':'/tmp/custom-config',
                                    'OPENAI_API_KEY':'fixture-secret', 'HTTP_PROXY':'http://user:secret@proxy'}):
            env = common.service_environment()
        self.assertEqual(env['PATH'], '/opt/local/bin:/usr/bin')
        self.assertEqual(env['BAC_DATA_DIR'], str(self.home))
        self.assertEqual(env['XDG_CONFIG_HOME'], '/tmp/custom-config')
        self.assertNotIn('OPENAI_API_KEY',env); self.assertNotIn('HTTP_PROXY',env)

    def test_concurrent_status_polls_share_one_runtime_probe(self):
        entered = threading.Event(); release = threading.Event()
        def probe():
            entered.set(); release.wait(3)
            return {'ready':True}
        with patch.object(self.studio.adapter,'status',side_effect=probe) as status, ThreadPoolExecutor(max_workers=6) as pool:
            results = [pool.submit(self.studio.runtime_status) for _ in range(6)]
            self.assertTrue(entered.wait(2)); release.set()
            self.assertTrue(all(f.result(timeout=3)['ready'] for f in results))
        status.assert_called_once()


if __name__ == '__main__': unittest.main()
