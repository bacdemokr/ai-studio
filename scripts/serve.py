#!/usr/bin/env python3
"""BaC Agent Studio: local UI, participant API and shared OpenClaw task queue."""
import argparse
import base64
import functools
import hashlib
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


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        super().end_headers()

    def log_message(self, format, *args):
        # API paths may carry file names; never log request bodies or cookies.
        if not self.path.startswith(('/api/', '/survey/')):
            super().log_message(format, *args)

    def json_response(self, value, status=200, cookie=None, conditional=False):
        body = json.dumps(value).encode()
        etag = '"' + hashlib.sha256(body).hexdigest() + '"' if conditional else None
        if etag and self.headers.get('If-None-Match') == etag:
            self.send_response(304)
            self.send_header('ETag', etag)
            self.end_headers()
            return
        self.send_response(status)
        if etag:
            self.send_header('ETag', etag)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
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

    def is_operator(self):
        host=urlparse('http://'+self.headers.get('Host','')).hostname
        try:
            return ipaddress.ip_address(self.client_address[0]).is_loopback and (host=='localhost' or ipaddress.ip_address(host).is_loopback)
        except ValueError:
            return False

    def require_operator(self):
        if not self.is_operator():
            raise Problem('Open settings on localhost, or through your private SSH tunnel.',403)

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
                return self.json_response({'csrf': row['csrf'], 'canConfigure': self.is_operator(), 'runtime': studio.runtime_status(), **studio.state(owner)}, cookie=row['token'] if new else None)
            if parsed.path == '/api/state':
                return self.json_response(studio.state(owner), conditional=True)
            if parsed.path == '/api/telegram':
                import telegram_notifications
                return self.json_response(telegram_notifications.public(row['id'], row['id']+':'+self.headers.get('X-BaC-Key-Session','missing')))
            if parsed.path == '/api/settings':
                self.require_operator()
                import runtime_settings
                return self.json_response(runtime_settings.public(row['id']+':'+self.headers.get('X-BaC-Key-Session','missing')))
            if parsed.path == '/api/event-catalog':
                import event_planner
                return self.json_response({'templates':event_planner.TEMPLATES,'topics':event_planner.TOPICS,'harnesses':event_planner.HARNESS})
            if parsed.path == '/api/survey-report':
                return self.json_response(studio.survey_report(owner, parse_qs(parsed.query).get('id',[''])[0]))
            if parsed.path == '/api/telemetry':
                import telemetry
                return self.json_response(telemetry.report(studio, owner))
            if parsed.path == '/api/runtime':
                return self.json_response(studio.runtime_status())
            if parsed.path == '/api/security':
                from security_lab import public_report
                return self.json_response(public_report(studio.directory))
            if parsed.path == '/api/agent-policy':
                return self.json_response(studio.policy_report(owner))
            if parsed.path == '/api/crew-policy':
                query = parse_qs(parsed.query, keep_blank_values=True)
                values = query.get('role', [])
                if set(query) != {'role'} or len(values) != 1 or not values[0].isascii() or not values[0].isdecimal():
                    raise Problem('Choose one valid crew member.')
                return self.json_response(studio.crew_policy_report(owner, int(values[0])))
            if parsed.path == '/api/evidence':
                return self.json_response(studio.evidence(owner, parse_qs(parsed.query).get('id', [''])[0]))
            if parsed.path == '/api/agent-documents':
                from agent_documents import read_documents
                query=parse_qs(parsed.query,keep_blank_values=True)
                if set(query)-{'role'} or len(query.get('role',[]))>1:
                    raise Problem('Choose one agent to inspect.')
                role=None
                if 'role' in query:
                    value=query['role'][0]
                    if not value.isascii() or not value.isdecimal():raise Problem('Choose a valid crew member.')
                    role=int(value)
                return self.json_response(read_documents(studio,owner,role))
            if parsed.path == '/api/file':
                name = parse_qs(parsed.query).get('path', [''])[0]
                if not (name.startswith(('inbox/', 'artifacts/')) or name in ('MEMORY.md', 'IDENTITY.md', 'SOUL.md', 'AGENTS.md')):
                    raise Problem('File is not available.', 404)
                path = safe_file(studio.workspace(owner), name, True)
                if path.suffix.lower() in ('.png','.jpg','.webp'):
                    mime={'.png':'image/png','.jpg':'image/jpeg','.webp':'image/webp'}[path.suffix.lower()]
                    return self.json_response({'path':name,'encoding':'base64','content':base64.b64encode(path.read_bytes()).decode(),'mime':mime})
                if path.suffix.lower()=='.pdf':
                    return self.json_response({'path':name,'encoding':'base64','content':base64.b64encode(path.read_bytes()).decode(), 'mime':'application/pdf'})
                if path.suffix.lower()=='.pptx':
                    return self.json_response({'path':name,'encoding':'base64','content':base64.b64encode(path.read_bytes()).decode(),'mime':'application/vnd.openxmlformats-officedocument.presentationml.presentation'})
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
            if not 0 < size <= (15 * 1024 * 1024 if self.path in ('/api/upload','/api/jobs') else 512000):
                raise Problem('Request is too large or empty.', 413)
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise Problem('Expected a JSON object.')
            studio = self.server.studio
            owner = studio.resolve_agent(row['id'], self.headers.get('X-BaC-Agent'))
            lease = self.headers.get('X-BaC-Key-Session','')
            if not lease or len(lease)>100:lease='missing'
            data['_credentialSession']=row['id']+':'+lease
            if self.path == '/api/credential-session':
                import session_secrets
                if data.get('end'):session_secrets.release(data['_credentialSession'])
                else:session_secrets.renew(data['_credentialSession'])
                studio.status_cache=(0,{})
                return self.json_response({'ok':True})
            if self.path == '/api/telegram':
                import telegram_notifications
                return self.json_response(telegram_notifications.configure(row['id'], data))
            if self.path == '/api/telegram/test':
                import telegram_notifications
                return self.json_response(telegram_notifications.test(row['id'], data['_credentialSession']))
            if self.path in ('/api/settings','/api/settings/models','/api/settings/start'):
                self.require_operator()
                import runtime_settings
                if self.path == '/api/settings/models':return self.json_response(runtime_settings.models(data))
                if self.path == '/api/settings/start':return self.json_response(runtime_settings.start_gateway())
                return self.json_response(runtime_settings.save(studio,data))
            routes = {
                '/api/heartbeat': lambda: studio.notes.control(owner, data),
                '/api/agents': lambda: studio.add_agent(row['id'], data),
                '/api/onboard': lambda: studio.onboard(owner, data),
                '/api/profile': lambda: studio.configure(owner, data),
                '/api/delete-agent': lambda: studio.delete_agent(owner, data),
                '/api/agent-policy': lambda: studio.policy_change(owner, data),
                '/api/crew-policy': lambda: studio.crew_policy_change(owner, data),
                '/api/jobs': lambda: studio.enqueue(owner, data),
                '/api/event-plan': lambda: studio.event_plan(data),
                '/api/survey-replan': lambda: studio.survey_replan(owner, data),
                '/api/upload': lambda: studio.upload(owner, data),
                '/api/decision': lambda: studio.decision(owner, data.get('id'), data.get('action')),
                '/api/prepare-demo': lambda: studio.prepare_demo(owner, data),
                '/api/retry-reaction': lambda: studio.retry_reaction(owner, data),
                '/api/event-reset': lambda: studio.reset_event_board(owner),
                '/api/reset': lambda: studio.reset_board(owner),
                '/api/crew-chat-reset': lambda: studio.reset_crew_chats(owner),
                '/api/bac-reset': lambda: studio.reset_crew_chats(owner, reset_event=True),
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
    import session_secrets, ops_common
    if studio is None:session_secrets.purge_legacy(ops_common.home())
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
    print(f'BaC Agent Studio: http://{args.host}:{server.server_port}', flush=True)
    print('Connect a model in Settings to run OpenClaw tasks.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.studio.stop.set()
        if hasattr(server.studio, 'notes_worker'):server.studio.notes_worker.join(timeout=15)
        server.server_close()


if __name__ == '__main__':
    main()
