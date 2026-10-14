"""Same-preset hires retain identities across bounded plan-selection repair."""
import json
import unittest

import test_visitor_teams as fixture
from agent_runtime import collaboration_capabilities, tool_allowlist
from studio import safe_file


class VisitorRosterDiversityTests(unittest.TestCase):
    setUp = fixture.VisitorTeamTests.setUp
    start = fixture.VisitorTeamTests.start
    execute = fixture.VisitorTeamTests.execute
    specialists = fixture.VisitorTeamTests.specialists

    def duplicate_selection(self, corrected=True):
        peer = self.app.add_agent(self.owner, {'name': 'Rain', 'skills': ['weather']})['agentId']
        tasks = [dict(role=6, agent=key, task=task, inputs=[], requiredFiles=[file])
                 for key, task, file in [(self.owner, 'Calculate total and average.', 'artifacts/calculation.md'),
                                         (peer, 'Independently verify the calculation.', 'artifacts/check.md')]]
        self.adapter.auto_agents = False
        self.adapter.writes = False
        self.adapter.selection = {'summary': 'Two weather hires calculate and check.', 'tasks': tasks}
        repaired = json.loads(json.dumps(self.adapter.selection))
        if corrected:
            repaired['tasks'][1]['role'] = 4
        original = self.adapter.respond

        def respond(agent, session, prompt, **kwargs):
            if '-planning-input-repair' in session:
                self.adapter.calls.append((agent, session, prompt))
                return json.dumps(repaired)
            answer = original(agent, session, prompt, **kwargs)
            if '-working' in session:
                file = 'artifacts/calculation.md' if agent == 'bac-' + self.owner else 'artifacts/check.md'
                safe_file(self.adapter.agents[agent], file).write_text('Total 60. Average 20. Static arithmetic check.')
            return answer

        self.adapter.respond = respond
        return peer

    def test_duplicate_roles_repaired_before_dispatch_preserve_both_weather_hires(self):
        peer = self.duplicate_selection()
        job = self.execute(self.start('/goal Pixel calculates 12 + 18 + 30; Rain independently checks it.', teamMode='hired'))
        plan = job['payload']['collaboration']
        self.assertEqual(job['status'], 'done')
        self.assertEqual(plan['planSelectionRecovery']['status'], 'corrected')
        self.assertEqual(plan['calledRoles'], [6, 4])
        self.assertEqual(plan['visitorBindings']['6']['key'], self.owner)
        self.assertEqual(plan['visitorBindings']['4']['key'], peer)
        self.assertCountEqual([c[0] for c in self.specialists()], ['bac-' + self.owner, 'bac-' + peer])
        self.assertEqual(len([c for c in self.adapter.calls if '-planning-input-repair' in c[1]]), 1)

    def test_bad_duplicate_repair_never_dispatches_or_recruits_standby(self):
        self.duplicate_selection(corrected=False)
        with self.assertRaisesRegex(RuntimeError, 'invalid or duplicate specialist'):
            self.execute(self.start('/goal Pixel calculates and Rain checks.', teamMode='hired'))
        self.assertEqual(self.specialists(), [])
        self.assertEqual(len([c for c in self.adapter.calls if '-planning-input-repair' in c[1]]), 1)

    def test_capability_guidance_tracks_real_permissions_not_skill_labels(self):
        weather = {'skills': ['weather'], 'protection': 'standard'}
        coder = {'skills': ['builder'], 'protection': 'standard'}
        protected = {'skills': ['weather'], 'protection': 'openshell'}
        for profile in (weather, coder, protected):
            with self.subTest(profile=profile):
                caps = collaboration_capabilities(profile)
                self.assertEqual(caps['tools'], tool_allowlist(profile))
                guidance = ' '.join(caps['limits'])
                self.assertEqual('write can save Markdown, HTML' in guidance, 'write' in caps['tools'])
                self.assertEqual('web_fetch can attempt public URLs on any requested topic' in guidance,
                                 'web_fetch' in caps['tools'])
        self.assertIn('web_fetch', collaboration_capabilities(weather)['tools'])
        self.assertNotIn('web_fetch', collaboration_capabilities(coder)['tools'])
        self.assertNotIn('write', collaboration_capabilities(protected)['tools'])


if __name__ == '__main__':
    unittest.main()
