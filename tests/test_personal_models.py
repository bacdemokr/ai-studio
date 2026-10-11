import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import model_connections as connections
import personal_models
import runtime_settings as settings
import session_secrets
from studio import Studio, Problem
from test_tech_radar import RadarAdapter
import visitor_teams


class PersonalModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        environment = patch.dict(os.environ, {'BAC_DATA_DIR': self.temp.name})
        environment.start(); self.addCleanup(environment.stop)
        background = patch.object(connections, 'threading')
        background.start(); self.addCleanup(background.stop)
        self.adapter = RadarAdapter()
        self.app = Studio(Path(self.temp.name) / 'studio', self.adapter, start_worker=False)
        self.owner = self.app.session()[0]['id']
        self.lease = 'personal-' + self.temp.name
        self.addCleanup(session_secrets.release, self.lease)
        connections.initialize()

    def connect(self, source, provider=None):
        provider = provider or ('local' if source == 'local' else 'nvidia')
        data = {'source': source, 'provider': provider, 'model': 'local-model' if source == 'local' else 'api-default',
                'baseUrl': settings.PROVIDERS[provider]['baseUrl'], 'contextWindow': 32768,
                '_credentialSession': self.lease}
        if source == 'api': data['apiKey'] = 'fixture-secret'
        with patch.object(settings, 'request', return_value={'data': [{'id': data['model']}, {'id': 'other-model'}]}):
            return connections.configure(self.app, data)

    def hire(self, name='Pixel', **extra):
        if not self.app.profile(self.owner):
            return self.app.onboard(self.owner, {'name': name, 'skills': ['writer'], **extra})
        added = self.app.add_agent(self.owner, {'name': name, 'skills': ['writer'], **extra})
        return self.app.profile(added['agentId'])

    def test_default_is_local_even_when_only_external_is_ready(self):
        self.connect('api')
        profile = self.hire()
        self.assertEqual(profile['model'], 'local')
        self.assertFalse(personal_models.ready(profile, self.app.runtime_status()))
        with self.assertRaisesRegex(Problem, 'Local model is not connected'):
            self.app.enqueue(self.owner, {'prompt': 'Hello'})
        with self.assertRaisesRegex(Problem, 'Local model is not connected'):
            self.app.ensure_agent(self.owner, profile)
        self.assertEqual(self.adapter.calls, [])

    def test_local_and_two_external_choices_route_independently(self):
        self.connect('local'); self.connect('api')
        profiles = [self.hire(), self.hire('One', model='api/nvidia/api-default'),
                    self.hire('Two', model='api/nvidia/other-model')]
        connections.preferences(self.app, {'lounge': 'api'})
        for profile, expected in zip(profiles, ['local-model', 'api-default', 'other-model']):
            self.app.ensure_agent(profile['id'][4:], profile)
            native = self.adapter.profiles[profile['id']]['_connectionConfig']
            self.assertEqual(native['models'][0]['id'], expected)
            self.assertNotIn('fixture-secret', json.dumps(native))
            self.assertNotIn('_connectionConfig', self.app.profile(profile['id'][4:]))

    def test_edit_changes_only_this_agent_and_keeps_saved_choice_on_reload(self):
        self.connect('local'); self.connect('api')
        first, other = self.hire(), self.hire('Second')
        self.app.ensure_agent(self.owner, first)
        changed = self.app.configure(self.owner, {**first, 'model': 'api/nvidia/other-model'})
        self.app.ensure_agent(self.owner, changed)
        self.assertEqual(self.adapter.profiles[first['id']]['_connectionConfig']['models'][0]['id'], 'other-model')
        self.assertEqual(self.app.profile(other['id'][4:])['model'], 'local')
        restored = Studio(Path(self.temp.name) / 'studio', self.adapter, start_worker=False)
        self.assertEqual(restored.profile(self.owner)['model'], 'api/nvidia/other-model')

    def test_expired_external_key_never_falls_back_to_local(self):
        self.connect('local'); self.connect('api', 'openai')
        profile = self.hire(model='api/openai/other-model')
        session_secrets.release(self.lease)
        self.assertTrue(self.app.runtime_status()['model'])
        self.assertFalse(personal_models.ready(profile, self.app.runtime_status()))
        with self.assertRaisesRegex(Problem, 'unavailable'):
            self.app.ensure_agent(self.owner, profile)
        # Editing a name does not require a working model or erase its choice.
        changed = self.app.configure(self.owner, {**profile, 'name': 'Pixel Two'})
        self.assertEqual(changed['model'], profile['model'])

    def test_provider_switch_does_not_reinterpret_same_model_id(self):
        self.connect('api')
        profile = self.hire(model='api/nvidia/other-model')
        self.connect('api', 'openai')
        self.assertFalse(personal_models.ready(profile, self.app.runtime_status()))
        changed = self.app.configure(self.owner, {**profile, 'name': 'Renamed'})
        self.assertEqual(changed['model'], 'api/nvidia/other-model')

    def test_missing_model_is_not_replaced_with_connection_default(self):
        self.connect('api')
        profile = self.hire(model='api/nvidia/other-model')
        value = connections.profile('api')
        connections._checks[connections.signature(value)] = (time.monotonic(), {'ready': True, 'models': [{'id': 'api-default'}]})
        self.assertFalse(personal_models.ready(profile, self.app.runtime_status()))
        with self.assertRaises(Problem): self.app.ensure_agent(self.owner, profile)

    def test_existing_agent_without_choice_keeps_lounge_preference(self):
        self.connect('api')
        profile = self.hire()
        profile.pop('model')
        with self.app.db() as db: db.execute('UPDATE agents SET profile=? WHERE id=?', (json.dumps(profile), self.owner))
        self.assertTrue(personal_models.ready(profile, self.app.runtime_status()))
        self.app.ensure_agent(self.owner, profile)
        self.assertEqual(self.adapter.profiles[profile['id']]['_connectionConfig']['models'][0]['id'], 'api-default')
        changed = self.app.configure(self.owner, {**profile, 'name': 'Legacy'})
        self.assertEqual(changed['model'], 'shared')

    def test_unconnected_local_can_be_saved_without_probe_or_key(self):
        with patch.object(settings, 'request', side_effect=AssertionError('No model calls while Hiring')):
            profile = self.hire()
        self.assertEqual(profile['model'], 'local')
        self.assertEqual(self.adapter.calls, [])

    def test_invalid_or_injected_model_references_are_rejected(self):
        for value in ({'apiKey': 'bad'}, None, 'https://example.com/key', 'api/nvidia/no-such-model', 'api/local/test', 'local\napi'):
            with self.subTest(value=value), self.assertRaises(Problem): self.hire(model=value)

    def test_background_radar_waits_for_its_own_source(self):
        self.connect('api')
        local = self.hire(skills=['radar'])
        api = self.hire('Radar Two', skills=['radar'], model='api/nvidia/other-model')
        self.app.heartbeat.presence(self.owner, 'tab')
        while (job := self.app.next_job()):
            try: self.app.execute(job)
            except Problem:
                with self.app.db() as db: db.execute("UPDATE jobs SET status='error' WHERE id=?", (job['id'],))
        with self.app.db() as db: db.execute("UPDATE jobs SET created=created-30,updated=updated-90 WHERE kind='prepare-agent'")
        self.app.heartbeat.tick()
        self.assertEqual(self.app.heartbeat.status(self.owner, local)['state'], 'waiting for model')
        self.assertFalse(self.adapter.cadence[local['id']])
        self.assertTrue(self.adapter.cadence[api['id']])
        self.assertEqual(self.adapter.profiles[api['id']]['_connectionConfig']['models'][0]['id'], 'other-model')

    def test_team_capture_checks_each_hired_model(self):
        self.connect('api')
        self.hire()
        external = self.hire('Writer', model='api/nvidia/other-model')
        with self.app.db() as db:
            members, _, unavailable = visitor_teams.capture(self.app, db, self.owner, 'Write a page.')
            self.assertEqual([row['name'] for row in members], ['Writer'])
            self.assertEqual(unavailable[0]['name'], 'Pixel')
            with self.assertRaisesRegex(Problem, 'Pixel: Local model'):
                visitor_teams.capture(self.app, db, self.owner, 'Have Pixel write a page.')
        with self.app.db() as db:
            reaction = self.app.capture_roundtable(db, self.owner)
            self.assertEqual([m['name'] for m in reaction['members']], ['Writer'])
            self.assertEqual(reaction['skipped'][0]['name'], 'Pixel')
        self.app.ensure_agent(external['id'][4:], external)
        self.assertEqual(self.adapter.profiles[external['id']]['_connectionConfig']['models'][0]['id'], 'other-model')

    def test_shared_settings_do_not_overwrite_scoped_native_routes(self):
        config = {'agents': {'defaults': {}, 'entries': {'bac-test': {'model': 'bac-connection-abc/chosen'}}}}
        settings.apply_to_config(config, 'local', {'apiKey': '', 'baseUrl': 'http://127.0.0.1:8000/v1', 'model': 'another', 'contextWindow': 32768})
        self.assertEqual(config['agents']['entries']['bac-test']['model'], 'bac-connection-abc/chosen')
