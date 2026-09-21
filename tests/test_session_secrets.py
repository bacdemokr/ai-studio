import json,os,sys,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parent)]
import session_secrets as vault
import runtime_settings as settings
import agent_runtime as runtime
from studio import Studio,Problem
from test_studio import Adapter

class SecretsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        env=patch.dict(os.environ,{'BAC_DATA_DIR':self.temp.name});env.start();self.addCleanup(env.stop)
        self.studio=Studio(Path(self.temp.name)/'studio',Adapter(),start_worker=False)
    def test_expiry_release_and_owner_isolation(self):
        vault.put('test',{'apiKey':'fixture-secret'},'one')
        self.assertFalse(vault.get('test','two'));vault.release('two');self.assertTrue(vault.get('test'))
        vault.release('one');self.assertFalse(vault.get('test'))
        with self.assertRaises(Problem):vault.put('test',{'apiKey':'fixture-secret'},'one')
        vault.put('test',{'apiKey':'fixture-secret'},'new')
        with patch.object(vault.time,'monotonic',return_value=10**15):
            vault.renew('new');self.assertFalse(vault.get('test'))
    def test_proxy_injects_key_without_persistence_and_rejects_after_close(self):
        calls=[]
        class Upstream(BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def do_POST(self):
                calls.append(self.headers.get('Authorization'));self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers();self.wfile.write(b'data: {"ok":true}\n\ndata: [DONE]\n\n')
        server=ThreadingHTTPServer(('127.0.0.1',0),Upstream);threading.Thread(target=server.serve_forever,daemon=True).start();self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        data={'provider':'local','baseUrl':f'http://127.0.0.1:{server.server_port}/v1','model':'fixture','apiKey':'fixture-secret-unique','_credentialSession':'proxy-owner'}
        settings.save(self.studio,data)
        for path in Path(self.temp.name).rglob('*'):
            if path.is_file():self.assertNotIn(b'fixture-secret-unique',path.read_bytes())
        config=json.loads(runtime.config_path().read_text());base=config['models']['providers']['bac-local']['baseUrl']
        request=urllib.request.Request(base+'/chat/completions',data=b'{}',headers={'Authorization':'Bearer session-only'})
        with urllib.request.urlopen(request) as r:self.assertIn(b'[DONE]',r.read())
        self.assertEqual(calls,['Bearer fixture-secret-unique'])
        vault.release('proxy-owner')
        with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(request)
        self.assertEqual(len(calls),1)
    def test_migration_scrubs_files_backups_and_never_loads_keys(self):
        home=Path(self.temp.name);(home/'openclaw/state').mkdir(parents=True)
        (home/'host-settings.json').write_text(json.dumps({'provider':'openai','profiles':{'openai':{'apiKey':'fixture-old-key'}}}))
        (home/'openclaw/state/openclaw.json.bak').write_text(json.dumps({'models':{'apiKey':'fixture-old-key'}}))
        (home/'openclaw/gateway.log').write_text('error fixture-old-key')
        (home/'studio/telegram.json').write_text('{"token":"fixture-old-token"}')
        vault.purge_legacy(home)
        for path in home.rglob('*'):
            if path.is_file():
                self.assertNotIn(b'fixture-old-key',path.read_bytes());self.assertNotIn(b'fixture-old-token',path.read_bytes())
        self.assertFalse(vault.get(settings.secret_key('openai')))
