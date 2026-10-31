import json,sqlite3,sys,tempfile,time,unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts')]
import model_reasoning as reasoning

class Store:
    def __init__(self,path):
        self.db_path=path
        with self.db() as db:
            db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,owner TEXT,status TEXT,created REAL)')
            reasoning.initialize(db)
            db.executemany('INSERT INTO jobs VALUES (?,?,?,?)',[('one','account-a','running',1),('two','account-b','done',2)])
    @contextmanager
    def db(self):
        c=sqlite3.connect(self.db_path);c.row_factory=sqlite3.Row
        try:
            with c:yield c
        finally:c.close()

class ReasoningTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'studio.sqlite')
    def capture(self,value,stream=False):
        def run():
            payload={'model':'fixture','messages':[{'role':'user','content':reasoning.tag('task')}],'tools':[{'type':'function'}]}
            cleaned,collector=reasoning.request(json.dumps(payload).encode(),'nvidia')
            self.assertEqual(json.loads(cleaned)['messages'][0]['content'],'task')
            collector.streaming=stream
            wire=b''.join(b'data: '+json.dumps(x,ensure_ascii=False).encode()+b'\r\n\r\n' for x in value)+b'data: [DONE]\r\n\r\n' if stream else json.dumps(value).encode()
            for i in range(0,len(wire),7):collector.feed(wire[i:i+7])
            collector.finish()
            live=reasoning.report(self.store,'account-a','one');self.assertTrue(live['active'])
            return 'final answer unchanged'
        self.assertEqual(reasoning.call(self.store,'one',5,'Pixel','Working',run),'final answer unchanged')
        return reasoning.report(self.store,'account-a','one')['calls'][-1]
    def test_chat_stream_split_unicode_and_tools(self):
        call=self.capture([{'choices':[{'delta':{'reasoning_content':'생각해'}}]},{'choices':[{'delta':{'reasoning_content':' 봅니다.'}}]},{'choices':[{'delta':{'content':'answer','tool_calls':[{'id':'secret-call'}]}}]}],True)
        self.assertEqual(call['turns'][0]['sections'],[{'kind':'text','text':'생각해 봅니다.'}]);self.assertNotIn('secret-call',json.dumps(call))
    def test_chat_nonstream_aliases_and_unknown_models(self):
        for field in ['reasoning_content','reasoning','reasoning_text']:
            with self.subTest(field=field):
                c=self.capture({'model':'unlisted-model','choices':[{'message':{field:'published','content':'final'}}]})
                self.assertEqual(c['turns'][0]['sections'][0]['text'],'published')
                self.assertEqual(c['turns'][0]['model'],'unlisted-model')
    def test_responses_summary_deltas_and_completed_deduplicate(self):
        item={'id':'rs1','type':'reasoning','summary':[{'type':'summary_text','text':'Public summary'}],'encrypted_content':'never-display'}
        c=self.capture([{'type':'response.reasoning_summary_text.delta','item_id':'rs1','summary_index':0,'delta':'Public '},{'type':'response.reasoning_summary_text.delta','item_id':'rs1','summary_index':0,'delta':'summary'},{'type':'response.reasoning_summary_text.done','item_id':'rs1','summary_index':0,'text':'Public summary'},{'type':'response.output_item.done','item':item},{'type':'response.completed','response':{'output':[item]}}],True)
        self.assertEqual(c['turns'][0]['sections'],[{'kind':'summary','text':'Public summary'}]);self.assertNotIn('never-display',json.dumps(c))
    def test_responses_nonstream_only_public_summary(self):
        c=self.capture({'output':[{'type':'reasoning','summary':[{'type':'summary_text','text':'Summary'}],'encrypted_content':'opaque'},{'type':'message','content':[{'type':'output_text','text':'answer'}]}]})
        self.assertEqual(c['turns'][0]['sections'],[{'kind':'summary','text':'Summary'}])
    def test_chat_wrapped_responses_items_only_public_summary(self):
        c=self.capture({'choices':[{'message':{'reasoning_items':[{'type':'reasoning','id':'r1','encrypted_content':'opaque','summary':[{'type':'summary_text','text':'Public summary'}]}]}}]})
        self.assertEqual(c['turns'][0]['sections'],[{'kind':'summary','text':'Public summary'}])
        self.assertNotIn('opaque',json.dumps(c))
    def test_anthropic_thinking_not_signature_or_redacted(self):
        c=self.capture([{'type':'content_block_start','index':0,'content_block':{'type':'thinking','thinking':''}},{'type':'content_block_delta','index':0,'delta':{'type':'thinking_delta','thinking':'Published thought'}},{'type':'content_block_delta','index':0,'delta':{'type':'signature_delta','signature':'opaque'}},{'type':'content_block_start','index':1,'content_block':{'type':'redacted_thinking','data':'opaque'}}],True)
        self.assertEqual(c['turns'][0]['sections'],[{'kind':'text','text':'Published thought'}])
    def test_reasoning_details_only_text_and_summary(self):
        c=self.capture({'choices':[{'message':{'reasoning_details':[{'type':'reasoning.encrypted','data':'opaque'},{'type':'reasoning.summary','index':1,'summary':'Visible'}]}}]})
        self.assertEqual(c['turns'][0]['sections'],[{'kind':'summary','text':'Visible'}])
    def test_no_reasoning_never_reconstructs_answer_or_think_tags(self):
        c=self.capture({'choices':[{'message':{'content':'<think>ordinary answer</think>'}}],'usage':{'reasoning_tokens':50}})
        self.assertEqual(c['turns'][0]['sections'],[])
    def test_payload_and_tool_history_unchanged(self):
        def run():
            original={'model':'deepseek','reasoning_effort':'low','stream':True,'messages':[{'role':'assistant','reasoning_content':'previous reasoning','tool_calls':[{'id':'tool'}]},{'role':'tool','content':'actual tool result','tool_call_id':'tool'},{'role':'user','content':[{'type':'text','text':'task'},{'type':'image_url','image_url':{'url':'data:image/png;base64,AA'}}]}]}
            observed=json.loads(json.dumps(original));observed['messages'][-1]['content'][0]['text']=reasoning.tag('task')
            cleaned,c=reasoning.request(json.dumps(observed).encode(),'nvidia');self.assertEqual(json.loads(cleaned),original);self.assertIsNotNone(c)
        reasoning.call(self.store,'one',5,'Pixel','Working',run)
    def test_nested_concurrent_scope_and_stale_markers(self):
        def first():
            first_marker=reasoning.tag('first')
            def second():
                raw,c=reasoning.request(json.dumps({'messages':[{'role':'user','content':reasoning.tag('second')}]}).encode(),'nvidia')
                c.feed(b'{"choices":[{"message":{"reasoning":"second only"}}]}');c.finish()
                self.assertEqual(len(reasoning.report(self.store,'account-a','one')['calls'][0]['turns']),0)
                return reasoning.tag('stale')
            stale=reasoning.call(self.store,'two',0,'Casey','Planning',second)
            _,c=reasoning.request(json.dumps({'messages':[{'role':'user','content':stale},{'role':'user','content':first_marker}]}).encode(),'nvidia')
            self.assertIsNotNone(c);c.feed(b'{"choices":[{"message":{"reasoning":"first only"}}]}');c.finish()
        reasoning.call(self.store,'one',5,'Pixel','Working',first)
        self.assertIn('first only',json.dumps(reasoning.report(self.store,'account-a','one')))
        self.assertNotIn('second only',json.dumps(reasoning.report(self.store,'account-a','one')))
    def test_unregistered_marker_not_attributed(self):
        wire=json.dumps({'messages':[{'role':'user','content':'[[bac-observe:'+'f'*32+']]\ntask'}]}).encode()
        cleaned,c=reasoning.request(wire,'nvidia');self.assertIsNone(c);self.assertEqual(json.loads(cleaned)['messages'][0]['content'],'task')
    def test_per_job_budget_and_truncation(self):
        with patch.object(reasoning,'MAX_TEXT',20),patch.object(reasoning,'MAX_JOB_TEXT',25):
            c=self.capture({'choices':[{'message':{'reasoning_content':'x'*30}}]});self.assertTrue(c['truncated']);self.assertEqual(len(c['turns'][0]['sections'][0]['text']),20)
            c=self.capture({'choices':[{'message':{'reasoning_content':'y'*30}}]});self.assertEqual(len(c['turns'][0]['sections'][0]['text']),5)
    def test_malformed_stream_does_not_break_delivery(self):
        def run():
            _,c=reasoning.request(json.dumps({'messages':[{'role':'user','content':reasoning.tag('task')}]}).encode(),'nvidia');c.streaming=True
            c.feed(b'data: broken-json\n\ndata: {"choices":[{"delta":{"reasoning_content":"good"}}]}\n\n');c.finish(False)
        reasoning.call(self.store,'one',5,'Pixel','Working',run)
        t=reasoning.report(self.store,'account-a','one')['calls'][0]['turns'][0];self.assertEqual(t['sections'][0]['text'],'good');self.assertEqual(t['status'],'interrupted')
    def test_error_restores_context_and_persists_partial(self):
        def fail():raise RuntimeError('real model error')
        with self.assertRaisesRegex(RuntimeError,'real model error'):reasoning.call(self.store,'one',0,'Casey','Planning',fail)
        self.assertFalse(reasoning.capturing());self.assertEqual(reasoning.tag('task'),'task')
        self.assertEqual(reasoning.report(self.store,'account-a','one')['calls'][0]['status'],'finished')
    def test_ownership_and_delete_cascade(self):
        self.capture({'choices':[{'message':{'reasoning':'private trace'}}]})
        from studio import Problem
        with self.assertRaises(Problem):reasoning.report(self.store,'account-b','one')
        with self.store.db() as db:db.execute("DELETE FROM jobs WHERE id='one'")
        with self.store.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM model_reasoning').fetchone()[0],0)
    def test_read_old_job_is_unavailable_not_fabricated(self):
        r=reasoning.report(self.store,'account-b','two');self.assertEqual(r['calls'],[]);self.assertFalse(r['recorded'])
    def test_no_marker_payload_passes_byte_for_byte(self):
        p=b'{  "model": "any", "messages": [] }';self.assertEqual(reasoning.request(p,'nvidia'),(p,None))

    def test_sol_summary_opt_in_preserves_effort_tools_and_explicit_options(self):
        for options in [None, {'effort':'low'}, {'summary':None}, {'summary':'concise','effort':'high'}, {'generate_summary':'concise'}, 'unsupported-shape']:
            for field in ['messages','input']:
                with self.subTest(options=options,field=field):
                    def run():
                        original={'model':'azure/openai/gpt-6.1-sol',field:[{'role':'user','content':'Task'}],
                                  'tools':[{'type':'function','name':'read'}],'stream':True,'reasoning_effort':'low'}
                        if options is not None:original['reasoning']=options
                        payload=json.loads(json.dumps(original));payload[field][0]['content']=reasoning.tag('Task')
                        raw,c=reasoning.request(json.dumps(payload).encode(),'nvidia',base_url='https://inference-api.nvidia.com/v1')
                        expected=json.loads(json.dumps(original));r=expected.setdefault('reasoning',{})
                        if isinstance(r,dict) and 'generate_summary' not in r:r.setdefault('summary','auto')
                        self.assertEqual(json.loads(raw),expected)
                        c.feed(b'{"choices":[{"message":{"reasoning_content":"Public summary","content":"Answer"}}]}');c.finish()
                        kind='summary' if isinstance(r,dict) and (r.get('summary') or r.get('generate_summary')) else 'text'
                        self.assertEqual(c.turn['sections'],[{'kind':kind,'text':'Public summary'}])
                    reasoning.call(self.store,'one',0,'Casey','Planning',run)

    def test_summary_option_is_scoped_to_verified_endpoint_model_and_active_capture(self):
        known='https://inference-api.nvidia.com/v1';sol='azure/openai/gpt-6.1-sol'
        for provider,base,model in [('local',known,sol),('openai',known,sol),('nvidia','https://other.example/v1',sol),
                                    ('nvidia',known+'.example',sol),('nvidia',known,'nvidia/nemotron'),
                                    ('nvidia',known,'deepseek'),('nvidia',known,'gpt-5.9-sol'),('nvidia',known,'vendor/gpt-6.1'),('nvidia',known,'gpt-6ish'),('nvidia',known,'my-gpt-6'),('nvidia',known,None)]:
            with self.subTest(provider=provider,base=base,model=model):
                def run():
                    payload={'model':model,'messages':[{'role':'user','content':reasoning.tag('Task')}]}
                    raw,c=reasoning.request(json.dumps(payload).encode(),provider,base_url=base)
                    self.assertNotIn('reasoning',json.loads(raw));self.assertIsNotNone(c)
                reasoning.call(self.store,'one',0,'Casey','Planning',run)
        for text in ['Task','[[bac-observe:'+'f'*32+']]\nTask']:
            raw,c=reasoning.request(json.dumps({'model':sol,'messages':[{'role':'user','content':text}]}).encode(),'nvidia',base_url=known)
            self.assertNotIn('reasoning',json.loads(raw));self.assertIsNone(c)

    def test_gpt_six_and_later_variants_request_summary(self):
        for model in ['gpt-6', 'openai/gpt-6.1', 'azure/openai/gpt-6.1-sol',
                      'azure/openai/gpt-6.1-terra', 'gpt-6-mini', 'gpt-7', 'gpt-10.2-preview']:
            with self.subTest(model=model):
                def run():
                    payload={'model':model,'messages':[{'role':'user','content':reasoning.tag('Task')}]}
                    raw,c=reasoning.request(json.dumps(payload).encode(),'nvidia',base_url='https://inference-api.nvidia.com/v1/')
                    self.assertEqual(json.loads(raw)['reasoning'],{'summary':'auto'})
                    self.assertTrue(c.turn['summaryRequested'])
                reasoning.call(self.store,'one',0,'Casey','Planning',run)

    def test_chat_summary_mirror_is_shown_and_counted_once(self):
        item={'id':'r1','type':'reasoning','summary':[{'type':'summary_text','text':'First point.'},{'type':'summary_text','text':'Second point.'}],'encrypted_content':'opaque'}
        message={'reasoning_content':'First point.\n\nSecond point.','reasoning_items':[item],'content':'Final answer'}
        c=self.capture({'choices':[{'message':message}]})
        self.assertEqual(c['turns'][0]['sections'],[{'kind':'summary','text':'First point.'},{'kind':'summary','text':'Second point.'}])
        self.assertEqual(c['chars'],len('First point.Second point.'));self.assertNotIn('opaque',json.dumps(c))
        c=self.capture([{'choices':[{'delta':{'reasoning_content':'First point.'}}]},
                        {'choices':[{'delta':{'reasoning_content':'\n\nSecond point.'}}]},
                        {'choices':[{'delta':{'reasoning_items':[item]}}]}],True)
        self.assertEqual(len(c['turns'][0]['sections']),2);self.assertEqual(c['chars'],len('First point.Second point.'))

    def test_distinct_chat_text_is_not_lost_when_summary_items_arrive(self):
        c=self.capture({'choices':[{'message':{'reasoning_content':'Distinct public text','reasoning_items':[
            {'type':'reasoning','id':'r1','summary':[{'type':'summary_text','text':'Public summary'}]},
            {'type':'reasoning','id':'r2','summary':[{'type':'summary_text','text':'Public summary'}]}]}}]})
        self.assertEqual([s['text'] for s in c['turns'][0]['sections']],['Distinct public text','Public summary','Public summary'])

