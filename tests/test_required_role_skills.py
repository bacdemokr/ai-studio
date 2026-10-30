"""Fixed preset skills survive API edits and upgrades; custom roles stay flexible."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from native_config_fixture import offline_config
from role_boundaries import ROLE_TEMPLATES
from studio import Studio
from test_studio import Adapter


class RequiredRoleSkillsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {'BAC_DATA_DIR': self.temp.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.directory = Path(self.temp.name) / 'studio'
        self.app = Studio(self.directory, Adapter(), start_worker=False)
        self.owner = self.app.session()[0]['id']
        self.presets = {p['label']: p for p in ROLE_TEMPLATES}

    def test_onboard_and_add_agent_supply_the_fixed_skill_without_dropping_extras(self):
        programmer = self.presets['프로그래머']
        profile = self.app.onboard(self.owner, {'name': 'Pixel', 'purpose': programmer['purpose'], 'skills': []})
        self.assertEqual(profile['skills'], ['builder'])
        researcher = self.presets['웹 조사원']
        added = self.app.add_agent(self.owner, {'name': 'Orbit', 'purpose': researcher['purpose'], 'skills': ['writer']})
        self.assertEqual(self.app.profile(added['agentId'])['skills'], ['web', 'writer'])
        analyst = self.presets['데이터 분석가']
        added = self.app.add_agent(self.owner, {'name': 'Dana', 'purpose': analyst['purpose'], 'skills': ['builder']})
        self.assertCountEqual(self.app.profile(added['agentId'])['skills'], ['data-analysis', 'builder'])
        self.assertTrue((self.app.workspace(added['agentId']) / 'skills/bac-data-analysis/SKILL.md').is_file())

    @offline_config
    def test_edit_cannot_remove_core_but_custom_role_can_have_no_skills(self):
        self.app.onboard(self.owner, {'name': 'Pixel', 'purpose': self.presets['프로그래머']['purpose'], 'skills': ['builder', 'web']})
        profile = self.app.configure(self.owner, {'name': 'Pixel', 'skills': ['web'], 'tonePrompt': 'Curious.'})
        self.assertEqual(profile['skills'], ['builder', 'web'])
        profile = self.app.configure(self.owner, {**profile, 'purpose': self.presets['웹 조사원']['purpose'], 'skills': []})
        self.assertEqual(profile['skills'], ['web'])
        profile = self.app.configure(self.owner, {**profile, 'purpose': self.presets['데이터 분석가']['purpose'], 'skills': []})
        self.assertEqual(profile['skills'], ['data-analysis'])
        profile = self.app.configure(self.owner, {**profile, 'skills': ['builder']})
        self.assertCountEqual(profile['skills'], ['data-analysis', 'builder'])
        profile = self.app.configure(self.owner, {**profile, 'purpose': 'Help me think through everyday decisions.', 'skills': []})
        self.assertEqual(profile['skills'], [])
        self.assertEqual(profile['tonePrompt'], 'Curious.')

    def test_restart_repairs_legacy_presets_and_leaves_custom_profiles_unchanged(self):
        profile = self.app.onboard(self.owner, {'name': 'Pixel', 'purpose': self.presets['프로그래머']['purpose'], 'skills': ['writer']})
        custom = self.app.add_agent(self.owner, {'name': 'Helper', 'purpose': 'Help me think.', 'skills': []})['agentId']
        # Model a persisted pre-upgrade profile whose core skill was removed.
        profile['skills'] = ['writer']
        with self.app.db() as db:
            for table in ('agents', 'participants'):
                db.execute('UPDATE '+table+' SET profile=? WHERE id=?', (json.dumps(profile), self.owner))
        restarted = Studio(self.directory, Adapter(), start_worker=False)
        self.assertEqual(restarted.profile(self.owner)['skills'], ['builder', 'writer'])
        self.assertEqual(restarted.profile(custom)['skills'], [])
        with restarted.db() as db:
            self.assertEqual(json.loads(db.execute('SELECT profile FROM participants WHERE id=?', (self.owner,)).fetchone()[0])['skills'], ['builder', 'writer'])
        self.assertTrue((restarted.workspace(self.owner) / 'skills/bac-builder/SKILL.md').is_file())
        self.assertEqual(Studio(self.directory, Adapter(), start_worker=False).profile(self.owner)['skills'], ['builder', 'writer'])

    @offline_config
    def test_lounge_presets_keep_core_skills_through_edits_and_upgrade(self):
        self.app.onboard(self.owner, {'name': 'Helper', 'purpose': 'Help me think.', 'skills': []})
        cases = [('날씨 도우미', 'weather'), ('테크 레이더', 'radar'),
                 ('arXiv 연구원', 'web'), ('Slack 작성자', 'writer')]
        saved = []
        for label, skill in cases:
            with self.subTest(role=label):
                owner = self.app.add_agent(self.owner, {
                    'name': label, 'purpose': self.presets[label]['purpose'], 'skills': ['builder']
                })['agentId']
                profile = self.app.profile(owner)
                self.assertCountEqual(profile['skills'], [skill, 'builder'])
                profile = self.app.configure(owner, {**profile, 'skills': []})
                self.assertEqual(profile['skills'], [skill])
                # A pre-upgrade saved preset may be missing its core skill.
                profile['skills'] = ['builder']
                with self.app.db() as db:
                    db.execute('UPDATE agents SET profile=? WHERE id=?', (json.dumps(profile), owner))
                saved.append((owner, skill))
        restarted = Studio(self.directory, Adapter(), start_worker=False)
        self.assertEqual(restarted.profile(self.owner)['skills'], [])
        for owner, skill in saved:
            self.assertCountEqual(restarted.profile(owner)['skills'], [skill, 'builder'])

    @offline_config
    def test_english_saved_presets_keep_fixed_skills_after_korean_upgrade(self):
        self.app.onboard(self.owner, {'name': 'Helper', 'purpose': 'Help me think.', 'skills': []})
        for preset in ROLE_TEMPLATES:
            with self.subTest(role=preset['label']):
                self.assertLessEqual(len(preset['purpose']), 240)
                self.assertRegex(preset['purpose'], '[가-힣]')
                previous = preset['purposeAliases'][0]
                profile = self.app.configure(self.owner, {
                    'name': 'Helper', 'purpose': previous, 'skills': [],
                    'tonePrompt': 'Keep my custom wording exactly.',
                })
                self.assertEqual(profile['skills'], preset['requiredSkills'])
                self.assertEqual(profile['purpose'], previous)
                self.assertEqual(profile['tonePrompt'], 'Keep my custom wording exactly.')
                profile = self.app.configure(self.owner, {**profile, 'purpose': preset['purpose'], 'skills': []})
                self.assertEqual(profile['skills'], preset['requiredSkills'])
