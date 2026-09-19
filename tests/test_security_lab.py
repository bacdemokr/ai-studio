import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import security_lab as lab


class SecurityLabTests(unittest.TestCase):
    def test_denial_needs_matching_policy_evidence_not_network_error(self):
        logs = 'action=deny dst_host=api.github.com dst_port=443 binary=/usr/bin/curl'
        self.assertTrue(lab.classify('api.github.com', 'blocked', 56, 'BAC_HTTP=000', logs)['passed'])
        for unproven in ('', 'DNS error', logs.replace('api.github.com', 'api.github.com.evil'),
                         logs.replace('/usr/bin/curl', '/usr/bin/wget'), logs.replace('deny', 'allow')):
            self.assertFalse(lab.classify('api.github.com', 'blocked', 28, 'timeout', unproven)['passed'])
        self.assertFalse(lab.classify('api.github.com', 'blocked', 0, 'BAC_HTTP=200', logs)['passed'])

    def test_allowed_requires_http_success_and_log(self):
        logs = 'NET:OPEN [INFO] ALLOWED /usr/bin/curl(58) -> api.github.com:443 [policy:bac_public_read engine:opa]'
        self.assertTrue(lab.classify('api.github.com', 'allowed', 0, 'BAC_HTTP=200', logs)['passed'])
        self.assertFalse(lab.classify('api.github.com', 'allowed', 22, 'BAC_HTTP=403', logs)['passed'])
        self.assertFalse(lab.classify('api.github.com', 'allowed', 0, 'BAC_HTTP=200', '')['passed'])

    def test_operator_capture_fixed_scope_cleanup_and_no_credentials_in_public_report(self):
        with tempfile.TemporaryDirectory() as folder:
            calls = []
            def run(args, **kwargs):
                calls.append(args)
                out = ''
                code = 0
                if args[1:] == ['--version']:
                    out = 'TEST FIXTURE VERSION'
                elif args[1:3] == ['sandbox', 'ssh-config']:
                    out = 'Host proof-test\n  HostName localhost\n'
                elif args[0] == 'ssh' and 'curl' in args[-1]:
                    allowed = 'api.github.com' in args[-1] and any(c[1:3] == ['policy', 'set'] for c in calls)
                    out, code = ('BAC_HTTP=200', 0) if allowed else ('BAC_HTTP=000', 56)
                elif args[1] == 'logs':
                    out = '\n'.join('action='+a+' dst_host='+h+' binary=/usr/bin/curl' for a,h in [('deny','api.github.com'),('allow','api.github.com'),('deny','example.com')])
                return subprocess.CompletedProcess(args, code, out, '')
            with patch('security_lab.c.initialize', return_value=Path(folder)), patch('security_lab.shutil.which', return_value='/test/tool'), patch('security_lab.subprocess.run', side_effect=run), patch('security_lab.time.sleep'):
                lab.prove()
            report = lab.public_report(Path(folder) / 'studio')
            self.assertEqual(report['status'], 'captured')
            self.assertTrue(report['cleanedUp'])
            self.assertEqual(len(report['steps']), 3)
            self.assertEqual(report['version'], 'TEST FIXTURE VERSION')
            serialized = json.dumps(report)
            self.assertNotIn('HostName', serialized)
            self.assertNotIn('Authorization', serialized)
            self.assertTrue(any(c[1:3] == ['sandbox', 'delete'] for c in calls))
            self.assertFalse(any('POST' in ' '.join(c) for c in calls))

    def test_create_failure_publishes_incomplete_without_deleting_unknown_sandbox(self):
        with tempfile.TemporaryDirectory() as folder:
            def run(args, **kwargs):
                return subprocess.CompletedProcess(args, 1 if args[1:3] == ['sandbox', 'create'] else 0, '', '')
            with patch('security_lab.c.initialize', return_value=Path(folder)), patch('security_lab.shutil.which', return_value='/test/tool'), patch('security_lab.subprocess.run', side_effect=run):
                with self.assertRaises(RuntimeError):
                    lab.prove()
            report = lab.public_report(Path(folder) / 'studio')
            self.assertEqual(report['status'], 'incomplete')
            self.assertEqual(report['steps'], [])
            self.assertFalse(report['cleanedUp'])


if __name__ == '__main__':
    unittest.main()
