#!/usr/bin/env python3
"""BaC Agent Studio: local UI, participant API and shared OpenClaw task queue."""
import argparse
import base64
import functools
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import secrets
import socket
import threading
from urllib.parse import urlparse, parse_qs

from studio import Studio, Problem, safe_file
from telegram_bridge import poll


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        super().end_headers()

    def log_message(self, format, *args):
        # API paths may carry file names; never log request bodies, cookies or pair codes.
        if not self.path.startswith(('/api/', '/survey/')):
            super().log_message(format, *args)

    def json_response(self, value, status=200, cookie=None):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        if cookie:
            self.send_header('Set-Cookie', 'bac_session=' + cookie + '; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000')
        self.end_headers()
        self.wfile.write(body)

    def host_ok(self):
        host = urlparse('http://' + self.headers.get('Host', '')).hostname
        if host in ('localhost', socket.gethostname().lower(), socket.gethostname().lower() + '.local'):
            return True
        try:
            return ipaddress.ip_address(host).is_private or ipaddress.ip_address(host).is_loopback
        except (ValueError, TypeError):
            return False

    def participant(self, create=False):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
        except Exception:
            raise Problem('Invalid session.', 401)
        token = cookie['bac_session'].value if 'bac_session' in cookie else None
        if create:
            return self.server.studio.session(token)
        with self.server.studio.db() as db:
            row = db.execute('SELECT * FROM participants WHERE token=?', (token,)).fetchone()
        if not row:
            raise Problem('Open the Agent Studio page to start a session.', 401)
        return dict(row), False

    def do_GET(self):
        if self.path.startswith('/survey/'):
            try:
                if not self.host_ok():
                    raise Problem('Use the event host address.', 403)
                from studio_events import survey_page
                token=urlparse(self.path).path.removeprefix('/survey/')
                body=survey_page(token, self.server.studio.survey_definition(token)).encode()
                self.send_response(200)
                self.send_header('Content-Type','text/html; charset=utf-8')
                self.send_header('Content-Length',str(len(body)))
                self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'self'")
                self.end_headers();self.wfile.write(body)
            except Problem as error:
                self.json_response({'error':str(error)},error.status)
            return
        if self.path == '/health':
            path = Path(self.directory) / 'version.json'
            version = json.loads(path.read_text()) if path.exists() else {'version': 'local-preview'}
            return self.json_response({'app': 'bac-demo', 'version': version['version'], 'mode': 'agent-studio'})
        if not self.path.startswith('/api/'):
            return super().do_GET()
        try:
            if not self.host_ok():
                raise Problem('Use the host IP address or localhost.', 403)
            parsed = urlparse(self.path)
            studio = self.server.studio
            row, new = self.participant(create=parsed.path == '/api/session')
            owner = studio.resolve_agent(row['id'], self.headers.get('X-BaC-Agent'))
            if parsed.path == '/api/session':
                return self.json_response({'csrf': row['csrf'], 'runtime': studio.runtime_status(), **studio.state(owner)}, cookie=row['token'] if new else None)
            if parsed.path == '/api/state':
                return self.json_response(studio.state(owner))
            if parsed.path == '/api/event-catalog':
                import event_planner
                return self.json_response({'templates':event_planner.TEMPLATES,'topics':event_planner.TOPICS,'harnesses':event_planner.HARNESS})
            if parsed.path == '/api/survey-report':
                return self.json_response(studio.survey_report(owner, parse_qs(parsed.query).get('id',[''])[0]))
            if parsed.path == '/api/runtime':
                return self.json_response(studio.runtime_status())
            if parsed.path == '/api/security':
                from security_lab import public_report
                return self.json_response(public_report(studio.directory))
            if parsed.path == '/api/agent-policy':
                return self.json_response(studio.policy_report(owner))
            if parsed.path == '/api/evidence':
                return self.json_response(studio.evidence(owner, parse_qs(parsed.query).get('id', [''])[0]))
            if parsed.path == '/api/file':
                name = parse_qs(parsed.query).get('path', [''])[0]
                if not (name.startswith(('inbox/', 'artifacts/')) or name in ('MEMORY.md', 'IDENTITY.md', 'SOUL.md', 'AGENTS.md')):
                    raise Problem('File is not available.', 404)
                path = safe_file(studio.workspace(owner), name, True)
                if path.suffix in ('.xlsx','.eml'):
                    return self.json_response({'path':name,'encoding':'base64','content':base64.b64encode(path.read_bytes()).decode(), 'mime':'message/rfc822' if path.suffix=='.eml' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
                return self.json_response({'path': name, 'content': path.read_text(encoding='utf-8')})
            raise Problem('Not found.', 404)
        except Problem as error:
            self.json_response({'error': str(error)}, error.status)
        except (UnicodeError, ValueError):
            self.json_response({'error': 'Invalid data.'}, 400)

    def do_POST(self):
        try:
            if not self.host_ok():
                raise Problem('Use the host IP address or localhost.', 403)
            origin = self.headers.get('Origin')
            if origin and urlparse(origin).netloc != self.headers.get('Host'):
                raise Problem('Cross-origin requests are not accepted.', 403)
            if self.path.startswith('/survey/'):
                size=int(self.headers.get('Content-Length','0'))
                if not 0 < size <= 4096:
                    raise Problem('Invalid survey response.',413)
                data=json.loads(self.rfile.read(size))
                if not isinstance(data,dict):
                    raise Problem('Expected survey answers.')
                return self.json_response(self.server.studio.survey_answer(self.path.removeprefix('/survey/'),data))
            row, _ = self.participant()
            if not secrets.compare_digest(self.headers.get('X-BaC-CSRF', ''), row['csrf']):
                raise Problem('Refresh the page to renew your session.', 403)
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 512000:
                raise Problem('Request is too large or empty.', 413)
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise Problem('Expected a JSON object.')
            studio = self.server.studio
            owner = studio.resolve_agent(row['id'], self.headers.get('X-BaC-Agent'))
            routes = {
                '/api/agents': lambda: studio.add_agent(row['id'], data),
                '/api/onboard': lambda: studio.onboard(owner, data),
                '/api/profile': lambda: studio.configure(owner, data),
                '/api/delete-agent': lambda: studio.delete_agent(owner, data),
                '/api/agent-policy': lambda: studio.policy_change(owner, data),
                '/api/jobs': lambda: studio.enqueue(owner, data),
                '/api/event-plan': lambda: studio.event_plan(data),
                '/api/survey-replan': lambda: studio.survey_replan(owner, data),
                '/api/upload': lambda: studio.upload(owner, data),
                '/api/decision': lambda: studio.decision(owner, data.get('id'), data.get('action')),
                '/api/pair': lambda: studio.pair(owner),
                '/api/reset': lambda: studio.reset_board(owner),
            }
            if self.path not in routes:
                raise Problem('Not found.', 404)
            self.json_response(routes[self.path]())
        except Problem as error:
            self.json_response({'error': str(error)}, error.status)
        except (UnicodeError, ValueError, TypeError):
            self.json_response({'error': 'Invalid request data.'}, 400)
        except Exception:
            self.json_response({'error': 'The host could not complete the request. Check application logs.'}, 500)


def create_server(host='127.0.0.1', port=8080, studio=None):
    root = Path(__file__).resolve().parents[1] / 'app'
    server = ThreadingHTTPServer((host, port), functools.partial(Handler, directory=str(root)))
    server.studio = studio or Studio()
    return server


def main():
    parser = argparse.ArgumentParser(description='Run BaC Agent Studio.')
    parser.add_argument('--host', default=os.environ.get('HOST', '127.0.0.1'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '8080')))
    args = parser.parse_args()
    try:
        server = create_server(args.host, args.port)
    except OSError as error:
        parser.exit(1, f'Cannot start server: {error}. Try --port 8081.\n')
    threading.Thread(target=poll, args=(server.studio,), daemon=True, name='bac-telegram').start()
    print(f'BaC Agent Studio: http://{args.host}:{server.server_port}', flush=True)
    print('OpenClaw runs tasks when configured. Visual rehearsal remains available separately.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.studio.stop.set()
        server.server_close()


if __name__ == '__main__':
    main()
