#!/usr/bin/env python3
"""Serve only the prototype's app directory using Python's standard library."""
import argparse
import functools
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def do_GET(self):
        if self.path == '/health':
            version_file = Path(self.directory) / 'version.json'
            version = json.loads(version_file.read_text()) if version_file.exists() else {'version': 'local-preview'}
            body = json.dumps({'app': 'bac-demo', 'version': version['version'], 'mode': 'prototype'}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def main():
    parser = argparse.ArgumentParser(description='Run the BaC Crew UI prototype.')
    parser.add_argument('--host', default=os.environ.get('HOST', '127.0.0.1'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '8080')))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / 'app'
    handler = functools.partial(Handler, directory=str(root))
    try:
        server = ThreadingHTTPServer((args.host, args.port), handler)
    except OSError as error:
        parser.exit(1, f'Cannot start server: {error}. Try --port 8081.\n')
    print(f'BaC Crew prototype: http://{args.host}:{server.server_port}', flush=True)
    print('Simulated agents and OpenShell. Press Ctrl+C to stop.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
