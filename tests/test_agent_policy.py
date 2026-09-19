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

    def test_protected_weather_denied_approved_then_revoked_with_scoped_history(self):
        self.assertEqual(self.studio.policy_report(self.owner)['status'], 'awaiting-first-mission')
        result = self.run_job({'prompt': 'Check weather'})
        self.assertEqual(result['status'], 'error')
        self.assertEqual(self.studio.policy_report(self.owner)['logs'][0]['action'], 'deny')
        self.studio.policy_change(self.owner, {'permission': 'weather', 'allow': True})
        report = self.studio.policy_report(self.owner)
        self.assertEqual(report['status'], 'applied')
        self.assertEqual(report['requested'], ['weather'])
        self.assertEqual({r['host'] for r in report['rules']}, set(policy.CATALOG['weather']['hosts']))
        self.assertEqual(self.run_job({'prompt': 'Check weather'})['status'], 'done')
        self.studio.policy_change(self.owner, {'permission': 'weather', 'allow': False})
        self.assertEqual(self.run_job({'prompt': 'Check weather'})['status'], 'error')
        self.assertEqual(len(self.studio.policy_report(self.owner)['history']), 2)
        other = self.studio.add_agent(self.owner, {**self.profile, 'name': 'Other'})['agentId']
        self.assertEqual(self.studio.policy_report(other)['requested'], [])
        self.assertEqual(self.studio.policy_report(other)['logs'], [])

    def test_preset_crew_is_separate_from_protected_personal_agent_and_needs_no_onboarding(self):
        result = self.run_job({'kind': 'crew', 'preset': True, 'brief': {}})
        self.assertEqual(result['status'], 'done')
        self.assertEqual([m['name'] for m in result['payload']['roster']], ['Milo','Nova','Atlas','Momo','Pico'])
        self.assertTrue(all(m['protection'] == 'standard' and m['key'] is None for m in result['payload']['roster']))
        self.assertNotIn('bac-' + self.owner, self.adapter.agents)
        self.assertTrue(all(p['protection'] == 'standard' for p in self.adapter.profiles.values()))
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
        self.studio.policy_change(self.owner, {'mode': 'standard'})
        self.assertEqual(self.studio.profile(self.owner)['protection'], 'standard')
        self.assertEqual(self.run_job({'prompt': 'Check weather'})['status'], 'done')

    def test_failure_keeps_requested_and_applied_state_distinct_and_is_retryable(self):
        self.run_job({'prompt': 'Check weather'})
        with patch.object(self.adapter, 'policy_apply', side_effect=RuntimeError('host unavailable')):
            with self.assertRaises(Problem):
                self.studio.policy_change(self.owner, {'permission': 'weather', 'allow': True})
        report = self.studio.policy_report(self.owner)
        self.assertEqual(report['status'], 'needs-review')
        self.assertEqual(report['requested'], ['weather'])
        self.assertEqual(report['rules'], [])
        before = len(self.adapter.calls)
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
            with patch('agent_runtime.cli', side_effect=[json.dumps({'agents':[{'id':native_id,'identity':{'theme':'old'}}]}), json.dumps({'agents':[{'id':native_id,'identity':{'theme':expected}}]})]) as cli, patch('agent_runtime.gateway', side_effect=[{'data':[{'id':'openclaw/'+native_id}]},{'choices':[{'message':{'content':'done'}}]}]) as gateway, patch('agent_runtime.time.sleep'):
                self.assertEqual(runtime.respond(native_id, 'session', 'hello'), 'done')
                self.assertEqual(cli.call_count, 2)
                self.assertEqual(gateway.call_count, 2)
            runtime.register(native_id, self.studio.workspace(self.owner), {**self.profile, 'protection':'standard'})
            entry = json.loads(runtime.config_path().read_text())['agents']['entries'][native_id]
            self.assertEqual(entry['sandbox']['mode'], 'off')
            self.assertIn('exec', entry['tools']['deny'])
            self.assertIn('web_fetch', entry['tools']['allow'])

    def test_protected_registration_without_backend_fails_closed(self):
        with patch('agent_runtime.root', return_value=Path(self.temp.name) / 'native'):
            runtime.save_config(runtime.initial_config())
            with patch('agent_policy.configured', return_value=False), self.assertRaises(RuntimeError):
                runtime.register('bac-' + self.owner, self.studio.workspace(self.owner), self.profile)
            self.assertEqual(json.loads(runtime.config_path().read_text())['agents']['entries'], {})

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
                    patch.object(c, 'service'), patch.object(runtime, 'cli', return_value='valid') as cli:
                ops.openshell('enable')
                ops.openshell('enable')
            self.assertTrue(all(call.args == ('config', 'validate') for call in cli.call_args_list))
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

    def test_read_policy_requires_loaded_revision_and_matching_sandbox(self):
        effective={'sandbox':'oc-example','version':4,'policy_source':'sandbox','policy':policy.policy_document()}
        for state, expected in [('loaded',True),('pending',False),('failed',False)]:
            with patch('agent_policy.shell', side_effect=[json.dumps(effective),json.dumps({'version':4,'active_version':4,'status':state})]):
                self.assertEqual(policy.read_policy('oc-example')['loaded'], expected)
        with patch('agent_policy.shell', return_value=json.dumps({**effective,'sandbox':'someone-else'})), self.assertRaises(RuntimeError):
            policy.read_policy('oc-example')

    def test_runtime_mapping_and_public_log_redaction(self):
        aid='bac-'+self.owner
        with patch('agent_runtime.cli',return_value=json.dumps({'containers':[
            {'backendId':'openshell','sessionKey':'agent:'+aid,'containerName':'oc-first'},
            {'backendId':'openshell','sessionKey':'agent:'+aid+':extra','containerName':'oc-second'},
            {'backendId':'openshell','sessionKey':'agent:'+aid+'bad','containerName':'oc-unrelated'},
            {'backendId':'docker','sessionKey':'agent:'+aid,'containerName':'other'}]})):
            self.assertEqual([x['containerName'] for x in policy.runtimes(aid)], ['oc-first','oc-second'])
        line='action=deny host=api.open-meteo.com binary=/usr/bin/curl secret=DO_NOT_SHOW'
        with patch('agent_policy.shell',return_value=line):
            events=policy.public_logs('oc-first')
        self.assertEqual(events[0]['action'],'deny')
        self.assertNotIn('DO_NOT_SHOW',json.dumps(events))
        self.assertEqual(policy.policy_document()['network_policies'],{})
        self.assertEqual(len(policy.network_rows(policy.policy_document(['weather']))),2)
        with self.assertRaises(ValueError):policy.policy_document(['evil.example'])


if __name__=='__main__':unittest.main()
