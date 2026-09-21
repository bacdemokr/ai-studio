"""Failure injection around native OpenShell responses and activation boundaries."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts')]
import agent_policy as policy


class NativePolicyResilienceTests(unittest.TestCase):
    aid = 'bac-' + 'a' * 24

    def snapshot(self, permissions=()):
        return {'sandbox': 'oc-owned', 'version': 2, 'policy_source': 'sandbox',
                'policy': policy.policy_document(permissions), 'loaded': True}

    def test_malformed_registry_never_means_no_sandbox(self):
        for malformed in (None, [], {}, {'containers': None}, {'containers': [None]}):
            with self.subTest(malformed=malformed), patch.object(policy, 'sandbox_registry', return_value=malformed):
                with self.assertRaises(RuntimeError):
                    policy.runtimes(self.aid)

    def test_malformed_effective_policy_or_revision_is_not_verified(self):
        good = self.snapshot()
        for malformed in ([], None, {**good, 'policy': []}, {**good, 'version': True}, {**good, 'version': 0}):
            with self.subTest(malformed=malformed), patch.object(policy, 'shell', return_value=json.dumps(malformed)):
                with self.assertRaises(RuntimeError):
                    policy.read_policy('oc-owned')
        with patch.object(policy, 'shell', side_effect=[json.dumps(good), '[]']):
            with self.assertRaises(RuntimeError):
                policy.read_policy('oc-owned')
        with patch.object(policy, 'shell', side_effect=[json.dumps(good), json.dumps({'status': 'loaded', 'version': 2, 'active_version': 1})]):
            self.assertFalse(policy.read_policy('oc-owned')['loaded'])

    def test_invalid_network_rule_reports_unavailable_instead_of_crashing(self):
        config = {'agents': {'entries': {self.aid: {'sandbox': {'mode': 'all'}}}}}
        for malformed in (None, [], {'broken': None}, {'broken': {'binaries': [None]}}, {'broken': {'endpoints': None}}):
            snapshot = self.snapshot()
            snapshot['policy']['network_policies'] = malformed
            with self.subTest(malformed=malformed), patch.object(policy, 'configured', return_value=True), \
                 patch.object(policy.c, 'read_json', return_value=config), \
                 patch.object(policy, 'runtimes', return_value=[{'containerName': 'oc-owned', 'running': True}]), \
                 patch.object(policy, 'read_policy', return_value=snapshot):
                self.assertEqual(policy.inspect(self.aid, 'openshell')['status'], 'unavailable')

    def test_filesystem_drift_is_repaired_even_with_unchanged_network(self):
        for field in ('filesystem_policy', 'landlock'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                before = self.snapshot(['weather'])
                before['policy'][field] = {}
                after = self.snapshot(['weather'])
                with patch.object(policy, 'configured', return_value=True), \
                     patch.object(policy.runtime, 'root', return_value=Path(folder)), \
                     patch.object(policy, 'runtimes', return_value=[{'containerName': 'oc-owned', 'running': True}]), \
                     patch.object(policy, 'read_policy', side_effect=[before, after]), \
                     patch.object(policy, 'shell') as write, patch.object(policy, 'inspect', return_value={'status': 'applied'}):
                    self.assertEqual(policy.apply(self.aid, ['weather'])['status'], 'applied')
                    self.assertEqual(write.call_count, 1)
                    self.assertEqual(write.call_args.args[:3], ('policy', 'set', 'oc-owned'))

    def test_lost_activation_ack_requires_verified_commit(self):
        for committed in (True, False):
            for failure in (subprocess.TimeoutExpired('set', 75), RuntimeError('connection lost')):
                with self.subTest(committed=committed, failure=type(failure).__name__), tempfile.TemporaryDirectory() as folder:
                    before = self.snapshot()
                    after = self.snapshot(['weather']) if committed else before
                    with patch.object(policy, 'configured', return_value=True), \
                         patch.object(policy.runtime, 'root', return_value=Path(folder)), \
                         patch.object(policy, 'runtimes', return_value=[{'containerName': 'oc-owned', 'running': True}]), \
                         patch.object(policy, 'read_policy', side_effect=[before, after]), \
                         patch.object(policy, 'shell', side_effect=failure) as write, \
                         patch.object(policy, 'inspect', return_value={'status': 'applied'}) as inspect:
                        if committed:
                            self.assertEqual(policy.apply(self.aid, ['weather'])['status'], 'applied')
                        else:
                            with self.assertRaises(type(failure)):
                                policy.apply(self.aid, ['weather'])
                            inspect.assert_not_called()
                        self.assertEqual(write.call_count, 1)  # No repeated mutation after timeout.

    def test_all_owned_sandboxes_must_match_and_logs_failure_is_independent(self):
        config = {'agents': {'entries': {self.aid: {'sandbox': {'mode': 'all'}}}}}
        rows = [{'containerName': 'oc-one', 'running': True}, {'containerName': 'oc-two', 'running': True}]
        for mismatch in (True, False):
            first = self.snapshot(['weather'])
            second = copy.deepcopy(first)
            if mismatch:
                second['policy']['filesystem_policy']['read_write'].append('/')
            with self.subTest(mismatch=mismatch), patch.object(policy, 'configured', return_value=True), \
                 patch.object(policy.c, 'read_json', return_value=config), \
                 patch.object(policy, 'runtimes', return_value=rows), \
                 patch.object(policy, 'read_policy', side_effect=[first, second]), \
                 patch.object(policy, 'public_logs', side_effect=subprocess.TimeoutExpired('logs', 35)):
                report = policy.inspect(self.aid, 'openshell', ['weather'])
                self.assertEqual(report['status'], 'needs-review' if mismatch else 'applied')
                self.assertTrue(report['logsUnavailable'])
                self.assertEqual(len(report['sandboxes']), 2)

    def test_partial_multi_sandbox_apply_is_not_success(self):
        before, after = self.snapshot(), self.snapshot(['weather'])
        with tempfile.TemporaryDirectory() as folder, patch.object(policy, 'configured', return_value=True), \
             patch.object(policy.runtime, 'root', return_value=Path(folder)), \
             patch.object(policy, 'runtimes', return_value=[{'containerName': name} for name in ('oc-one', 'oc-two')]), \
             patch.object(policy, 'read_policy', side_effect=[before, after, before, before]), \
             patch.object(policy, 'shell', side_effect=[None, subprocess.TimeoutExpired('set', 75)]) as write, \
             patch.object(policy, 'inspect') as inspect:
            with self.assertRaises(subprocess.TimeoutExpired):
                policy.apply(self.aid, ['weather'])
            self.assertEqual([c.args[2] for c in write.call_args_list], ['oc-one', 'oc-two'])
            inspect.assert_not_called()


if __name__ == '__main__':
    unittest.main()
