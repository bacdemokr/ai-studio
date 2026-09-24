import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'scripts'), str(Path(__file__).resolve().parent)]
import agent_runtime as runtime
import runtime_settings as settings
import user_location
from studio import Studio, Problem
from test_studio import Adapter


class UserLocationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, {'BAC_DATA_DIR': self.temp.name}); env.start(); self.addCleanup(env.stop)
        self.studio = Studio(Path(self.temp.name)/'studio', Adapter(), start_worker=False)
        self.person = self.studio.session()[0]
        self.owner = self.person['id']
        self.studio.onboard(self.owner, {'name':'Scout', 'skills':['weather']})

    def test_changes_all_agents_and_crew_without_canceling_pending_work(self):
        second = self.studio.add_agent(self.owner, {'name':'Orbit','skills':['weather'], 'protection':'openshell'})['agentId']
        job = self.studio.enqueue(self.owner, {'prompt':'weather today'})
        workspace = self.studio.workspace(self.owner)
        (workspace/'USER.md').write_text('# Event preferences\n{"city":"Zurich"}\nMy personal note.\n')
        (workspace/'MEMORY.md').write_text('keep memory')
        team = self.studio.crew_owner(self.owner)
        before_event = settings.event()
        result = settings.save(self.studio, {'section':'location', 'location':{'city':' Seoul '}})
        self.assertEqual(result['location'], {'city':'Seoul'})
        self.assertEqual(settings.event(), before_event)
        for owner in (self.owner, second, team):
            for role in ((None, 0, 1, 2, 3) if owner == team else (None,)):
                content = (self.studio.workspace(owner,role)/'USER.md').read_text()
                self.assertIn('Seoul', content)
                self.assertNotIn('Zurich', content)
                self.assertNotIn('Event preferences', content)
        self.assertIn('My personal note.', (workspace/'USER.md').read_text())
        self.assertEqual((workspace/'MEMORY.md').read_text(), 'keep memory')
        self.assertFalse(runtime.config_path().exists())
        with self.studio.db() as db:
            self.assertEqual(db.execute('SELECT status FROM jobs WHERE id=?',(job['id'],)).fetchone()['status'], 'queued')
        third = self.studio.add_agent(self.owner, {'name':'Echo','skills':['documents']})['agentId']
        self.assertIn('Seoul', (self.studio.workspace(third)/'USER.md').read_text())

    def test_default_validation_and_model_independence(self):
        self.assertEqual(settings.location(), {'city':'Zurich'})
        saved = {'provider':'local','profiles':{'local':{'model':'keep'}},'event':{'city':'Tokyo'}}
        settings.persist(saved)
        for city in ('', ' ', 'x'*81, 'Seoul\nTokyo', None):
            with self.assertRaises(Problem):settings.save(self.studio, {'section':'location','location':{'city':city}})
        settings.save(self.studio, {'section':'location','location':{'city':'Zürich, Switzerland'}})
        self.assertEqual(settings.read()['profiles'], saved['profiles'])
        self.assertEqual(settings.event(), {'city':'Tokyo'})

    def test_each_native_request_receives_latest_default_without_changing_session(self):
        calls=[]
        def gateway(path, data=None, **kwargs):
            if path=='/v1/models':return {'data':[{'id':'openclaw/test'}]}
            calls.append(data)
            return {'choices':[{'message':{'content':'ok'}}]}
        with patch.object(runtime,'gateway', side_effect=gateway):
            runtime.respond('test','same-session','Weather in Paris?')
            settings.save(self.studio, {'section':'location','location':{'city':'Seoul'}})
            runtime.respond('test','same-session','Weather today?')
        self.assertEqual([c['user'] for c in calls], ['same-session']*2)
        self.assertIn('Zurich', calls[0]['messages'][0]['content'])
        self.assertIn('Weather in Paris?', calls[0]['messages'][0]['content'])
        self.assertIn('takes precedence', calls[0]['messages'][0]['content'])
        self.assertIn('Seoul', calls[1]['messages'][0]['content'])
        self.assertNotIn('Zurich', calls[1]['messages'][0]['content'])

    def test_migration_is_idempotent_and_does_not_touch_other_files(self):
        workspace = self.studio.workspace(self.owner)
        user_location.sync(workspace)
        first=(workspace/'USER.md').read_text()
        user_location.sync(workspace)
        self.assertEqual((workspace/'USER.md').read_text(), first)
        self.assertEqual(first.count(user_location.START),1)


if __name__=='__main__':unittest.main()
