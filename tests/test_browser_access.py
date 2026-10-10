"""Browser admission must precede participant and native-team creation."""
from concurrent.futures import ThreadPoolExecutor
import http.client
import json
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from test_studio import Studio, Adapter
from studio import Problem
from serve import create_server
from browser_access import BROWSER_GRACE_SECONDS


class BrowserAccessTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.app = Studio(temp.name, Adapter(), start_worker=False)
        self.access = self.app.browser_access

    def open(self, token=None, view='a'*48):
        return self.access.session(token, view, create=True)[0]

    def blocked(self, token=None, view='b'*48, create=True):
        with self.assertRaises(Problem) as caught:
            self.access.session(token, view, create=create)
        self.assertEqual(caught.exception.status, 423)

    def test_simultaneous_browsers_create_only_one_participant(self):
        barrier = threading.Barrier(2)
        def start(view):
            barrier.wait()
            try: return self.open(view=view)['id']
            except Problem as error: return error.status
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(start, ['a'*48, 'b'*48]))
        self.assertEqual(results.count(423), 1)
        with self.app.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM participants').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM crew_contexts').fetchone()[0], 0)

    def test_refresh_and_same_browser_tabs_share_existing_agents(self):
        account = self.open()
        self.app.onboard(account['id'], {'name':'Fixture', 'skills':['writer']})
        refreshed = self.open(account['token'], 'b'*48)
        self.assertEqual(refreshed['id'], account['id'])
        self.access.release(account['id'], 'a'*48)
        self.blocked(view='c'*48)
        self.assertIsNotNone(self.app.profile(account['id']))

    def test_close_last_tab_releases_admission_without_deleting_data(self):
        account = self.open()
        self.access.release(account['id'], 'a'*48)
        other = self.open(view='b'*48)
        self.assertNotEqual(other['id'], account['id'])
        # A delayed close event from the previous browser cannot release this one.
        self.access.release(account['id'], 'a'*48)
        self.blocked(view='c'*48)
        with self.app.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM participants').fetchone()[0], 2)

    def test_lost_connection_expires_and_old_browser_cannot_resume_work(self):
        with patch('browser_access.time.monotonic', return_value=100):
            account = self.open()
        with patch('browser_access.time.monotonic', return_value=100+BROWSER_GRACE_SECONDS-1):
            self.blocked()
        with patch('browser_access.time.monotonic', return_value=100+BROWSER_GRACE_SECONDS):
            other = self.open(view='b'*48)
            self.blocked(account['token'], 'a'*48, create=False)
        self.assertNotEqual(account['id'], other['id'])

    def test_renewal_keeps_a_background_tab_alive(self):
        with patch('browser_access.time.monotonic', return_value=100):
            account = self.open()
        with patch('browser_access.time.monotonic', return_value=160):
            self.access.session(account['token'], 'a'*48)
        with patch('browser_access.time.monotonic', return_value=210):
            self.blocked()

    def test_closed_browser_work_finishes_before_another_demo_opens(self):
        account = self.open()
        self.app.onboard(account['id'], {'name':'Fixture', 'skills':['writer']})
        self.app.enqueue(account['id'], {'prompt':'Fixture work'})
        self.access.release(account['id'], 'a'*48)
        self.blocked()  # queued foreground work
        with self.app.db() as db:
            db.execute("UPDATE jobs SET status='done'")
        self.app.executing_owners.add(account['id'])
        self.blocked()  # final artifact writes
        self.app.executing_owners.clear()
        self.assertNotEqual(self.open(view='b'*48)['id'], account['id'])

    def test_own_browser_can_reconnect_during_its_work(self):
        account = self.open()
        self.app.executing_owners.add(account['id'])
        self.access.release(account['id'], 'a'*48)
        self.assertEqual(self.open(account['token'], 'b'*48)['id'], account['id'])

    def test_background_settings_clients_do_not_take_browser_slot(self):
        helper, _ = self.app.session()
        account = self.open()
        self.app.touch_session(helper['id'])
        self.assertNotEqual(account['id'], helper['id'])
        self.blocked()

    def test_retired_account_can_recover_to_a_new_session(self):
        account = self.open()
        with self.app.db() as db:
            db.execute('UPDATE participants SET retiring=1 WHERE id=?', (account['id'],))
        self.assertNotEqual(self.open(account['token'])['id'], account['id'])

    def test_invalid_view_cannot_create_participant(self):
        with self.assertRaises(Problem):
            self.open(view='')
        with self.app.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM participants').fetchone()[0], 0)

    def test_deleted_account_does_not_leave_a_stale_browser_lock(self):
        account = self.open()
        with self.app.db() as db:
            db.execute('UPDATE participants SET last_seen=0 WHERE id=?', (account['id'],))
        self.app.clean_idle_sessions()
        self.assertNotEqual(self.open(account['token'])['id'], account['id'])


class BrowserAccessHTTPTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.app = Studio(temp.name, Adapter(), start_worker=False)
        self.server = create_server('127.0.0.1', 0, self.app)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, route, view, cookie='', csrf='', body=None, host='127.0.0.1'):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        headers = {'Host':host, 'Origin':'http://'+host, 'Cookie':cookie,
                   'X-BaC-Browser-View':view, 'X-BaC-Key-Session':view,
                   'X-BaC-CSRF':csrf, 'Content-Type':'application/json'}
        conn.request('GET' if body is None else 'POST', '/api/'+route,
                     body=None if body is None else json.dumps(body), headers=headers)
        response = conn.getresponse()
        result = response.status, json.loads(response.read()), response.getheader('Set-Cookie')
        conn.close()
        return result

    def test_localhost_and_lan_share_one_slot_and_block_before_state_creation(self):
        self.assertEqual(self.request('session','a'*48)[0],200)
        with self.app.db() as db:
            before = [db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('participants','agents','crew_contexts','jobs')]
        self.assertEqual(self.request('session','b'*48,host='10.21.11.165')[0],423)
        with self.app.db() as db:
            after = [db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('participants','agents','crew_contexts','jobs')]
        self.assertEqual(before,after)

    def test_closing_requires_csrf_and_releases_only_that_view(self):
        _, account, cookie = self.request('session','a'*48)
        cookie = cookie.split(';')[0]
        self.assertEqual(self.request('credential-session','a'*48,cookie,body={'end':True})[0],403)
        self.assertEqual(self.request('session','b'*48)[0],423)
        self.assertEqual(self.request('credential-session','a'*48,cookie,account['csrf'],{'end':True})[0],200)
        self.assertEqual(self.request('session','b'*48)[0],200)

    def test_expired_browser_cannot_submit_a_task_after_another_claims(self):
        _, account, cookie = self.request('session','a'*48)
        cookie = cookie.split(';')[0]
        with self.app.browser_access.lock:
            self.app.browser_access.views.clear()
        self.assertEqual(self.request('session','b'*48)[0],200)
        with patch.object(self.app,'onboard') as onboard:
            self.assertEqual(self.request('onboard','a'*48,cookie,account['csrf'],{'name':'Stale'})[0],423)
            onboard.assert_not_called()


if __name__ == '__main__': unittest.main()
