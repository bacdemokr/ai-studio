"""Reuse persisted registration without weakening live policy or edit barriers."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts'), str(Path(__file__).parent)]
import agent_runtime as runtime
from native_config_fixture import apply_config


class RegistrationReuseTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        env = patch.dict(os.environ, {'BAC_DATA_DIR': str(self.home)})
        env.start(); self.addCleanup(env.stop)
        proxy = patch('session_secrets.proxy_url', return_value='http://127.0.0.1:19000/provider/team/v1')
        proxy.start(); self.addCleanup(proxy.stop)
        expected = patch.dict(runtime._expected_identity, {}, clear=True)
        expected.start(); self.addCleanup(expected.stop)
        runtime.save_config(runtime.initial_config())
        self.agent = 'bac-' + 'a' * 24
        self.workspace = self.home / 'workspace'
        self.profile = {'name': 'Fixture', 'persona': 'guide', 'skills': ['builder']}
        gateway = patch.object(runtime, 'gateway_config_patch', side_effect=apply_config)
        self.apply = gateway.start(); self.addCleanup(gateway.stop)

    def register(self, **overrides):
        runtime.register(self.agent, self.workspace, {**self.profile, **overrides})

    def entry(self):
        return json.loads(runtime.config_path().read_text())['agents']['entries'][self.agent]

    def test_repeat_and_app_restart_skip_patch_but_preserve_live_identity_barrier(self):
        self.register()
        before = runtime.config_path().read_bytes()
        runtime._expected_identity.clear()  # An app restart loses this memory.
        self.register()
        self.assertEqual(self.apply.call_count, 1)
        self.assertEqual(runtime.config_path().read_bytes(), before)
        self.assertEqual(runtime._expected_identity[self.agent], self.entry()['identity']['theme'])
        self.assertFalse((self.workspace / '.bac-prepared-only').exists())

    def test_reused_registration_still_waits_for_live_policy_before_model_post(self):
        self.register(); self.register()
        expected = runtime._expected_identity[self.agent]
        posts = []
        def gateway(path, payload=None, **kwargs):
            if payload is not None:
                posts.append(payload)
                self.assertNotIn(self.agent, runtime._expected_identity)
                return {'choices': [{'message': {'content': 'Ready'}}]}
            return {'data': [{'id': 'openclaw/' + self.agent}]}
        with patch.object(runtime, 'live_agents', side_effect=[{'agents': []}, {
            'agents': [{'id': self.agent, 'identity': {'theme': expected}}]}]) as live, \
             patch.object(runtime, 'gateway', side_effect=gateway), \
             patch.object(runtime.time, 'sleep'), patch('user_location.context', return_value=''), \
             patch.object(runtime, 'observed_activity', return_value={'calls': []}), \
             patch.object(runtime, 'model_endpoint', return_value=None), \
             patch('telemetry.measure', return_value={}):
            self.assertEqual(runtime.respond(self.agent, 'reuse-test', 'Hello'), 'Ready')
        self.assertEqual(live.call_count, 2)
        self.assertEqual(len(posts), 1)

    def test_captain_mode_changes_still_replace_tools_and_publish_each_revision(self):
        self.agent += '-r0'
        for mode, allow, deny in [('none', [], ['*']), ('read', ['read'], []), ('none', [], ['*'])]:
            self.register(_planControl=mode)
            entry = self.entry()
            self.assertEqual(entry['tools']['allow'], allow)
            self.assertEqual(entry['tools']['deny'], deny)
            self.assertEqual(entry['skills'], [])
        self.assertEqual(self.apply.call_count, 3)

    def test_real_skill_instruction_edits_still_publish_a_new_identity(self):
        self.register()
        previous = self.entry()['identity']['theme']
        title, instruction = runtime.SKILLS['builder']
        with patch.dict(runtime.SKILLS, {'builder': (title, instruction + '\nNew guidance.')}):
            self.register()
        self.assertEqual(self.apply.call_count, 2)
        self.assertNotEqual(previous, self.entry()['identity']['theme'])

    def test_list_drift_is_repaired_even_when_saved_identity_stamp_matches(self):
        self.register()
        config = json.loads(runtime.config_path().read_text())
        config['agents']['entries'][self.agent]['tools']['allow'].append('exec')
        runtime.save_config(config)
        self.register()
        self.assertEqual(self.apply.call_count, 2)
        self.assertNotIn('exec', self.entry()['tools']['allow'])

    def test_connection_change_cannot_hide_behind_unchanged_identity_or_mutated_config(self):
        connection = {'baseUrl': 'https://first.example/v1', 'api': 'openai-completions',
                      'apiKey': 'fixture-only-not-a-credential', 'models': [{'id': 'fixture-model'}]}
        self.register(_connectionConfig=connection)
        previous = self.entry()['identity']['theme']
        self.register(_connectionConfig={**connection, 'baseUrl': 'https://second.example/v1'})
        self.assertEqual(self.apply.call_count, 2)
        self.assertEqual(previous, self.entry()['identity']['theme'])
        config = json.loads(runtime.config_path().read_text())
        from model_connections import provider_id
        self.assertEqual(config['models']['providers'][provider_id(self.agent)]['baseUrl'],
                         'https://second.example/v1')

    def test_team_provider_changes_are_compared_before_apply_mutates_config(self):
        self.register()
        import team_models
        original = team_models.apply
        def changed(config, **kwargs):
            original(config, **kwargs)
            config['models']['providers']['bac-team']['baseUrl'] = 'https://changed.example/v1'
        with patch.object(team_models, 'apply', side_effect=changed):
            self.register()
        self.assertEqual(self.apply.call_count, 2)
        config = json.loads(runtime.config_path().read_text())
        self.assertEqual(config['models']['providers']['bac-team']['baseUrl'], 'https://changed.example/v1')

    def test_unrelated_configuration_survives_unchanged_registration(self):
        self.register()
        config = json.loads(runtime.config_path().read_text())
        config['agents']['entries']['other'] = {'name': 'Keep', 'workspace': '/somewhere-else'}
        runtime.save_config(config)
        self.register()
        self.assertEqual(self.apply.call_count, 1)
        self.assertEqual(json.loads(runtime.config_path().read_text())['agents']['entries']['other'],
                         config['agents']['entries']['other'])

    def test_comparison_defers_null_removal_and_type_changes_to_native_patch(self):
        for current, update in [({'value': None}, {'value': None}),
                                ({'enabled': 1}, {'enabled': True}),
                                ({'allow': ['read', 'write']}, {'allow': ['read']})]:
            with self.subTest(update=update):
                before = copy.deepcopy(current)
                self.assertFalse(runtime._patch_already_applied(current, update))
                self.assertEqual(current, before)

    def test_registration_log_contains_timings_but_no_connection_or_instruction_content(self):
        with self.assertLogs(level='INFO') as logs:
            self.register(); self.register()
        text = '\n'.join(logs.output)
        self.assertIn('update=patched', text)
        self.assertIn('update=unchanged', text)
        self.assertIn('lock=', text)
        self.assertNotIn('baseUrl', text)
        self.assertNotIn('SKILL', text)


if __name__ == '__main__':
    unittest.main()
