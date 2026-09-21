"""Opt-in disposable-container test of a localhost model and a real read tool.

The model is a deterministic HTTP fixture, not an LLM-quality test. Run only in
the release verification stack; it temporarily replaces that stack's provider.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import time

if os.environ.get('BAC_CONTAINER_TEST') != '1':
    raise SystemExit('Use BAC_CONTAINER_TEST=1 in a disposable release verification stack.')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import agent_runtime as runtime
import ops_common as common

agent = 'bac-'+secrets.token_hex(12)
workspace = common.home()/'smoke-workspaces'/agent
workspace.mkdir(parents=True)
nonce = secrets.token_hex(16)
probe = workspace/'probe.txt'
probe.write_text(nonce)
observed = []
requests = []


class Model(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        body = json.dumps({'object': 'list', 'data': [{'id': 'bac-local', 'object': 'model'}]}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        requests.append(body)
        tools = [m for m in body.get('messages', []) if m.get('role') == 'tool']
        observed.extend(tools)
        # Return the nonce only after it arrives through an actual tool result.
        read_ok = any(nonce in json.dumps(m) for m in tools)
        stopped = len(requests) > 4
        delta = {'role': 'assistant', 'content': 'Verified '+nonce if read_ok else 'Fixture stopped: read did not succeed'} if read_ok or stopped else {
            'role': 'assistant', 'tool_calls': [{'index': 0, 'id': 'call_read_probe', 'type': 'function',
                'function': {'name': 'read', 'arguments': json.dumps({'path': str(probe)})}}]}
        finish = 'stop' if read_ok or stopped else 'tool_calls'
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.end_headers()
        for part, reason in [(delta, None), ({}, finish)]:
            chunk = {'id': 'fixture', 'object': 'chat.completion.chunk', 'created': int(time.time()),
                     'model': 'bac-local', 'choices': [{'index': 0, 'delta': part, 'finish_reason': reason}]}
            self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode())
        self.wfile.write(b'data: [DONE]\n\n')
        self.wfile.flush()


server = ThreadingHTTPServer(('127.0.0.1', 0), Model)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
original = common.read_json(runtime.config_path())
try:
    with runtime.config_lock():
        config = json.loads(json.dumps(original))
        provider = runtime.initial_config()['models']['providers']['bac-vllm']
        provider['baseUrl'] = 'http://127.0.0.1:'+str(server.server_port)+'/v1'
        config['models']['providers'] = {'bac-vllm': provider}
        config['agents']['defaults']['model'] = {'primary': 'bac-vllm/bac-local', 'fallbacks': []}
        runtime.save_config(config)
    runtime.register(agent, workspace, {'name': 'Container read test', 'persona': 'guide', 'skills': ['documents']})
    answer = runtime.respond(agent, 'container-read-test', 'Read '+str(probe)+' and report its exact contents.')
    assert nonce in str(answer), 'The gateway did not return the observed tool result'
    assert any(nonce in json.dumps(m) for m in observed), 'The model never received the read result'
    print('PASS: localhost OpenAI-compatible endpoint → OpenClaw → real read tool → tool result → response')
finally:
    try:
        runtime.delete_native(agent)
    finally:
        with runtime.config_lock():
            runtime.save_config(original)
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
