"""Local server protocol fixtures, not downloaded/running Qwen model weights."""
import json,sys,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parent)]
import model_reasoning as reasoning
import model_connections as connections
import session_secrets as vault
from test_model_reasoning import Store

class LocalReasoningTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'test.sqlite');self.calls=[]
        self.direct=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def server(self,field='reasoning',stream=True,text='Published local reasoning'):
        calls=self.calls
        class Upstream(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                calls.append((self.headers.get('Authorization'),request))
                events=[{'choices':[{'delta':{field:text}}]},{'choices':[{'delta':{'content':'Final answer','tool_calls':[{'id':'read-1','function':{'name':'read'}}]}}]}]
                wire=b''.join(b'data: '+json.dumps(e).encode()+b'\n\n' for e in events)+b'data: [DONE]\n\n' if stream else json.dumps({'choices':[{'message':{field:text,'content':'Final answer'}}]}).encode()
                self.send_response(200);self.send_header('Content-Type','text/event-stream' if stream else 'application/json');self.end_headers();self.wfile.write(wire)
        s=ThreadingHTTPServer(('127.0.0.1',0),Upstream);threading.Thread(target=s.serve_forever,daemon=True).start()
        self.addCleanup(s.server_close);self.addCleanup(s.shutdown)
        return f'http://127.0.0.1:{s.server_port}/v1'
    def collect(self,base,stream=True):
        config=connections.native({'_provider':'local','model':'Qwen-fixture','baseUrl':base,'apiKey':'','contextWindow':32768})
        self.assertTrue(vault.observes(config['baseUrl']))
        self.assertFalse(config['models'][0]['reasoning'])
        original={'model':'Qwen-fixture','messages':[{'role':'user','content':'Task'}],'stream':stream,'chat_template_kwargs':{'enable_thinking':False},'tools':[{'type':'function','function':{'name':'read'}}]}
        def run():
            data={**original,'messages':[{'role':'user','content':reasoning.tag('Task')}]}
            req=urllib.request.Request(config['baseUrl']+'/chat/completions',data=json.dumps(data).encode(),headers={'Authorization':'Bearer session-only'})
            with self.direct.open(req,timeout=5) as r:return r.read()
        wire=reasoning.call(self.store,'one',5,'Local coder','Working',run)
        self.assertEqual(self.calls[-1],(None,original))
        self.assertIn(b'Final answer',wire)
        return reasoning.report(self.store,'account-a','one')['calls'][-1]
    def test_vllm_qwen_reasoning_stream_and_response(self):
        for stream in (True,False):
            with self.subTest(stream=stream):
                call=self.collect(self.server('reasoning',stream),stream)
                self.assertEqual(call['turns'][0]['sections'],[{'kind':'text','text':'Published local reasoning'}])
    def test_llamacpp_and_older_vllm_reasoning_content(self):
        for stream in (True,False):
            with self.subTest(stream=stream):
                call=self.collect(self.server('reasoning_content',stream),stream)
                self.assertEqual(call['turns'][0]['sections'],[{'kind':'text','text':'Published local reasoning'}])
    def test_keyless_routes_stay_bound_to_their_endpoints(self):
        a=self.server(text='Server A');b=self.server(text='Server B')
        route_a=vault.native_route('local',{'baseUrl':a,'apiKey':''})
        route_b=vault.native_route('local',{'baseUrl':b,'apiKey':''})
        self.assertNotEqual(route_a,route_b)
        self.assertEqual(vault.native_route('local',{'baseUrl':a,'apiKey':''}),route_a)
        self.assertEqual(self.collect(a)['turns'][0]['sections'][0]['text'],'Server A')
        self.assertEqual(self.collect(b)['turns'][0]['sections'][0]['text'],'Server B')
    def test_environment_proxy_is_bypassed_for_keyless_upstream(self):
        base=self.server()
        with patch.dict('os.environ',{'http_proxy':'http://127.0.0.1:1','https_proxy':'http://127.0.0.1:1','no_proxy':''}),patch('urllib.request.proxy_bypass',return_value=False):self.collect(base)
    def test_expired_key_is_never_downgraded_to_keyless(self):
        base=self.server();vault.native_route('local',{'baseUrl':base,'apiKey':''})
        config=vault.native_route('local',{'baseUrl':base,'apiKey':'','requiresKey':True})
        self.assertIn('/provider/local/v1',config['baseUrl'])
        req=urllib.request.Request(config['baseUrl']+'/chat/completions',data=b'{}',headers={'Authorization':'Bearer session-only'})
        with patch.object(vault,'get',return_value={}):
            with self.assertRaises(urllib.error.HTTPError) as caught:self.direct.open(req,timeout=5)
        self.assertEqual(caught.exception.code,401);caught.exception.close();self.assertEqual(self.calls,[])
    def test_unknown_route_rejected_before_upstream(self):
        base=self.server();route=vault.native_route('local',{'baseUrl':base,'apiKey':''})
        url=route['baseUrl'].split('/provider/')[0]+'/provider/local-unknown/v1/chat/completions'
        req=urllib.request.Request(url,data=b'{}',headers={'Authorization':'Bearer session-only'})
        with self.assertRaises(urllib.error.HTTPError) as caught:self.direct.open(req,timeout=5)
        caught.exception.close();self.assertEqual(self.calls,[])

if __name__=='__main__':unittest.main()
