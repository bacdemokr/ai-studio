import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import openshell_warmup as warmup


class WarmupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.owner = 'a' * 24
        self.config = {'prefix': ['openshell', '--gateway', 'test', '--workspace', 'demo'],
                       'env': {}, 'directory': Path(self.temp.name), 'owner': self.owner,
                       'image': 'registry/openclaw@sha256:example', 'policy': '/default-deny.json'}
        self.rows = [];self.calls = [];self.states = [];self.stop = threading.Event()
        self.fail_create = False;self.fail_delete = False;self.not_ready = False

    def cli(self, command, env, timeout=20, stop=None):
        args = command[len(self.config['prefix']):];self.calls.append(args)
        if args[:2] == ['sandbox', 'list']:
            return json.dumps({'sandboxes': self.rows, 'next_page_token': ''})
        if args[:2] == ['sandbox', 'delete']:
            if self.fail_delete:raise RuntimeError('cleanup failed')
            self.rows = [r for r in self.rows if r['name'] != args[2]]
        if args[:2] == ['sandbox', 'create']:
            self.rows.append({'name': args[args.index('--name')+1],
                              'labels': {'bac-warmup-owner': self.owner},
                              'phase': 'Pending' if self.not_ready else 'Ready'})
            if self.fail_create:raise RuntimeError('uncertain create outcome')
        return '{}'

    def prepare(self):
        with patch.object(warmup, 'settings', return_value=self.config), patch.object(warmup, 'invoke', side_effect=self.cli):
            return warmup.prepare(self.stop, self.states.append)

    def test_native_prepare_and_scoped_cleanup(self):
        self.assertEqual(self.prepare(), 'ready');self.assertEqual(self.rows, [])
        create = next(c for c in self.calls if c[:2] == ['sandbox', 'create'])
        self.assertIn('--no-auto-providers', create)
        self.assertIn('--no-keep', create)  # Native expiry also covers app termination.
        self.assertNotIn('--output', create)  # Native --no-keep conflicts with structured output.
        self.assertEqual(create[create.index('--policy')+1], '/default-deny.json')
        self.assertEqual(create[create.index('--from')+1], self.config['image'])
        self.assertEqual(create[-3:], ['--', 'sleep', '60'])
        self.assertLessEqual(len(create[create.index('--name')+1]), 19)
        self.assertNotIn('--upload', create);self.assertNotIn('--provider', create)
        self.assertNotIn('--env', create)
        self.assertEqual(self.states, ['preparing', 'cleaning'])

    def test_partial_creation_is_cleaned_without_retrying_creation(self):
        self.fail_create = True
        with self.assertRaises(RuntimeError):self.prepare()
        self.assertEqual(self.rows, [])
        self.assertEqual(sum(c[:2] == ['sandbox', 'create'] for c in self.calls), 1)

    def test_pending_sandbox_does_not_report_success(self):
        self.not_ready = True
        with self.assertRaises(RuntimeError):self.prepare()
        self.assertEqual(self.rows, [])

    def test_cleanup_failure_stops_new_creation(self):
        self.rows = [{'name': 'bac-wu-'+'b'*12,
                      'labels': {'bac-warmup-owner': self.owner}}]
        self.fail_delete = True
        with self.assertRaises(RuntimeError):self.prepare()
        self.assertFalse(any(c[:2] == ['sandbox', 'create'] for c in self.calls))

    def test_restart_recovers_only_installation_owned_warmup(self):
        stale = 'bac-wu-'+'b'*12
        self.rows = [{'name': stale, 'labels': {'bac-warmup-owner': self.owner}}]
        self.assertEqual(self.prepare(), 'ready')
        self.assertLess(self.calls.index(['sandbox', 'delete', stale]),
                        next(i for i,c in enumerate(self.calls) if c[:2] == ['sandbox', 'create']))

    def test_agent_or_foreign_resource_never_deleted(self):
        for name, owner in [('oc-user-agent', self.owner), ('bac-wu-'+'b'*12, 'foreign')]:
            self.calls = [];self.rows = [{'name': name, 'labels': {'bac-warmup-owner': owner}}]
            with self.assertRaises(RuntimeError):self.prepare()
            self.assertFalse(any(c[:2] in (['sandbox', 'delete'], ['sandbox', 'create']) for c in self.calls))

    def test_disabled_runtime_is_not_installed_or_contacted(self):
        with patch.object(warmup, 'settings', return_value=None), patch.object(warmup, 'invoke') as cli:
            self.assertEqual(warmup.prepare(self.stop, self.states.append), 'not-configured')
            cli.assert_not_called()

    def test_shutdown_before_start_creates_nothing(self):
        self.stop.set()
        with self.assertRaises(warmup.Cancelled):self.prepare()
        self.assertEqual(self.calls, [])

    def test_cross_process_lock_prevents_duplicate_warmups(self):
        with (self.config['directory']/'.warmup.lock').open('a') as handle:
            warmup.fcntl.flock(handle, warmup.fcntl.LOCK_EX | warmup.fcntl.LOCK_NB)
            self.assertEqual(self.prepare(), 'skipped');self.assertEqual(self.calls, [])

    def test_startup_is_nonblocking_and_only_starts_once(self):
        entered, release = threading.Event(), threading.Event();calls = []
        def prepare(stop, publish):
            calls.append(1);entered.set();release.wait(2);return 'ready'
        worker = warmup.StartupWarmup(self.stop, prepare)
        started = time.monotonic();worker.start();worker.start()
        self.assertLess(time.monotonic()-started, .5)
        self.assertTrue(entered.wait(1));self.assertEqual(calls, [1])
        self.assertEqual(worker.state['state'], 'checking')
        release.set();worker.thread.join(2)
        self.assertEqual(worker.state['state'], 'ready')

    def test_failure_is_contained_and_output_is_not_exposed(self):
        def prepare(stop, publish):raise RuntimeError('sensitive raw CLI output')
        worker = warmup.StartupWarmup(self.stop, prepare)
        worker.start();worker.thread.join(2)
        self.assertEqual(worker.state['state'], 'unavailable')
        self.assertNotIn('sensitive', json.dumps(worker.state))

    def test_native_command_cancellation_is_bounded(self):
        import os
        self.stop.set();started = time.monotonic()
        with self.assertRaises(warmup.Cancelled):
            warmup.invoke([sys.executable, '-c', 'import time; time.sleep(30)'], dict(os.environ), stop=self.stop)
        self.assertLess(time.monotonic()-started, 3)


if __name__ == '__main__':unittest.main()
