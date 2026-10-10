"""Disposable browser fixture with an expiry trigger; never used by production."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time

sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'scripts'), str(Path(__file__).parent)]
from fixture_studio import BrowserAdapter
from studio import Studio
from serve import create_server, Handler
from studio_sessions import SESSION_IDLE_SECONDS

original_post = Handler.do_POST
original_get = Handler.do_GET
def fixture_get(self):
    if self.path != '/api/fixture-counts':
        return original_get(self)
    with self.server.studio.db() as db:
        counts = {table:db.execute('SELECT count(*) FROM '+table).fetchone()[0]
                  for table in ('participants','agents','crew_contexts')}
    return self.json_response(counts)

def fixture_post(self):
    if self.path == '/api/fixture-disconnect':
        self.rfile.read(int(self.headers.get('Content-Length', '0')))
        with self.server.studio.browser_access.lock:
            self.server.studio.browser_access.views.clear()
        return self.json_response({'disconnected':True})
    if self.path != '/api/fixture-expire':
        return original_post(self)
    account, _ = self.participant()
    self.rfile.read(int(self.headers.get('Content-Length', '0')))
    with self.server.studio.db() as db:
        db.execute('UPDATE participants SET last_seen=? WHERE id=?', (time.time()-SESSION_IDLE_SECONDS-1, account['id']))
    self.server.studio.retire_idle_sessions()
    return self.json_response({'expired': True})

Handler.do_POST = fixture_post
Handler.do_GET = fixture_get
with tempfile.TemporaryDirectory(prefix='bac-session-browser-') as folder:
    os.environ['BAC_DATA_DIR'] = folder
    app = Studio(Path(folder)/'studio', BrowserAdapter())
    server = create_server('0.0.0.0', int(os.environ.get('BAC_TEST_PORT', '18089')), app)
    print('SESSION CLEANUP FIXTURE - NO REAL MODEL OR USER DATA', flush=True)
    try: server.serve_forever()
    finally: app.stop.set(); server.server_close()
