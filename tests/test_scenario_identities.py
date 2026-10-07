"""Distinct event personas and one connection model for the entire event crew."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import agent_runtime as runtime
import model_connections as connections
import scenario_models
import team_models
from studio import Studio, CREW_CATALOG, Problem
from test_studio import Adapter


class ScenarioIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, {'BAC_DATA_DIR': self.temp.name})
        env.start(); self.addCleanup(env.stop)
        self.app = Studio(Path(self.temp.name)/'studio', Adapter(), start_worker=False)
        person = self.app.session()[0]['id']
        self.event = self.app.crew_owner(person, 'event-brief')
        self.plan = self.app.crew_owner(person, 'plan')

    def test_role_definitions_and_native_contexts_are_distinct(self):
        for role in range(4):
            event = self.app.workspace(self.event, role)
            plan = self.app.workspace(self.plan, role)
            self.assertNotEqual(self.app.crew_native_id(self.event, role), self.app.crew_native_id(self.plan, role))
            self.assertNotEqual(self.app.crew_chat_session(self.event, role), self.app.crew_chat_session(self.plan, role))
            self.assertNotEqual((event/'SOUL.md').read_text(), (plan/'SOUL.md').read_text())
            self.assertIn('Team: Event Brief', (event/'IDENTITY.md').read_text())
        self.assertIn('Name: Riley', (self.app.workspace(self.event, 0)/'IDENTITY.md').read_text())
        self.assertIn('Name: Casey', (self.app.workspace(self.plan, 0)/'IDENTITY.md').read_text())
        with self.app.db() as db:
            event = self.app.crew_roster(db, self.event, {}, preset=True)
            plan = self.app.crew_roster(db, self.plan, {}, preset=True)
        self.assertEqual((event[0]['name'], event[0]['role']), ('Riley', 'Event coordinator'))
        self.assertEqual(plan[0]['name'], 'Casey')

    def test_upgrade_updates_generated_files_and_preserves_custom_files_and_memory(self):
        for role in range(4):
            member = CREW_CATALOG[role]
            runtime.write_workspace(self.app.workspace(self.event, role), member, member['role'])
        folder = self.app.workspace(self.event, 0)
        (folder/'MEMORY.md').write_text('Keep event memory')
        (self.app.workspace(self.event, 1)/'SOUL.md').write_text('Custom Dylan instructions')
        self.app.initialize_crew_workspaces(self.event)
        self.assertIn('Name: Riley', (folder/'IDENTITY.md').read_text())
        self.assertIn('fixed team', (folder/'SOUL.md').read_text())
        self.assertEqual((folder/'MEMORY.md').read_text(), 'Keep event memory')
        self.assertEqual((self.app.workspace(self.event, 1)/'SOUL.md').read_text(), 'Custom Dylan instructions')

    def test_event_ignores_old_agent_models_for_all_connection_providers(self):
        for provider, source in [('nvidia','api'), ('openai','api'), ('anthropic','api'), ('local','local')]:
            value = {'_provider':provider, 'baseUrl':'http://localhost:8000/v1', 'apiKey':'',
                     'model':'connection-model', 'contextWindow':32768}
            with patch.object(connections, 'resolve', return_value=(source, value)), patch.object(team_models, 'available_models', side_effect=AssertionError('No specialist catalog needed')):
                for role in range(4):
                    member = {'id':self.app.crew_native_id(self.event,role), '_scenario':'event-brief', '_teamModel':'stale-specialist-model'}
                    connections.prepare(self.app, member)
                    self.assertEqual(member['_connectionConfig']['models'][0]['id'], 'connection-model')
        value = {'_provider':'nvidia', 'baseUrl':'http://localhost:8000/v1', 'apiKey':'', 'model':'connection-model', 'contextWindow':32768}
        with patch.object(connections, 'resolve', return_value=('api',value)), patch.object(team_models, 'available_models', return_value=[{'id':'specialist-model'}]):
            member = {'id':self.app.crew_native_id(self.plan,5), '_scenario':'plan', '_teamModel':'specialist-model'}
            connections.prepare(self.app, member)
            self.assertEqual(member['_connectionConfig']['models'][0]['id'], 'specialist-model')

    def test_direct_chats_use_their_own_role_prompts(self):
        for owner, name, title in [(self.event, 'Riley', 'Event coordinator'), (self.plan, 'Casey', 'Team captain')]:
            self.app.enqueue(owner, {'kind':'crew-chat', 'crewRole':0, 'prompt':'What is your role?'})
            self.app.execute(self.app.next_job())
            prompt = self.app.adapter.calls[-1][2]
            self.assertIn('You are ' + name + ', the ' + title, prompt)
            profile = self.app.adapter.profiles[self.app.crew_native_id(owner,0)]
            self.assertEqual(profile['_scenario'], self.app.crew_scenario(owner))

    def test_event_model_display_and_edit_boundary(self):
        with self.app.db() as db:
            db.execute('UPDATE crew_resources SET model=? WHERE owner=?', ('stale-model',self.event))
        with patch.object(scenario_models, 'connection', return_value={'shared':True,'model':'connection-model'}):
            self.assertEqual({r['id'] for r in team_models.selections(self.app,self.event)}, {'connection-model'})
        with self.assertRaisesRegex(Problem, 'whole team'):
            team_models.select(self.app,self.event,{'role':0,'model':team_models.MODELS[0]})
        self.assertEqual(team_models.selections(self.app,self.plan)[5]['id'],team_models.MODELS[0])
