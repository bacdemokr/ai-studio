import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts'), str(Path(__file__).resolve().parent)]
from studio import Studio, Problem
from test_studio import Adapter
import agent_runtime as runtime
import agent_policy as policy


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.adapter = Adapter()
        self.studio = Studio(self.temp.name, self.adapter, start_worker=False)
        self.account, _ = self.studio.session()
        self.owner = self.account['id']
        self.profile = {'name': 'Orbit', 'persona': 'guide', 'skills': ['weather', 'web', 'memory'], 'protection': 'openshell'}
        self.studio.onboard(self.owner, self.profile)
        runtime._expected_identity.clear()
        self.addCleanup(runtime._expected_identity.clear)

    def tearDown(self):
        self.temp.cleanup()

    def run_job(self, data):
        job = self.studio.enqueue(self.owner, data)
        row = self.studio.next_job()
        try:
            self.studio.execute(row)
        except RuntimeError as error:
            self.studio.event(row['id'], 'Mission needs attention', str(error), status='error', result=json.dumps({'error': str(error)}))
        return self.studio.evidence(self.owner, job['id'])['mission']

    def test_prepare_workspace_reuses_saved_approvals_without_adding_access(self):
        self.assertEqual(self.studio.policy_report(self.owner)['status'],'awaiting-first-mission')
        with patch.object(self.adapter,'policy_prepare',wraps=self.adapter.policy_prepare) as prepare:
            self.assertEqual(self.studio.policy_change(self.owner,{'retry':True}),{'applied':True})
            prepare.assert_called_once_with('bac-'+self.owner)
        report=self.studio.policy_report(self.owner)
        self.assertEqual(report['status'],'applied')
        self.assertEqual(report['requested'],[])
        self.assertEqual(self.adapter.permissions['bac-'+self.owner],[])
        self.assertEqual(self.adapter.calls,[])

    def test_protected_weather_denied_approved_then_revoked_with_scoped_history(self):
        self.assertEqual(self.studio.policy_report(self.owner)['status'], 'awaiting-first-mission')
        result = self.run_job({'prompt': 'Check weather'})
        self.assertEqual(result['status'], 'error')
        self.assertEqual(self.studio.policy_report(self.owner)['logs'][0]['action'], 'deny')
        self.studio.policy_change(self.owner, {'permission': 'weather', 'allow': True})
        report = self.studio.policy_report(self.owner)
        self.assertEqual(report['status'], 'applied')
        self.assertEqual(report['requested'], policy.individual_permissions(['weather']))
        self.assertEqual({r['host'] for r in report['rules']}, set(policy.CATALOG['weather']['hosts']))
        self.assertEqual(self.run_job({'prompt': 'Check weather'})['status'], 'done')
        self.studio.policy_change(self.owner, {'permission': 'weather', 'allow': False})
        self.assertEqual(self.run_job({'prompt': 'Check weather'})['status'], 'error')
        self.assertEqual(len(self.studio.policy_report(self.owner)['history']), 2)
        other = self.studio.add_agent(self.owner, {**self.profile, 'name': 'Other'})['agentId']
        self.assertEqual(self.studio.policy_report(other)['requested'], [])
        self.assertEqual(self.studio.policy_report(other)['logs'], [])

    def test_preset_crew_is_separate_from_protected_personal_agent_and_needs_no_onboarding(self):
        # Hiring now prepares the personal runtime independently of event work.
        self.studio.execute(self.studio.next_job())
        result = self.run_job({'kind': 'crew', 'preset': True, 'brief': {}})
        self.assertEqual(result['status'], 'done')
        self.assertEqual([m['name'] for m in result['payload']['roster']], [role['name'] for role in json.loads((Path(__file__).resolve().parents[1]/'src/crew-catalog.json').read_text())])
        self.assertTrue(all(m['protection'] == ('openshell' if i == 1 else 'standard') and m['key'] is None for i,m in enumerate(result['payload']['roster'])))
        self.assertFalse(any(call[0] == 'bac-' + self.owner for call in self.adapter.calls))
        self.assertEqual(self.studio.policy_report(self.owner)['requested'], [])
        self.assertTrue(all(p['protection'] == ('openshell' if key.endswith('-r1') else 'standard') for key,p in self.adapter.profiles.items() if key != 'bac-' + self.owner))
        account, _ = self.studio.session()
        job = self.studio.enqueue(account['id'], {'kind': 'crew', 'preset': True, 'brief': {}})
        self.studio.execute(self.studio.next_job())
        self.assertEqual(self.studio.evidence(account['id'], job['id'])['mission']['status'], 'done')
        self.assertIsNone(self.studio.state(account['id'])['profile'])

    def test_custom_crew_preserves_protected_member_and_modes_cannot_change_while_assigned(self):
        other = self.studio.add_agent(self.owner, {**self.profile, 'name': 'Other', 'protection': 'standard'})['agentId']
        job = self.studio.enqueue(other, {'kind': 'crew', 'brief': {}, 'members': {'1': self.owner}})
        self.assertEqual(self.studio.state(other)['jobs'][0]['payload']['roster'][1]['protection'], 'openshell')
        with self.assertRaises(Problem):
            self.studio.policy_change(self.owner, {'mode': 'standard'})
        with self.assertRaises(Problem):
            self.studio.policy_change(self.owner, {'permission': 'weather', 'allow': True})
        self.studio.decision(other, job['id'], 'cancel')
        with self.assertRaises(Problem):
            self.studio.policy_change(self.owner, {'mode': 'standard'})
        self.assertEqual(self.studio.profile(self.owner)['protection'], 'openshell')

    def test_failure_keeps_requested_and_applied_state_distinct_and_is_retryable(self):
        self.run_job({'prompt': 'Check weather'})
        with patch.object(self.adapter, 'policy_apply', side_effect=RuntimeError('host unavailable')):
            with self.assertRaises(Problem):
                self.studio.policy_change(self.owner, {'permission': 'weather', 'allow': True})
        report = self.studio.policy_report(self.owner)
        self.assertEqual(report['status'], 'needs-review')
        self.assertEqual(report['requested'], policy.individual_permissions(['weather']))
        self.assertEqual(report['rules'], [])
        before = len(self.adapter.calls)
        with patch.object(self.adapter, 'policy_apply', side_effect=RuntimeError('still unavailable')):
            self.assertEqual(self.run_job({'prompt': 'Check weather'})['status'], 'error')
        self.assertEqual(len(self.adapter.calls), before)  # Never send to an unverified runtime.
        self.studio.policy_change(self.owner, {'retry': True})
        self.assertEqual(self.studio.policy_report(self.owner)['status'], 'applied')
        self.assertEqual(self.run_job({'prompt': 'Check weather'})['status'], 'done')

    def test_policy_update_fences_writes_and_deletion(self):
        with self.studio.db() as db:
            db.execute('INSERT INTO agent_policies (owner,updating) VALUES (?,1)', (self.owner,))
        for callback in (lambda: self.studio.delete_agent(self.owner, {'name': 'Orbit'}),
                         lambda: self.studio.policy_change(self.owner, {'mode': 'standard'}),
                         lambda: self.studio.enqueue(self.owner, {'prompt': 'hello'})):
            with self.assertRaises(Problem):
                callback()

    def test_busy_agent_rejects_policy_change_before_native_lookup(self):
        self.studio.enqueue(self.owner, {'prompt': 'Check weather'})
        with patch.object(self.adapter, 'policy_status') as status, patch.object(self.adapter, 'policy_apply') as apply:
            with self.assertRaises(Problem):
                self.studio.policy_change(self.owner, {'permission': 'weather', 'allow': True})
            status.assert_not_called()
            apply.assert_not_called()
        with self.studio.db() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM agent_policies WHERE owner=?', (self.owner,)).fetchone())

    def test_concurrent_approval_changes_have_one_writer(self):
        import threading
        entered, release = threading.Event(), threading.Event()
        outcomes = []
        original = self.adapter.policy_apply
        def paused(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('Test did not release writer')
            return original(*args)
        def first():
            try:
                outcomes.append(self.studio.policy_change(self.owner, {'permission': 'weather', 'allow': True}))
            except Exception as error:
                outcomes.append(error)
        with patch.object(self.adapter, 'policy_apply', side_effect=paused):
            worker = threading.Thread(target=first)
            worker.start()
            try:
                self.assertTrue(entered.wait(5))
                with patch.object(self.adapter, 'policy_status') as status:
                    with self.assertRaises(Problem):
                        self.studio.policy_change(self.owner, {'permission': 'papers', 'allow': True})
                    status.assert_not_called()
            finally:
                release.set()
                worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(outcomes, [{'applied': True}])
        self.assertEqual(self.studio.policy_report(self.owner)['requested'], policy.individual_permissions(['weather']))
        with self.studio.db() as db:
            self.assertEqual(db.execute('SELECT updating FROM agent_policies WHERE owner=?', (self.owner,)).fetchone()['updating'], 0)

    def test_native_standard_and_protected_tool_paths_and_config_barrier(self):
        with patch('agent_runtime.root', return_value=Path(self.temp.name) / 'native'):
            runtime.save_config(runtime.initial_config())
            native_id = 'bac-' + self.owner
            with patch('agent_policy.configured', return_value=True):
                runtime.register(native_id, self.studio.workspace(self.owner), self.profile)
            config = json.loads(runtime.config_path().read_text())
            entry = config['agents']['entries'][native_id]
            self.assertEqual(entry['sandbox'], {'mode':'all','backend':'openshell','scope':'agent','workspaceAccess':'rw'})
            self.assertIn('exec', entry['tools']['allow'])
            self.assertNotIn('exec', config['tools']['deny'])
            self.assertEqual(entry['tools']['exec']['host'], 'sandbox')
            self.assertEqual(set(entry['tools']['deny']), {'web_fetch', 'web_search'})
            self.assertNotIn('web_fetch', entry['tools']['allow'])
            self.assertIn('/usr/bin/curl', (self.studio.workspace(self.owner) / 'skills/bac-weather/SKILL.md').read_text())
            expected = entry['identity']['theme']
            with patch('agent_runtime.live_agents', side_effect=[RuntimeError('transient gateway read timeout'), {'agents':[{'id':native_id,'identity':{'theme':'old'}}]}, {'agents':[{'id':native_id,'identity':{'theme':expected}}]}]) as cli, patch('agent_runtime.gateway', side_effect=[{'data':[{'id':'openclaw/'+native_id}]},{'choices':[{'message':{'content':'done'}}]}]) as gateway, patch('agent_runtime.time.sleep'):
                self.assertEqual(runtime.respond(native_id, 'session', 'hello'), 'done')
                self.assertEqual(cli.call_count, 3)
                self.assertEqual(gateway.call_count, 2)
            runtime.register(native_id, self.studio.workspace(self.owner), {**self.profile, 'protection':'standard'})
            entry = json.loads(runtime.config_path().read_text())['agents']['entries'][native_id]
            self.assertEqual(entry['sandbox']['mode'], 'off')
            self.assertIn('exec', entry['tools']['deny'])
            self.assertIn('web_fetch', entry['tools']['allow'])

    def test_protected_registration_without_backend_fails_closed(self):
        with patch('agent_runtime.root', return_value=Path(self.temp.name) / 'native'):
            runtime.save_config(runtime.initial_config())
            with patch('agent_policy.configured', return_value=False), patch('ops_runtime.openshell', side_effect=RuntimeError('unavailable')), self.assertRaises(RuntimeError):
                runtime.register('bac-' + self.owner, self.studio.workspace(self.owner), self.profile)
            self.assertEqual(json.loads(runtime.config_path().read_text())['agents']['entries'], {})

    def test_protected_setup_runs_once_and_verifies_before_registration(self):
        with patch('agent_runtime.root', return_value=Path(self.temp.name) / 'native'), \
                patch('agent_policy.configured', side_effect=[False, False, True]), \
                patch('ops_runtime.openshell') as setup:
            runtime.ensure_openshell()
            setup.assert_called_once_with('enable', automatic=True)
        with patch('agent_policy.configured', return_value=True), patch('ops_runtime.openshell') as setup:
            runtime.ensure_openshell()
            setup.assert_not_called()

    def test_host_setup_is_repeatable_and_preserves_gateway_selection(self):
        import ops_common as c
        import ops_runtime as ops
        with patch('agent_runtime.root', return_value=Path(self.temp.name) / 'native'):
            package = runtime.root() / 'state/extensions/openshell'
            c.write_json(package / 'package.json', {'version': runtime.VERSION})
            config = runtime.initial_config()
            config['agents']['defaults']['sandbox'] = {'mode': 'all', 'backend': 'openshell'}
            config['plugins']['entries']['openshell'] = {'enabled': True, 'config': {
                'gateway': 'workshop-host', 'workspace': 'demo', 'mode': 'remote', 'autoProviders': True}}
            runtime.save_config(config)
            with patch('ops_runtime.shutil.which', return_value='/test/openshell'), patch.object(c, 'run'), \
                    patch.object(c, 'service'), patch('ops_runtime.subprocess.run'), patch('ops_runtime.time.sleep'), patch.object(runtime, 'gateway', return_value={}), patch.object(runtime, 'cli', return_value='valid') as cli:
                ops.openshell('enable')
                ops.openshell('enable')
            self.assertEqual([call.args for call in cli.call_args_list], [('config', 'validate'), ('gateway', 'restart', '--safe')] * 2)
            result = c.read_json(runtime.config_path())
            self.assertEqual(result['agents']['defaults']['sandbox'], {'mode': 'off'})
            settings = result['plugins']['entries']['openshell']['config']
            self.assertEqual((settings['gateway'], settings['workspace'], settings['mode']), ('workshop-host', 'demo', 'mirror'))
            self.assertIs(settings['autoProviders'], False)
            self.assertEqual(c.read_json(policy.default_path()), policy.policy_document())
            with patch('agent_policy.shutil.which', return_value='/test/openshell'):
                self.assertTrue(policy.configured())
                policy.default_path().write_text('{ broken json')
                self.assertFalse(policy.configured())

    def test_filesystem_report_does_not_claim_enforcement_or_hide_drift(self):
        native_id = 'bac-' + self.owner
        config = {'agents': {'entries': {native_id: {'sandbox': {'mode': 'all'}}}}}
        with patch('agent_policy.configured', return_value=True), patch('agent_policy.c.read_json', return_value=config), \
                patch('agent_policy.runtimes', return_value=[{'containerName': 'oc-first', 'running': True}]), \
                patch('agent_policy.public_logs', return_value=[]):
            document = policy.policy_document()
            report = {'policy': document, 'loaded': True, 'version': 1}
            with patch('agent_policy.read_policy', return_value=report):
                result = policy.inspect(native_id, 'openshell')
            self.assertEqual(result['filesystem']['status'], 'policy-loaded')
            self.assertEqual(result['filesystem']['observed'][0]['policy']['read_write'], ['/sandbox', '/agent', '/tmp', '/dev/null'])
            self.assertNotIn('enforced', result['filesystem'])
            document['filesystem_policy']['read_write'].append('/')
            with patch('agent_policy.read_policy', return_value=report):
                result = policy.inspect(native_id, 'openshell')
            self.assertEqual(result['filesystem']['status'], 'needs-review')
            self.assertEqual(result['status'], 'needs-review')
            self.assertFalse(result['filesystem']['observed'][0]['matchesConfigured'])

    def test_read_policy_requires_loaded_revision_and_matching_sandbox(self):
        effective={'sandbox':'oc-example','version':4,'policy_source':'sandbox','policy':policy.policy_document()}
        for state, expected in [('loaded',True),('pending',False),('failed',False)]:
            with patch('agent_policy.shell', side_effect=[json.dumps(effective),json.dumps({'version':4,'active_version':4,'status':state})]):
                self.assertEqual(policy.read_policy('oc-example')['loaded'], expected)
        with patch('agent_policy.shell', return_value=json.dumps({**effective,'sandbox':'someone-else'})), self.assertRaises(RuntimeError):
            policy.read_policy('oc-example')

    def test_runtime_mapping_and_public_log_redaction(self):
        aid='bac-'+self.owner
        with patch('agent_policy.sandbox_registry',return_value={'containers':[
            {'backendId':'openshell','sessionKey':'agent:'+aid,'containerName':'oc-first'},
            {'backendId':'openshell','sessionKey':'agent:'+aid+':extra','containerName':'oc-second'},
            {'backendId':'openshell','sessionKey':'agent:'+aid+'bad','containerName':'oc-unrelated'},
            {'backendId':'docker','sessionKey':'agent:'+aid,'containerName':'other'}]}), patch('agent_policy.shell',return_value='{"phase":"Ready"}') as probe:
            self.assertEqual([x['containerName'] for x in policy.runtimes(aid)], ['oc-first','oc-second'])
            self.assertEqual([c.args[2] for c in probe.call_args_list], ['oc-first','oc-second'])
        line='action=deny host=api.open-meteo.com binary=/usr/bin/curl secret=DO_NOT_SHOW'
        with patch('agent_policy.shell',return_value=line):
            events=policy.public_logs('oc-first')
        self.assertEqual(events[0]['action'],'deny')
        self.assertNotIn('DO_NOT_SHOW',json.dumps(events))
        self.assertEqual(policy.policy_document()['network_policies'],{})
        self.assertEqual({row['host'] for row in policy.network_rows(policy.policy_document(['weather']))},
                         {'api.open-meteo.com', 'geocoding-api.open-meteo.com', 'wttr.in'})
        with self.assertRaises(ValueError):policy.policy_document(['evil.example'])


    def test_scoped_health_never_confuses_missing_stopped_and_unreachable(self):
        import subprocess
        aid='bac-'+self.owner
        entry={'backendId':'openshell','sessionKey':'agent:'+aid+':main','containerName':'oc-owned'}
        with patch('agent_policy.sandbox_registry',return_value={'containers':[entry]}), patch('agent_runtime.cli') as global_scan:
            with patch('agent_policy.shell',return_value='{"phase":"Stopped"}'):
                self.assertFalse(policy.runtimes(aid)[0]['running'])
            with patch('agent_policy.shell',side_effect=RuntimeError('not found')), patch('agent_policy.sandbox_names',return_value=set()):
                self.assertFalse(policy.runtimes(aid)[0]['running'])
            with patch('agent_policy.shell',side_effect=RuntimeError('offline')), patch('agent_policy.sandbox_names',side_effect=RuntimeError('offline')):
                with self.assertRaises(RuntimeError):policy.runtimes(aid)
            with patch('agent_policy.shell',side_effect=subprocess.TimeoutExpired('get',35)):
                with self.assertRaises(subprocess.TimeoutExpired):policy.runtimes(aid)
            with patch('agent_policy.shell',return_value='{"phase":"Ready","name":"oc-unrelated"}'):
                with self.assertRaises(RuntimeError):policy.runtimes(aid)
            global_scan.assert_not_called()

    def test_missing_native_runtime_waits_for_creation_but_unreachable_gateway_blocks(self):
        native={'containerName':'oc-missing','running':False}
        config={'agents':{'entries':{'bac-'+self.owner:{'sandbox':{'mode':'all'}}}}}
        with patch('agent_policy.configured',return_value=True), patch('agent_policy.c.read_json',return_value=config), patch('agent_policy.runtimes',return_value=[native]), patch('agent_policy.sandbox_names',return_value=set()) as inventory:
            self.assertEqual(policy.inspect('bac-'+self.owner,'openshell')['status'],'awaiting-first-mission')
            inventory.side_effect=RuntimeError('unreachable')
            self.assertEqual(policy.inspect('bac-'+self.owner,'openshell')['status'],'unavailable')
            inventory.side_effect=None
            inventory.return_value={'oc-missing'}
            with patch('agent_policy.read_policy',side_effect=RuntimeError('unverified')):
                self.assertEqual(policy.inspect('bac-'+self.owner,'openshell')['status'],'unavailable')

    def test_preflight_retries_only_a_timeout_and_keeps_protection_required(self):
        from studio_policy import ProtectionNotVerified
        profile=self.studio.profile(self.owner)
        timeout={'status':'unavailable','checkFailure':'timeout'}
        applied={'status':'applied'}
        with patch.object(self.studio,'policy_report',side_effect=[timeout,applied]) as report, patch.object(self.adapter,'policy_apply') as apply:
            self.assertEqual(self.studio.check_protected_run(self.owner,profile),applied)
            self.assertEqual(report.call_count,2);apply.assert_not_called()
        with patch.object(self.studio,'policy_report',return_value=timeout) as report:
            with self.assertRaises(ProtectionNotVerified):self.studio.check_protected_run(self.owner,profile)
            self.assertEqual(report.call_count,2)
        with patch.object(self.studio,'policy_report',return_value={'status':'unavailable','checkFailure':'read-failed'}) as report:
            with self.assertRaises(ProtectionNotVerified):self.studio.check_protected_run(self.owner,profile)
            self.assertEqual(report.call_count,1)

    def test_protection_cannot_be_changed_through_edit(self):
        with self.assertRaises(Problem):
            self.studio.configure(self.owner, {**self.profile, 'protection': 'standard'})
        self.studio.configure(self.owner, {**self.profile, 'name': 'Still protected'})
        self.assertEqual(self.studio.profile(self.owner)['protection'], 'openshell')

    def test_requested_hosts_are_scoped_explicit_and_revocable(self):
        self.run_job({'prompt': 'can you access www.naver.com?'})
        key = 'host:www.naver.com'
        report = self.studio.policy_report(self.owner)
        self.assertIn(key, report['catalog'])
        self.assertNotIn(key, report['requested'])
        self.studio.policy_change(self.owner, {'permission': key, 'allow': True})
        report = self.studio.policy_report(self.owner)
        self.assertEqual(report['requested'], [key])
        self.assertEqual([r['host'] for r in report['rules']], ['www.naver.com'])
        other = self.studio.add_agent(self.owner, {**self.profile, 'name': 'Other'})['agentId']
        self.assertNotIn(key, self.studio.policy_report(other)['catalog'])
        with self.assertRaises(Problem):
            self.studio.policy_change(other, {'permission': key, 'allow': True})
        self.studio.policy_change(self.owner, {'permission': key, 'allow': False})
        self.assertEqual(self.studio.policy_report(self.owner)['requested'], [])
        for host in ['*.naver.com', '127.0.0.1', 'localhost', 'metadata.internal', 'naver.com:443', 'https://naver.com']:
            with self.assertRaises(ValueError):
                policy.destination_permission(host)

    def test_verified_denials_offer_redirect_host_without_claiming_http_error_is_denial(self):
        self.adapter.policy_logs[self.studio.profile(self.owner)['id']] = [{'host': 'nid.naver.com', 'action': 'deny'}]
        self.assertIn('host:nid.naver.com', self.studio.policy_report(self.owner)['catalog'])

    def test_native_ocsf_denial_host_is_parsed(self):
        log = '[sandbox] [OCSF ] [ocsf] NET:OPEN [MED] DENIED /usr/bin/curl(806) -> www.naver.com:443 [reason:network connections not allowed by policy]'
        with patch('agent_policy.shell', return_value=log):
            entries = policy.public_logs('this-agent')
        self.assertEqual(entries[0]['host'], 'www.naver.com')
        self.assertEqual(entries[0]['action'], 'deny')
        with patch('agent_policy.shell', return_value='HTTP 403 from www.naver.com'):
            self.assertEqual(policy.public_logs('this-agent'), [])

    def test_dns_and_destination_failures_do_not_become_approval_requests(self):
        self.run_job({'prompt': 'Check weather'})
        now = time.time()
        lines = [
            f'[{now}] [sandbox] NET:OPEN [MED] DENIED /usr/bin/curl(12) -> api.open-meteo.com:443 [engine:ssrf] [reason:DNS resolution failed: Try again]',
            f'[{now}] [sandbox] NET:OPEN [MED] DENIED /usr/bin/curl(12) -> example.com:443 [engine:ssrf] [reason:blocked destination address]',
            f'[{now}] [sandbox] NET:OPEN [MED] DENIED /usr/bin/curl(12) -> arxiv.org:443 [engine:opa] [reason:network connections not allowed by policy]']
        with patch('agent_policy.shell', return_value='\n'.join(lines)):
            events = policy.public_logs('oc-owned')
        self.adapter.policy_logs[self.studio.profile(self.owner)['id']] = events
        report = self.studio.policy_report(self.owner)
        self.assertEqual(report['pendingAccess'], [{'host': 'arxiv.org', 'reason': 'blocked'}])
        self.assertEqual({e['reason'] for e in report['connectionIssues']}, {'dns-failed', 'destination-blocked'})
        self.assertEqual(len(report['recentDenied']), 1)
        self.assertNotIn('host:example.com', report['catalog'])

    def test_http_ocsf_denial_appears_in_latest_conversation(self):
        self.run_job({'prompt': "What's the weather like today?"})
        now = time.time()
        log = (f'[{now}] [sandbox] [OCSF ] [ocsf] HTTP:GET [MED] DENIED '
               '/usr/bin/curl(173) -> GET http://wttr.in/Zurich '
               '[policy:- engine:opa] [reason:network connections not allowed by policy]')
        with patch('agent_policy.shell', return_value=log):
            entries = policy.public_logs('this-agent')
        self.adapter.policy_logs[self.studio.profile(self.owner)['id']] = entries
        report = self.studio.policy_report(self.owner)
        self.assertEqual(report['pendingAccess'], [{'host': 'wttr.in', 'reason': 'blocked'}])
        self.assertEqual(report['requested'], [])
        self.assertEqual(entries[0]['time'], now)
        self.assertEqual(entries[0]['binary'], '/usr/bin/curl')
        with patch('agent_policy.shell', return_value=log.replace('DENIED', 'ALLOWED')):
            self.assertEqual(policy.public_logs('this-agent')[0]['action'], 'allow')

    def test_scout_backtick_destination_is_only_a_suggestion(self):
        job = self.studio.enqueue(self.owner, {'prompt': "What's the weather like today?"})
        self.studio.decision(self.owner, job['id'], 'cancel')
        answers = [
            ("If you want me to fetch the current weather, you can approve a destination like "
             "`wttr.in` in the OpenShell Policies tab, and I'll be right on it.",
             [{'host': 'wttr.in', 'reason': 'suggested'}]),
            ('Weather reference: `wttr.in`.', []),
            ('Please approve **api.open-meteo.com**.', [{'host':'api.open-meteo.com','reason':'suggested'}]),
            ('Please approve `127.0.0.1`, `metadata.internal`, and `*.example.com`.', []),
        ]
        for answer, expected in answers:
            with self.subTest(answer=answer):
                with self.studio.db() as db:
                    db.execute('UPDATE jobs SET result=? WHERE id=?', (json.dumps({'answer': answer}), job['id']))
                report = self.studio.policy_report(self.owner)
                self.assertEqual(report['pendingAccess'], expected)
                self.assertEqual(report['recentDenied'], [])
                self.assertEqual(report['requested'], [])

    def test_latest_conversation_filters_old_denials(self):
        self.run_job({'prompt': 'can you access www.naver.com?'})
        with self.studio.db() as db:
            created = db.execute('SELECT created FROM jobs WHERE owner=? ORDER BY created DESC LIMIT 1', (self.owner,)).fetchone()['created']
        self.adapter.policy_logs[self.studio.profile(self.owner)['id']] = [
            {'host': 'www.naver.com', 'action': 'deny', 'time': created + 1},
            {'host': 'old.example.com', 'action': 'deny', 'time': created - 20},
            {'host': 'allowed.example.com', 'action': 'allow', 'time': created + 1}]
        self.assertEqual([e['host'] for e in self.studio.policy_report(self.owner)['recentDenied']], ['www.naver.com'])

    def test_approval_request_without_tool_denial_is_visible_and_can_be_saved(self):
        job = self.studio.enqueue(self.owner, {'prompt': 'can you access www.naver.com?'})
        self.studio.decision(self.owner, job['id'], 'cancel')
        report = self.studio.policy_report(self.owner)
        self.assertEqual(report['recentDenied'], [])
        self.assertEqual(report['pendingAccess'], [{'host': 'www.naver.com', 'reason': 'requested'}])
        result = self.studio.policy_change(self.owner, {'permission': 'host:www.naver.com', 'allow': True})
        self.assertTrue(result['applied'])
        self.assertEqual(self.studio.policy_report(self.owner)['pendingAccess'], [])
        self.assertEqual(self.adapter.permissions[self.studio.profile(self.owner)['id']], ['host:www.naver.com'])
        self.studio.ensure_agent(self.owner, self.studio.profile(self.owner))
        self.studio.check_protected_run(self.owner, self.studio.profile(self.owner))
        self.assertEqual(self.adapter.permissions[self.studio.profile(self.owner)['id']], ['host:www.naver.com'])

    def test_answer_approval_destinations_are_candidates_not_denials(self):
        job = self.studio.enqueue(self.owner, {'prompt': 'Find recent agentic AI papers'})
        self.studio.decision(self.owner, job['id'], 'cancel')
        answer = ('The source returned HTTP 403.\n\nPlease approve these research destinations in Policies:\n\n'
                  '- [https://export.arxiv.org](https://export.arxiv.org) — metadata\n'
                  '- [https://arxiv.org](https://arxiv.org) — abstracts\n\n'
                  'Other citation: https://example.com')
        with self.studio.db() as db:
            db.execute('UPDATE jobs SET result=? WHERE id=?', (json.dumps({'answer': answer}), job['id']))
        report = self.studio.policy_report(self.owner)
        self.assertEqual(report['pendingAccess'], [
            {'host': 'export.arxiv.org', 'reason': 'suggested'},
            {'host': 'arxiv.org', 'reason': 'suggested'}])
        self.assertEqual(report['recentDenied'], [])
        self.assertEqual(report['requested'], [])
        self.studio.policy_change(self.owner, {'permission': 'host:export.arxiv.org', 'allow': True})
        self.assertEqual(self.studio.policy_report(self.owner)['pendingAccess'],
                         [{'host': 'arxiv.org', 'reason': 'suggested'}])
        with self.studio.db() as db:
            db.execute('UPDATE jobs SET result=? WHERE id=?',
                       (json.dumps({'answer': 'HTTP 403 from https://arxiv.org. Reference https://example.com'}), job['id']))
        self.assertEqual(self.studio.policy_report(self.owner)['pendingAccess'], [])

    def test_preparation_failure_never_calls_model_or_claims_approval(self):
        with patch.object(self.adapter, 'policy_prepare', side_effect=RuntimeError('OpenShell unavailable')):
            with self.assertRaises(Problem):
                self.studio.policy_change(self.owner, {'permission': 'weather', 'allow': True})
        self.assertEqual(self.adapter.calls, [])
        self.assertEqual(self.studio.policy_report(self.owner)['status'], 'needs-review')

    def test_unverified_apply_is_not_success(self):
        self.studio.ensure_agent(self.owner, self.studio.profile(self.owner))
        with patch.object(self.adapter, 'policy_apply', return_value={'status': 'needs-review'}):
            with self.assertRaises(Problem):
                self.studio.policy_change(self.owner, {'permission': 'weather', 'allow': True})
        self.assertEqual(self.studio.policy_report(self.owner)['status'], 'needs-review')

if __name__=='__main__':unittest.main()
