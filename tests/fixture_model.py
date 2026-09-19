"""Protocol fixture only. NOT an LLM; used to exercise the real OpenClaw gateway.

Run manually on port 8000 with an isolated BAC_DATA_DIR and the pinned gateway.
Never run this alongside vLLM on a workshop Spark.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        data = json.dumps({'object': 'list', 'data': [{'id': 'bac-local', 'object': 'model'}]}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        messages = body['messages']
        user_index = max(i for i, message in enumerate(messages) if message['role'] == 'user')
        prompt = json.dumps(messages[user_index]['content'])
        tool_done = any(m['role'] == 'tool' for m in messages[user_index + 1:])
        message = {'role': 'assistant', 'content': 'Protocol fixture: OpenClaw completed the agent run.'}
        reason = 'stop'
        if 'PROTOCOL_SAVE_MEMORY' in prompt and not tool_done:
            message = {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'call_save', 'type': 'function', 'function': {'name': 'write', 'arguments': json.dumps({'path': 'MEMORY.md', 'content': '# Saved preferences\nProtocol fixture preference: concise English.\n'})}}]}
            reason = 'tool_calls'
        elif 'PROTOCOL_READ_MEMORY' in prompt and not tool_done:
            message = {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'call_read', 'type': 'function', 'function': {'name': 'read', 'arguments': json.dumps({'path': 'MEMORY.md'})}}]}
            reason = 'tool_calls'
        elif 'PROTOCOL_READ_MEMORY' in prompt:
            message['content'] = 'Protocol fixture: tool read returned: ' + json.dumps(messages[-1]['content'])
        elif 'PROTOCOL_SAVE_MEMORY' in prompt:
            message['content'] = 'Protocol fixture: memory write tool completed.'
        self.send_response(200)
        if body.get('stream'):
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            delta = dict(message)
            if 'tool_calls' in delta:
                delta['tool_calls'][0]['index'] = 0
            chunks = [{'id': 'fixture', 'object': 'chat.completion.chunk', 'choices': [{'index': 0, 'delta': delta, 'finish_reason': None}]},
                      {'id': 'fixture', 'object': 'chat.completion.chunk', 'choices': [{'index': 0, 'delta': {}, 'finish_reason': reason}]}]
            for chunk in chunks:
                self.wfile.write(('data: ' + json.dumps(chunk) + '\n\n').encode())
            self.wfile.write(b'data: [DONE]\n\n')
        else:
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'id': 'fixture', 'object': 'chat.completion', 'choices': [{'index': 0, 'message': message, 'finish_reason': reason}]}).encode())


if __name__ == '__main__':
    print('TEST FIXTURE, not an LLM: http://127.0.0.1:8000', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8000), Handler).serve_forever()