class ProxyIntegrationTests(unittest.TestCase):
    setUp = ReasoningTests.setUp
    def test_verified_sol_proxy_adds_summary_without_replaying_or_changing_response(self):
        import io,urllib.request
        import session_secrets as vault
        import runtime_settings as settings
        captured=[];base='https://inference-api.nvidia.com/v1'
        item={'type':'reasoning','id':'rs1','summary':[{'type':'summary_text','text':'Public summary'}],'encrypted_content':'opaque'}
        wire=json.dumps({'choices':[{'message':{'reasoning_content':'Public summary','reasoning_items':[item],
                                              'tool_calls':[{'id':'call1','type':'function','function':{'name':'read','arguments':'{}'}}]}}]}).encode()
        class Response(io.BytesIO):headers={'Content-Type':'application/json'}
        class Opener:
            def open(self,request,**kwargs):
                captured.append(json.loads(request.data));return Response(wire)
        def run():
            payload={'model':'azure/openai/gpt-6.1-sol','messages':[{'role':'user','content':reasoning.tag('Task')}],
                     'tools':[{'type':'function','function':{'name':'read','parameters':{'type':'object'}}}],
                     'reasoning':{'effort':'low'},'stream':False}
            request=urllib.request.Request(vault.proxy_url('nvidia',base)+'/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer session-only'})
            with patch.object(vault,'get',return_value={'baseUrl':base,'apiKey':'fixture-key'}),patch.object(settings,'provider_opener',return_value=Opener()):
                with urllib.request.urlopen(request) as response:self.assertEqual(response.read(),wire)
                for _ in range(50):
                    calls=reasoning.report(self.store,'account-a','one')['calls']
                    if calls and calls[0]['turns'][0]['status']=='complete':break
                    time.sleep(.01)
            payload['messages'][0]['content']='Task';payload['reasoning']['summary']='auto'
            self.assertEqual(captured,[payload])
        reasoning.call(self.store,'one',0,'Casey','Planning',run)
        call=reasoning.report(self.store,'account-a','one')['calls'][0]
        self.assertEqual(call['turns'][0]['sections'],[{'kind':'summary','text':'Public summary'}])
        self.assertEqual(call['chars'],len('Public summary'))
        self.assertNotIn('opaque',json.dumps(call))

    def test_http_proxy_preserves_response_and_request_with_tools(self):
        import threading, urllib.request
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        import session_secrets as vault
        import runtime_settings as settings
        captured=[]
        wire=b'data: {"choices":[{"delta":{"reasoning_content":"Published"}}]}\n\ndata: {"choices":[{"delta":{"tool_calls":[{"id":"tool-1","function":{"name":"read"}}]}}]}\n\ndata: {"choices":[{"delta":{"content":"Done"}}]}\n\ndata: [DONE]\n\n'
        class Upstream(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                captured.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
                for start in range(0,len(wire),19):self.wfile.write(wire[start:start+19]);self.wfile.flush()
        server=ThreadingHTTPServer(('127.0.0.1',0),Upstream)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        base=f'http://127.0.0.1:{server.server_port}/v1'
        proxy=vault.proxy_url('local',base)
        original={'model':'deepseek','messages':[{'role':'user','content':'Task'},{'role':'assistant','reasoning_content':'previous reasoning','tool_calls':[{'id':'previous'}]},{'role':'tool','tool_call_id':'previous','content':'File'}],'stream':True,'tools':[{'type':'function','function':{'name':'read'}}]}
        def run():
            payload=json.loads(json.dumps(original));payload['messages'][0]['content']=reasoning.tag('Task')
            req=urllib.request.Request(proxy+'/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer session-only'})
            with patch.object(vault,'get',return_value={'baseUrl':base,'apiKey':''}),patch.object(settings,'provider_opener',return_value=urllib.request.build_opener(urllib.request.ProxyHandler({}))):
                with urllib.request.urlopen(req) as response:self.assertEqual(response.read(),wire)
            for _ in range(20):
                if reasoning.report(self.store,'account-a','one')['calls'][0]['turns'][0]['status']=='complete':break
                time.sleep(.01)
        reasoning.call(self.store,'one',5,'Pixel','Working',run)
        self.assertEqual(captured,[original])
        calls=reasoning.report(self.store,'account-a','one')['calls'];self.assertEqual(calls[0]['turns'][0]['sections'],[{'kind':'text','text':'Published'}])
        for _ in range(5):reasoning.report(self.store,'account-a','one')
        self.assertEqual(len(captured),1)

if __name__=='__main__':unittest.main()
