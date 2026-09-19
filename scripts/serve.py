#!/usr/bin/env python3
"""Serve only the prototype's app directory using Python's standard library."""
import argparse
import functools
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Run the BaC Crew UI prototype.')
    parser.add_argument('--host', default=os.environ.get('HOST', '127.0.0.1'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '8080')))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / 'app'
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(root))
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
