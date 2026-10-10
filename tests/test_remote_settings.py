"""LAN settings parity with a disposable HTTP server and no model calls."""
import http.client
import json
import os
import tempfile
import threading
import unittest
from unittest.mock import patch

from test_studio import Studio, Adapter
from serve import create_server


class RemoteSettingsTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        env = patch.dict(os.environ, {'BAC_DATA_DIR': folder.name})
        env.start(); self.addCleanup(env.stop)
        self.app = Studio(folder.name, Adapter(), start_worker=False)
        self.person = self.app.session()[0]
        self.server = create_server('127.0.0.1', 0, self.app)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close); self.addCleanup(self.server.shutdown)
        self.host = '10.21.11.165:8080'

    def request(self, path, body=None, **overrides):
        headers = {'Host': self.host, 'Cookie': 'bac_session=' + self.person['token'],
                   'X-BaC-CSRF': self.person['csrf'], 'Content-Type': 'application/json',
                   'Origin': 'http://' + self.host}
        headers.update(overrides)
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        conn.request('GET' if body is None else 'POST', '/api/' + path,
                     body=None if body is None else json.dumps(body), headers=headers)
        response = conn.getresponse(); result = response.status, json.loads(response.read())
        conn.close()
        return result

    def test_remote_session_shows_settings_and_location_save_persists(self):
        self.assertTrue(self.request('session')[1]['canConfigure'])
        self.assertEqual(self.request('settings')[0], 200)
        status, _ = self.request('settings', {'section': 'location', 'location': {'city': 'Seoul'}})
        self.assertEqual(status, 200)
        self.assertEqual(self.request('settings')[1]['location']['city'], 'Seoul')

    def test_every_settings_route_accepts_same_origin_remote_session(self):
        routes = [
            ('settings', None, 'runtime_settings.public'),
            ('settings/connections', None, 'model_connections.public_for'),
            ('settings', {}, 'runtime_settings.save'),
            ('settings/models', {}, 'runtime_settings.models'),
            ('settings/start', {}, 'runtime_settings.start_gateway'),
            ('settings/team-model', {}, 'team_models.configure'),
            ('settings/connections', {}, 'model_connections.configure'),
            ('settings/connections/models', {}, 'model_connections.models'),
            ('settings/connections/preferences', {}, 'model_connections.preferences'),
            ('settings/connections/check', {}, 'model_connections.public'),
            ('settings/scenario-model', {}, 'scenario_models.configure'),
            ('settings/scenario-models', {}, 'scenario_models.models'),
        ]
        for route, body, target in routes:
            with self.subTest(route=route, write=body is not None), patch(target, return_value={'ok': True}) as action:
                self.assertEqual(self.request(route, body), (200, {'ok': True}))
                action.assert_called_once()

    def test_session_origin_csrf_and_host_checks_still_prevent_writes(self):
        for headers, status in [({'Cookie': ''}, 401), ({'X-BaC-CSRF': 'wrong'}, 403),
                                ({'Origin': 'http://different.example'}, 403),
                                ({'Host': 'different.example'}, 403)]:
            with self.subTest(headers=headers), patch('model_connections.configure') as configure:
                self.assertEqual(self.request('settings/connections', {}, **headers)[0], status)
                configure.assert_not_called()
        self.assertEqual(self.request('settings', **{'Cookie': ''})[0], 401)


if __name__ == '__main__':
    unittest.main()
