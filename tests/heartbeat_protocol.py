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
import notes_watch

class Model(BaseHTTPRequestHandler):
    calls=0
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
        if not tools:call('exec',{'command':'python3 skills/bac-notes/scripts/notes_watch.py poll','host':'gateway'})
        elif len(tools)==1:
            content=json.dumps(tools[-1]['content'])
            token=re.search(r'[a-f0-9]{64}',content)
            if 'new-notes' in content and token:
                call('write',{'path':'artifacts/notes-draft.json','content':json.dumps({'token':token[0],'answer':'PROTOCOL FIXTURE: Pat will revise the slides by Friday.'})})
        elif len(tools)==2:call('exec',{'command':'python3 skills/bac-notes/scripts/notes_watch.py publish','host':'gateway'})
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
        agent='bac-'+'a'*24;workspace=folder/'workspace'
        runtime.register(agent,workspace,{'name':'Proof','persona':'analyst','skills':['notes']})
        (workspace/'inbox/meeting.txt').write_text('Pat will revise the slides by Friday.')
        notes_watch.save(workspace,notes_watch.MANIFEST,['inbox/meeting.txt'])
        runtime.set_notes_heartbeat(agent,True)
        # A real 30-second configured heartbeat, no wake or agent endpoint invocation.
        log=(folder/'gateway.log').open('w')
        process=subprocess.Popen([str(installed/'node/bin/node'),str(installed/'package/node_modules/openclaw/openclaw.mjs'),'gateway','run'],env=runtime.environment(),stdout=log,stderr=log)
        try:
            deadline=time.monotonic()+110
            while time.monotonic()<deadline:
                if process.poll() is not None:raise RuntimeError('Native gateway exited: '+(folder/'gateway.log').read_text()[-3000:])
                box=notes_watch.read(workspace,notes_watch.OUTBOX,{})
                if box.get('events'):
                    assert len(box['events'])==1
                    assert box['events'][0]['answer'].startswith('PROTOCOL FIXTURE:')
                    print('PASS: native 30-second heartbeat executed poll, write and publish without a chat request; protocol fixture calls:',Model.calls,flush=True)
                    return
                time.sleep(1)
            raise RuntimeError('Heartbeat did not publish. Calls='+str(Model.calls)+' Log: '+(folder/'gateway.log').read_text()[-4000:])
        finally:
            process.terminate()
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            log.close();model.shutdown();model.server_close()
if __name__=='__main__':main()
