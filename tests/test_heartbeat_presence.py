"""Browser leases must be authenticated, tab-scoped and independent of model keys."""
import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from studio import Studio
from serve import create_server
from test_tech_radar import RadarAdapter


class PresenceHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        adapter = RadarAdapter(); adapter.status = lambda: {'ready': True, 'gateway': True, 'model': True}
        self.studio = Studio(self.temp.name, adapter, start_worker=False)
        self.owner = self.studio.session()[0]
        self.other = self.studio.session()[0]
        self.server = create_server('127.0.0.1', 0, self.studio)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.close)
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(3)

    def request(self, path, account=None, tab='tab', data=None, csrf=True):
        headers = {'X-BaC-Key-Session': tab}
        if account:
            headers['Cookie'] = 'bac_session=' + account['token']
            if csrf:headers['X-BaC-CSRF'] = account['csrf']
        if data is not None:headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(self.base+path, headers=headers,
                  data=json.dumps(data).encode() if data is not None else None)
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request) as response:
            return json.load(response)

    def test_anonymous_and_wrong_csrf_requests_cannot_renew_a_lease(self):
        with self.assertRaises(urllib.error.HTTPError):self.request('/api/state')
        with self.assertRaises(urllib.error.HTTPError):self.request('/api/credential-session', self.owner, data={}, csrf=False)
        self.assertFalse(self.studio.heartbeat.connected(self.owner['id']))

    def test_keyless_session_state_renewal_and_close_are_scoped_to_the_owner_and_tab(self):
        self.request('/api/session', self.owner)
        self.assertTrue(self.studio.heartbeat.connected(self.owner['id']))
        self.assertFalse(self.studio.heartbeat.connected(self.other['id']))
        self.request('/api/state', self.owner, 'tab2')
        self.request('/api/credential-session', self.owner, data={'end': True})
        self.assertTrue(self.studio.heartbeat.connected(self.owner['id']))
        self.request('/api/credential-session', self.owner, 'tab2', {'end': True})
        self.assertFalse(self.studio.heartbeat.connected(self.owner['id']))
        self.request('/api/state', self.owner)
        self.assertFalse(self.studio.heartbeat.connected(self.owner['id']))
        self.request('/api/credential-session', self.owner, 'fresh-tab', {})
        self.assertTrue(self.studio.heartbeat.connected(self.owner['id']))


if __name__ == '__main__':unittest.main()
