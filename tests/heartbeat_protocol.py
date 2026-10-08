"""Opt-in native OpenClaw timer proof with a deterministic protocol fixture, NOT an LLM.
Usage: python3 tests/heartbeat_protocol.py /path/to/existing/openclaw
Uses its pinned package/node read-only, a temporary config/workspace and random ports.
"""
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import agent_runtime as runtime
import tech_radar
from radar_fixture_data import sample

class Model(BaseHTTPRequestHandler):
    calls=0
    starts=[]
    def log_message(self,*args):pass
    def do_POST(self):
        data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        Model.calls+=1
        messages=data['messages'];latest=max(i for i,m in enumerate(messages) if m['role']=='user')
        tools=[m for m in messages[latest+1:] if m['role']=='tool']
        answer={'role':'assistant','content':'HEARTBEAT_OK'};reason='stop'
        def call(name,args):
            nonlocal answer,reason
            answer={'role':'assistant','content':None,'tool_calls':[{'id':'call_'+str(Model.calls),'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]};reason='tool_calls'
        if not tools:
            Model.starts.append(time.monotonic())
            call('exec',{'command':'python3 skills/bac-radar/scripts/tech_radar.py poll','host':'gateway'})
        elif len(tools)==1:
            content=json.dumps(tools[-1]['content'])
            tokens=re.findall(r'[a-f0-9]{64}',content)
            if 'new-articles' in content and len(tokens)>=2:
                call('write',{'path':'artifacts/radar-draft.json','content':json.dumps({'token':tokens[0],'articleId':tokens[1],'answer':'PROTOCOL FIXTURE: A useful developer SDK tutorial.'})})
        elif len(tools)==2:call('exec',{'command':'python3 skills/bac-radar/scripts/tech_radar.py publish','host':'gateway'})
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
        if 'tool_calls' in answer:answer['tool_calls'][0]['index']=0
        for delta,finish in [(answer,None),({},reason)]:
            self.wfile.write(('data: '+json.dumps({'id':'proof','object':'chat.completion.chunk','choices':[{'index':0,'delta':delta,'finish_reason':finish}]})+'\n\n').encode())
        self.wfile.write(b'data: [DONE]\n\n')

def unused_port():
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]

def main():
    installed=Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix='bac-native-heartbeat-') as tmp:
        folder=Path(tmp);os.environ['BAC_DATA_DIR']=str(folder)
        runtime.root().mkdir();(runtime.root()/'node').symlink_to(installed/'node');(runtime.root()/'package').symlink_to(installed/'package')
        model=ThreadingHTTPServer(('127.0.0.1',0),Model);threading.Thread(target=model.serve_forever,daemon=True).start()
        config=runtime.initial_config();config['gateway']['port']=unused_port();config['models']['providers']['bac-vllm']['baseUrl']=f'http://127.0.0.1:{model.server_port}/v1';runtime.save_config(config)
        runtime.bootstrap_host()
        agent='bac-'+'a'*24;workspace=folder/'workspace'
        # Keep native work disabled during the same initial quiet interval as
        # the app, then use the actual scheduler, never a forced wake.
        log=(folder/'gateway.log').open('w')
        process=subprocess.Popen([str(installed/'node/bin/node'),str(installed/'package/node_modules/openclaw/openclaw.mjs'),'gateway','run'],env=runtime.environment(),stdout=log,stderr=log)
        try:
            for _ in range(60):
                if process.poll() is not None:raise RuntimeError('Native gateway exited: '+(folder/'gateway.log').read_text()[-3000:])
                try:
                    with socket.create_connection(('127.0.0.1',config['gateway']['port']),timeout=1):break
                except OSError:time.sleep(.5)
            else:raise RuntimeError('Native gateway did not become ready')
            runtime.register(agent,workspace,{'name':'Proof','persona':'analyst','skills':['radar']})
            # Only this temporary test copy uses offline feeds. Production keeps real curl.
            script=workspace/'skills/bac-radar/scripts/tech_radar.py'
            fixtures={source['id']:sample(source,time.time()) for source in tech_radar.SOURCES}
            injected='def fixture_fetch(source, cached):\n    return '+repr(fixtures)+"[source['id']], {}\n\n"
            script.write_text(script.read_text().replace('def run(root, action, fetcher=fetch, now=None):',injected+'def run(root, action, fetcher=fixture_fetch, now=None):'))
            saved=json.loads(runtime.config_path().read_text())
            assert saved['agents']['entries'][agent]['model']=='bac-vllm/bac-local'
            assert saved['models']['providers']['bac-vllm']['baseUrl']==f'http://127.0.0.1:{model.server_port}/v1'
            started=time.monotonic();deadline=started+110;enabled=False
            while time.monotonic()<deadline:
                if process.poll() is not None:raise RuntimeError('Native gateway exited: '+(folder/'gateway.log').read_text()[-3000:])
                if not enabled:
                    assert Model.calls==0, 'Native model ran during initial quiet interval'
                    if time.monotonic()-started>=20:
                        runtime.set_radar_heartbeat(agent,True);enabled=True
                        assert json.loads(runtime.config_path().read_text())['agents']['entries'][agent]['heartbeat']['every']=='20s'
                box=tech_radar.read(workspace,tech_radar.OUTBOX,{})
                if len(box.get('events',[]))>=2:
                    assert len({e['id'] for e in box['events']})==len(box['events'])
                    assert box['events'][0]['answer'].startswith('PROTOCOL FIXTURE:')
                    assert Model.starts[0]-started>=20
                    print('PASS: quiet first 20 seconds, then two native 20-second heartbeats without a chat request; first start:',round(Model.starts[0]-started,1),'seconds; run gap:',round(Model.starts[1]-Model.starts[0],1),'seconds; protocol fixture calls:',Model.calls,flush=True)
                    return
                time.sleep(1)
            raise RuntimeError('Heartbeat did not publish. Calls='+str(Model.calls)+' Log: '+(folder/'gateway.log').read_text()[-4000:])
        finally:
            process.terminate()
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            log.close();model.shutdown();model.server_close()
if __name__=='__main__':main()
