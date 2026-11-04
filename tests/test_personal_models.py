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
        for name, empty in [('_checks', {}), ('_pending', set()), ('_discovered', {})]:
            cache = patch.object(connections, name, empty)
            cache.start(); self.addCleanup(cache.stop)
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

    def test_local_default_uses_only_available_api_without_overwriting_choice(self):
        self.connect('api')
        profile = self.hire()
        self.assertEqual(profile['model'], 'local')
        self.assertTrue(personal_models.ready(profile, self.app.runtime_status()))
        self.app.ensure_agent(self.owner, profile)
        self.assertEqual(self.adapter.profiles[profile['id']]['_connectionConfig']['models'][0]['id'], 'api-default')
        self.assertEqual(self.app.profile(self.owner)['model'], 'local')

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

    def test_model_only_change_preserves_identity_and_routes_next_call(self):
        self.connect('api')
        original = self.hire(model='api/nvidia/api-default', purpose='Build small pages.',
                             tonePrompt='Friendly and concise.', skills=['builder'], protection='openshell')
        other = self.hire('Second', model='api/nvidia/api-default')
        changed = self.app.select_agent_model(self.owner, {'model': 'api/nvidia/other-model', 'name': 'Do not apply'})
        self.assertEqual(changed, {**original, 'model': 'api/nvidia/other-model'})
        self.assertEqual(self.app.profile(other['id'][4:]), other)
        # Preparation is model-free; the next actual call binds the new route.
        self.app.ensure_agent(self.owner, changed)
        self.assertEqual(self.adapter.profiles[original['id']]['_connectionConfig']['models'][0]['id'], 'other-model')
        restored = Studio(Path(self.temp.name) / 'studio', self.adapter, start_worker=False)
        self.assertEqual(restored.profile(self.owner), changed)

    def test_model_only_change_rejects_offline_and_deleted_agents(self):
        self.connect('api')
        original = self.hire(model='api/nvidia/api-default')
        with self.assertRaisesRegex(Problem, 'not connected'):
            self.app.select_agent_model(self.owner, {'model': 'local'})
        self.assertEqual(self.app.profile(self.owner), original)
        with self.app.db() as db:
            db.execute('UPDATE agents SET deleting=2 WHERE id=?', (self.owner,))
        with self.assertRaisesRegex(Problem, 'deletion'):
            self.app.select_agent_model(self.owner, {'model': 'api/nvidia/other-model'})

    def test_model_change_is_locked_for_pending_personal_and_team_work(self):
        self.connect('api')
        original = self.hire(model='api/nvidia/api-default')
        personal = self.app.enqueue(self.owner, {'prompt': 'Hello'})
        with self.assertRaisesRegex(Problem, 'pending missions'):
            self.app.select_agent_model(self.owner, {'model': 'api/nvidia/other-model'})
        self.app.decision(self.owner, personal['id'], 'cancel')
        manager = self.app.crew_owner(self.owner)
        job = self.app.enqueue(manager, {'kind': 'crew-chat', 'crewRole': 0,
                              'prompt': '/goal Have Pixel build a counter.', 'teamMode': 'hired'})
        with self.assertRaisesRegex(Problem, 'pending crew mission'):
            self.app.select_agent_model(self.owner, {'model': 'api/nvidia/other-model'})
        self.assertEqual(self.app.profile(self.owner), original)
        self.app.decision(manager, job['id'], 'cancel')
        changed = self.app.select_agent_model(self.owner, {'model': 'api/nvidia/other-model'})
        self.assertEqual(changed['model'], 'api/nvidia/other-model')

    def test_new_work_during_model_save_wins_without_overwriting_profile(self):
        self.connect('api')
        original = self.hire(model='api/nvidia/api-default')
        with patch.object(self.app.heartbeat, 'disable', side_effect=lambda _: self.app.enqueue(self.owner, {'prompt': 'Race'})):
            with self.assertRaisesRegex(Problem, 'pending missions'):
                self.app.select_agent_model(self.owner, {'model': 'api/nvidia/other-model'})
        self.assertEqual(self.app.profile(self.owner), original)

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

    def test_background_radar_uses_api_fallback_and_preserves_explicit_choice(self):
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
        self.assertEqual(self.app.heartbeat.status(self.owner, local)['state'], 'watching')
        self.assertTrue(self.adapter.cadence[local['id']])
        self.assertEqual(self.adapter.profiles[local['id']]['_connectionConfig']['models'][0]['id'], 'api-default')
        self.assertTrue(self.adapter.cadence[api['id']])
        self.assertEqual(self.adapter.profiles[api['id']]['_connectionConfig']['models'][0]['id'], 'other-model')

    def test_team_capture_checks_each_hired_model(self):
        self.connect('api')
        self.hire()
        external = self.hire('Writer', model='api/nvidia/other-model')
        with self.app.db() as db:
            members, unavailable = visitor_teams.capture(self.app, db, self.owner)
            self.assertEqual([row['name'] for row in members], ['Pixel', 'Writer'])
            self.assertEqual(unavailable, [])
        with self.app.db() as db:
            reaction = self.app.capture_roundtable(db, self.owner)
            self.assertEqual([m['name'] for m in reaction['members']], ['Pixel', 'Writer'])
            self.assertEqual(reaction['skipped'], [])
        self.app.ensure_agent(external['id'][4:], external)
        self.assertEqual(self.adapter.profiles[external['id']]['_connectionConfig']['models'][0]['id'], 'other-model')

    def test_shared_settings_do_not_overwrite_scoped_native_routes(self):
        config = {'agents': {'defaults': {}, 'entries': {'bac-test': {'model': 'bac-connection-abc/chosen'}}}}
        settings.apply_to_config(config, 'local', {'apiKey': '', 'baseUrl': 'http://127.0.0.1:8000/v1', 'model': 'another', 'contextWindow': 32768})
        self.assertEqual(config['agents']['entries']['bac-test']['model'], 'bac-connection-abc/chosen')

    def route(self, profile, stage):
        self.app.ensure_agent(self.owner, profile, model_stage=stage)
        return self.adapter.profiles[profile['id']]['_connectionConfig']['models'][0]['id']

    def test_local_hire_switches_api_and_returns_local_without_profile_mutation(self):
        self.connect('local'); self.connect('api')
        profile = self.hire()
        self.assertEqual(self.route(profile, 'lounge'), 'local-model')
        self.assertEqual(self.route(profile, 'team'), 'api-default')
        self.assertEqual(self.route(profile, 'lounge'), 'local-model')
        self.assertEqual(self.app.profile(self.owner), profile)

    def test_explicit_api_is_preserved_in_every_stage(self):
        self.connect('local'); self.connect('api')
        profile = self.hire(model='api/nvidia/other-model')
        for stage in ('lounge', 'team', 'lounge'):
            self.assertEqual(self.route(profile, stage), 'other-model')

    def test_local_only_works_in_both_stages(self):
        self.connect('local')
        profile = self.hire()
        for stage in ('lounge', 'team'):
            self.assertEqual(self.route(profile, stage), 'local-model')

    def test_open_task_explicit_local_and_reset_are_separate_from_lounge(self):
        self.connect('local'); self.connect('api')
        profile = self.hire(model='api/nvidia/other-model')
        changed = self.app.select_agent_model(self.owner, {'model':'local', 'stage':'team'})
        self.assertEqual(changed['model'], profile['model'])
        self.assertEqual(self.route(changed, 'team'), 'local-model')
        self.assertEqual(self.route(changed, 'lounge'), 'other-model')
        edited = self.app.configure(self.owner, {**changed, 'name':'Renamed'})
        self.assertEqual(edited['taskModel'], 'local')
        restored = self.app.select_agent_model(self.owner, {'model':'auto', 'stage':'team'})
        self.assertNotIn('taskModel', restored)
        self.assertEqual(self.route(restored, 'team'), 'other-model')

    def test_stage_choice_captured_in_direct_chat_not_current_room(self):
        self.connect('local'); self.connect('api')
        profile = self.hire()
        job = self.app.enqueue(self.owner, {'prompt':'Hello', 'modelStage':'team'})
        self.app.heartbeat.presence(self.owner, 'tab', open_task=False, revision=1)
        self.app.execute(self.app.next_job())
        self.assertEqual(self.adapter.profiles[profile['id']]['_connectionConfig']['models'][0]['id'], 'api-default')
        self.app.enqueue(self.owner, {'prompt':'Hello from Lounge'})
        self.app.execute(self.app.next_job())
        self.assertEqual(self.adapter.profiles[profile['id']]['_connectionConfig']['models'][0]['id'], 'local-model')

    def test_open_task_override_cannot_change_during_pending_work(self):
        self.connect('local'); self.connect('api')
        profile = self.hire()
        self.app.enqueue(self.owner, {'prompt':'Hello', 'modelStage':'team'})
        with self.assertRaises(Problem):
            self.app.select_agent_model(self.owner, {'model':'local', 'stage':'team'})
        self.assertEqual(self.app.profile(self.owner), profile)

    def test_explicit_api_is_unavailable_in_team_instead_of_silently_falling_back(self):
        self.connect('local'); self.connect('api', 'openai')
        profile = self.hire(model='api/openai/other-model')
        session_secrets.release(self.lease)
        self.assertFalse(personal_models.ready(profile, self.app.runtime_status(), 'team'))
        with self.assertRaises(Problem):
            self.route(profile, 'team')

    def test_api_only_stage_cycle_uses_default_without_mutating_local_preference(self):
        self.connect('api')
        profile = self.hire()
        for stage in ('lounge', 'team', 'lounge'):
            self.assertEqual(self.route(profile, stage), 'api-default')
        self.assertEqual(self.app.profile(self.owner)['model'], 'local')

    def test_task_dispatch_and_reactions_use_api_then_next_lounge_call_restores_local(self):
        from test_visitor_teams import VisitorAdapter
        self.adapter = VisitorAdapter()
        self.app.adapter = self.adapter
        self.connect('local'); self.connect('api')
        profile = self.hire(skills=['builder'], purpose='Build small webpages.')
        guest = self.hire('Guest', model='local')
        manager = self.app.crew_owner(self.owner, 'plan')
        seen = []
        self.adapter.after = lambda agent, session: seen.append((agent, session, self.adapter.profiles[agent]['_connectionConfig']['models'][0]['id']))
        import team_models
        with patch.object(team_models, 'selections', return_value=[{'role':i,'id':'api-default'} for i in range(9)]):
            submitted = self.app.enqueue(manager, {'kind':'crew-chat','crewRole':0,'teamMode':'hired','prompt':'/goal Build a counter.'})
            self.app.heartbeat.presence(self.owner, 'tab', open_task=False, revision=2)
            self.app.execute(self.app.next_job())
        hired_calls = [x for x in seen if x[0] in (profile['id'], guest['id'])]
        self.assertTrue(any('-working' in x[1] for x in hired_calls), seen)
        self.assertTrue(any('roundtable' in x[1] for x in hired_calls), seen)
        self.assertEqual({x[2] for x in hired_calls}, {'api-default'})
        with self.app.db() as db:
            job = self.app.public_job(db.execute('SELECT * FROM jobs WHERE id=?',(submitted['id'],)).fetchone())
        self.assertEqual(job['status'], 'done')
        self.assertEqual(self.app.profile(self.owner)['model'], 'local')
        self.assertEqual(self.route(profile, 'lounge'), 'local-model')

    def test_failed_reaction_retry_uses_updated_task_override(self):
        from test_visitor_teams import VisitorAdapter
        self.adapter = VisitorAdapter()
        self.app.adapter = self.adapter
        self.connect('local'); self.connect('api')
        self.hire(skills=['builder'])
        guest = self.hire('Guest', model='local')
        guest_key = guest['id'][4:]
        self.app.select_agent_model(guest_key, {'model':'api/nvidia/other-model', 'stage':'team'})
        manager = self.app.crew_owner(self.owner, 'plan')
        respond = self.adapter.respond
        def fail_guest(agent, session, prompt, **kwargs):
            if agent == guest['id'] and 'roundtable' in session:
                raise RuntimeError('Simulated reaction failure')
            return respond(agent, session, prompt, **kwargs)
        self.adapter.respond = fail_guest
        import team_models
        with patch.object(team_models, 'selections', return_value=[{'role':i,'id':'api-default'} for i in range(9)]):
            submitted = self.app.enqueue(manager, {'kind':'crew-chat','crewRole':0,'teamMode':'hired','prompt':'/goal Build a counter.'})
            with self.assertLogs(level='ERROR'):
                self.app.execute(self.app.next_job())
        self.adapter.respond = respond
        self.app.select_agent_model(guest_key, {'model':'local', 'stage':'team'})
        self.app.retry_reaction(manager, {'id':submitted['id'], 'member':guest_key})
        self.app.execute(self.app.next_job())
        with self.app.db() as db:
            row = db.execute('SELECT payload FROM jobs WHERE id=?', (submitted['id'],)).fetchone()
        self.assertEqual(json.loads(row['payload'])['roundtable']['replies'][guest_key]['status'], 'done')
        self.assertEqual(self.adapter.profiles[guest['id']]['_connectionConfig']['models'][0]['id'], 'local-model')
