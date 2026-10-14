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

    def test_room_updates_are_authenticated_ordered_and_survive_reads(self):
        update = {'openTask':True, 'viewRevision':2}
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/api/credential-session', self.owner, data=update, csrf=False)
        self.assertFalse(self.studio.heartbeat.in_open_task(self.owner['id']))
        self.request('/api/credential-session', self.owner, data=update)
        self.request('/api/state', self.owner)
        self.request('/api/credential-session', self.owner, data={})
        self.request('/api/credential-session', self.owner, data={'openTask':False, 'viewRevision':1})
        self.assertTrue(self.studio.heartbeat.in_open_task(self.owner['id']))
        self.assertFalse(self.studio.heartbeat.in_open_task(self.other['id']))
        for invalid in ({'openTask':'false','viewRevision':3}, {'openTask':False,'viewRevision':True}):
            self.request('/api/credential-session', self.owner, data=invalid)
            self.assertTrue(self.studio.heartbeat.in_open_task(self.owner['id']))
        self.request('/api/credential-session', self.owner, data={'openTask':False, 'viewRevision':3})
        self.assertFalse(self.studio.heartbeat.in_open_task(self.owner['id']))

    def test_room_pause_uses_live_tabs_and_cannot_be_reopened_by_late_close_requests(self):
        import time
        from unittest.mock import patch
        self.request('/api/credential-session', self.owner, data={'openTask':True, 'viewRevision':1})
        self.request('/api/credential-session', self.owner, 'helper', {'openTask':False, 'viewRevision':99})
        self.assertTrue(self.studio.heartbeat.in_open_task(self.owner['id']))
        self.request('/api/credential-session', self.owner, data={'end':True})
        self.request('/api/credential-session', self.owner, data={'openTask':True, 'viewRevision':2})
        self.assertFalse(self.studio.heartbeat.in_open_task(self.owner['id']))
        self.assertTrue(self.studio.heartbeat.connected(self.owner['id']))
        self.request('/api/credential-session', self.owner, 'new-tab', {'openTask':True, 'viewRevision':1})
        with patch('studio_heartbeat.time.monotonic', return_value=time.monotonic()+91):
            self.assertFalse(self.studio.heartbeat.in_open_task(self.owner['id']))
            self.studio.heartbeat.presence(self.owner['id'], 'helper')
            self.assertTrue(self.studio.heartbeat.connected(self.owner['id']))
            self.assertFalse(self.studio.heartbeat.views)



if __name__ == '__main__':unittest.main()
