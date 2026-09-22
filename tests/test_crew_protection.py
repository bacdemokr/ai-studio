import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from test_studio import Adapter
from studio import Studio
from studio_policy import ProtectionNotVerified
import research_http as http
import agent_runtime as runtime


class CrewProtectionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.adapter = Adapter()
        self.studio = Studio(directory.name, self.adapter, start_worker=False)
        self.owner = self.studio.session()[0]['id']
        with self.studio.db() as db:
            self.members = self.studio.crew_roster(db, self.owner, {}, True)

    def test_only_dylan_gets_verified_research_access_before_any_model_call(self):
        for role, member in enumerate(self.members[:4]):
            report = self.studio.prepare_builtin_crew(self.owner, role, member)
            self.assertEqual(bool(report), role == 1)
        self.assertEqual(self.adapter.calls, [])
        self.assertEqual(self.adapter.permissions, {self.members[1]['id']: list(http.RESEARCH_APPROVALS)})
        with self.studio.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM agent_policies').fetchone()[0], 0)

    def test_saved_standard_roster_is_upgraded_and_drift_repaired_before_reuse(self):
        member = self.members[1]
        member['protection'] = 'standard'
        self.studio.prepare_builtin_crew(self.owner, 1, member)
        self.assertEqual(self.adapter.profiles[member['id']]['protection'], 'openshell')
        self.adapter.permissions[member['id']] = ['host:example.com']
        self.studio.prepare_builtin_crew(self.owner, 1, member)
        self.assertEqual(self.adapter.permissions[member['id']], list(http.RESEARCH_APPROVALS))

    def test_verified_reuse_does_not_reapply_policy(self):
        member = self.members[1]
        self.studio.prepare_builtin_crew(self.owner, 1, member)
        with patch.object(self.adapter, 'policy_apply', side_effect=AssertionError('Unnecessary mutation')):
            self.assertEqual(self.studio.prepare_builtin_crew(self.owner, 1, member)['status'], 'applied')

    def test_unverified_policy_stops_chat_without_model_or_host_fallback(self):
        with patch.object(self.adapter, 'policy_apply', return_value={'status':'unavailable'}):
            with self.assertRaises(ProtectionNotVerified):
                self.studio.crew_chat({'owner':self.owner,'id':'fixture'}, {'crewRole':1,'prompt':'Find current themes'})
        self.assertEqual(self.adapter.calls, [])

    def test_native_config_uses_sandbox_exec_and_can_write_deliverables(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runtime, 'root', return_value=Path(directory)), patch.object(runtime, 'ensure_openshell'):
            runtime.save_config(runtime.initial_config())
            member = self.members[1]
            workspace = Path(directory) / 'workspace'
            runtime.register(member['id'], workspace, member, member['role'])
            entry = json.loads(runtime.config_path().read_text())['agents']['entries'][member['id']]
            self.assertEqual(entry['sandbox']['backend'], 'openshell')
            self.assertEqual(entry['tools']['exec']['host'], 'sandbox')
            self.assertTrue({'read','write','edit','exec'} <= set(entry['tools']['allow']))
            self.assertTrue({'web_fetch','web_search'} <= set(entry['tools']['deny']))
            self.assertTrue((workspace/'skills/bac-event-tools/scripts/research_http.py').exists())

    def test_legacy_host_research_is_rejected_for_protected_dylan(self):
        self.studio.enqueue(self.owner, {'kind':'crew','preset':True,'workflow':'showcase',
                                        'brief':{'schema':2,'themeCount':3}})
        with patch('nvidia_research.discover', side_effect=AssertionError('Host bypass')):
            with self.assertRaisesRegex(RuntimeError, 'No host research was performed'):
                self.studio.execute(self.studio.next_job())

    def test_l7_denial_without_arrow_is_visible_in_policy_evidence(self):
        import agent_policy as policy
        log = '[1790069339.766] [sandbox] [OCSF ] [ocsf] HTTP:POST [MED] DENIED POST http://blogs.nvidia.com:443/ [policy:research engine:l7] [reason:L7_REQUEST deny POST blogs.nvidia.com:443/ reason=POST / not permitted by policy]'
        with patch.object(policy, 'shell', return_value=log):
            row = policy.public_logs('test')[0]
        self.assertEqual((row['host'], row['action'], row['reason']), ('blogs.nvidia.com','deny','policy-denied'))


class ResearchHTTPTests(unittest.TestCase):
    def response(self, status=200, body=b'content', location=None):
        def run(args, **kwargs):
            self.assertEqual(args[:2], ['/usr/bin/curl','--disable'])
            self.assertNotIn('--location', args)
            self.assertNotIn('--insecure', args)
            Path(args[args.index('--output')+1]).write_bytes(body)
            headers = 'HTTP/1.1 %d Response\r\n' % status
            if location: headers += 'Location: '+location+'\r\n'
            Path(args[args.index('--dump-header')+1]).write_text(headers+'\r\n')
            return subprocess.CompletedProcess(args, 0, str(status), '')
        return run

    def test_fetch_and_same_origin_redirect(self):
        first = self.response(301, location='/blog/source/')
        second = self.response()
        calls = iter((first, second))
        with patch.object(http.subprocess, 'run', side_effect=lambda *a,**kw:next(calls)(*a,**kw)) as call:
            self.assertEqual(http.fetch('https://blogs.nvidia.com/blog/source'), b'content')
            self.assertEqual(call.call_count, 2)

    def test_redirect_outside_approved_origin_never_connects(self):
        with patch.object(http.subprocess, 'run', side_effect=self.response(302,location='https://example.com/')) as call:
            with self.assertRaises(ValueError): http.fetch('https://blogs.nvidia.com/')
            self.assertEqual(call.call_count, 1)

    def test_invalid_destinations_never_invoke_transport(self):
        with patch.object(http.subprocess, 'run', side_effect=AssertionError('Must not connect')):
            for url in ('http://blogs.nvidia.com/', 'https://blogs.nvidia.com:444/', 'https://user@blogs.nvidia.com/', 'https://example.com/', 'https://blogs.nvidia.com/\n'):
                with self.subTest(url=url), self.assertRaises(ValueError): http.fetch(url)

    def test_network_failure_is_not_retried_with_another_transport(self):
        failure = subprocess.CompletedProcess([], 56, '000', 'CONNECT tunnel failed, response 403')
        with patch.object(http.subprocess, 'run', return_value=failure) as call:
            with self.assertRaisesRegex(RuntimeError, 'curl 56'): http.fetch('https://blogs.nvidia.com/')
            self.assertEqual(call.call_count, 1)

    def test_response_size_is_bounded_even_when_curl_does_not_enforce_it(self):
        with patch.object(http.subprocess, 'run', side_effect=self.response(body=b'large')):
            with self.assertRaisesRegex(ValueError, 'size limit'): http.fetch('https://blogs.nvidia.com/',limit=2)
