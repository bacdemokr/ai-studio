"""Reported name/negation cases, plus structural enforcement of Casey's decisions.

These test real capture/validation/dispatch with simulated availability and planner
responses. Actual model interpretation is covered separately by live regression.
"""
import json
import unittest
from unittest.mock import Mock, patch
from collaboration_plan import read_plan, PlanSelectionError
from studio import Problem
import visitor_teams as teams
import test_visitor_teams as fixture

A = [("Don't have Pixel build it; let Cody do the page.", 'Pixel'),
 ("Pixel shouldn't touch this. Use Cody to build the page.", 'Pixel'),
 ('Pixel 없이 해줘', 'Pixel'),
 ('Pixel 없이 Cody한테 맡겨줘', 'Pixel'),
 ('Pixel 안 쓰고 Cody가 해줘', 'Pixel'),
 ('Pixel은 이번에 참여 안 해도 돼', 'Pixel'),
 ('Pixel is on vacation. Use Cody to build the page.', 'Pixel'),
 ('Do not use Pixel or Nova. Have Cody build the page.', 'Nova'),
 ('Have Cody chart the numbers in nova-sales.csv.', 'Nova'),
 ('Show max 3 items and have Cody build a bar chart.', 'Max')]

B = [("Don't skip Pixel: have Pixel build the page.", 'Pixel'),
 ('Pixel은 빼지 말고 꼭 넣어서 페이지 만들어줘', 'Pixel'),
 ('Pixel 제외하지 말고 Pixel이 만들어줘', 'Pixel'),
 ('Pixel must not be left out. Have Pixel build it.', 'Pixel'),
 ('Without Pixel this fails, so have Pixel build the page.', 'Pixel')]

C = [('Pixel이 카운터 페이지 만들어줘', 'Pixel'),
 ('Pixel, build a small counter page.', 'Pixel'),
 ('Pixel에게 부탁해서 페이지 만들어줘', 'Pixel')]

class ParticipantIntentTests(unittest.TestCase):
    def setUp(self):
        self.members = [{'key': char * 24, 'name': name, 'skills': ['builder']}
                        for char, name in zip('abcd', ('Pixel', 'Nova', 'Max', 'Cody'))]
        self.app, self.db = Mock(), Mock()
        self.db.execute.return_value.fetchone.return_value = None
        self.pixel, self.cody = self.members[0]['key'], self.members[-1]['key']

    def capture(self):
        with patch.object(teams, 'hired_members', return_value=self.members), patch('personal_models.ready', return_value=True):
            return teams.capture(self.app, self.db, 'owner')

    def plan(self, agent, **fields):
        return {'summary': 'Build the page.', 'tasks': [{'role': 5, 'agent': agent,
            'task': 'Build a counter.', 'roleFit': 'Coding covers this page.'}], **fields}

    def test_all_ten_false_requirements_cannot_block_correct_cody_plan(self):
        for prompt, name in A:
            with self.subTest(prompt=prompt):
                busy = next(m['key'] for m in self.members if m['name'] == name)
                self.app.require_idle.side_effect = lambda db, key: (_ for _ in ()).throw(Problem('Busy', 409)) if key == busy else None
                available, unavailable = self.capture()
                self.assertEqual([m['key'] for m in unavailable], [busy])
                teams.validate_selection(self.plan(self.cody, requestedAgents=[self.cody]), available, unavailable, 'hired')

    def test_all_five_requested_but_excluded_agents_stay_assignable(self):
        for prompt, _ in B:
            with self.subTest(prompt=prompt):
                available, unavailable = self.capture()
                self.assertEqual(available, self.members)
                self.assertEqual(unavailable, [])
                teams.validate_selection(self.plan(self.pixel, requestedAgents=[self.pixel]), available, [], 'hired')

    def test_model_can_require_all_three_previously_missed_requests(self):
        for prompt, _ in C:
            with self.subTest(prompt=prompt):
                teams.validate_selection(self.plan(self.pixel, requestedAgents=[self.pixel]), self.members, [], 'hired')
                with self.assertRaisesRegex(teams.TeamSelectionError, 'participation request'):
                    teams.validate_selection(self.plan(self.cody, requestedAgents=[self.pixel]), self.members, [], 'hired')

    def test_preparing_and_disconnected_are_context_not_regex_rejections(self):
        self.app.require_idle.side_effect = Problem('Preparing', 409)
        self.db.execute.return_value.fetchone.return_value = (1,)
        members, unavailable = self.capture()
        self.assertFalse(members)
        self.assertTrue(all(m['reason'] == 'Preparing.' for m in unavailable))
        self.assertEqual({m['key'] for m in unavailable}, {m['key'] for m in self.members})

    def test_missing_requested_agent_needs_explicit_decline(self):
        available = self.members[1:]
        unavailable = [{'key': self.pixel, 'name': 'Pixel', 'reason': 'Preparing.'}]
        plan = self.plan(self.cody, requestedAgents=[self.pixel])
        with self.assertRaises(teams.TeamSelectionError):
            teams.validate_selection(plan, available, unavailable, 'hired')
        plan['declinedAgents'] = [{'agent': self.pixel, 'reason': 'Preparing. Wait for Pixel.'}]
        teams.validate_selection(plan, available, unavailable, 'hired')
        with self.assertRaisesRegex(RuntimeError, 'outside the available'):
            teams.validate_selection(self.plan(self.pixel), available, unavailable, 'hired')

    def test_excluded_requested_unknown_and_declined_conflicts_are_rejected(self):
        for fields in ({'excludedAgents': [self.pixel]},
                       {'requestedAgents': [self.pixel], 'excludedAgents': [self.pixel]},
                       {'requestedAgents': ['f' * 24]}, {'excludedAgents': ['f' * 24]},
                       {'declinedAgents': [{'agent': self.pixel, 'reason': 'Busy.'}]}):
            with self.subTest(fields=fields), self.assertRaises(teams.TeamSelectionError):
                teams.validate_selection(self.plan(self.pixel, **fields), self.members, [], 'hired')

    def test_standby_priority_exception_uses_model_intent_not_name_mentions(self):
        plan = self.plan('builtin')
        with self.assertRaisesRegex(teams.TeamSelectionError, 'must use a suitable hired'):
            teams.validate_selection(plan, self.members)
        plan['requestedAgents'] = ['Cody']
        teams.validate_selection(plan, self.members)
        with self.assertRaisesRegex(teams.TeamSelectionError, 'Hired agents only'):
            teams.validate_selection(plan, self.members, [], 'hired')
        plan['excludedAgents'] = ['Cody']
        with self.assertRaises(teams.TeamSelectionError):
            teams.validate_selection(plan, self.members)

    def test_participation_decisions_do_not_grant_skills(self):
        with self.assertRaisesRegex(teams.TeamSelectionError, 'Coding'):
            teams.validate_selection(self.plan(self.pixel, requestedAgents=[self.pixel]),
                [{**self.members[0], 'skills': ['weather']}], [], 'hired')

    def test_participation_schema_rejects_malformed_ids_and_duplicates(self):
        for field in ('requestedAgents', 'excludedAgents'):
            for value in ('Pixel', ['Pixel'], [self.pixel, self.pixel], [None], [{}], ['f' * 25]):
                with self.subTest(field=field, value=value), self.assertRaises(PlanSelectionError):
                    read_plan(json.dumps(self.plan(self.pixel, **{field: value})))
        plan = read_plan(json.dumps(self.plan(self.pixel, requestedAgents=[self.pixel, 'Scout'])))
        self.assertEqual(plan['requestedAgents'], [self.pixel, 'Scout'])


class ParticipantDispatchTests(unittest.TestCase):
    setUp = fixture.VisitorTeamTests.setUp
    start = fixture.VisitorTeamTests.start
    execute = fixture.VisitorTeamTests.execute
    specialists = fixture.VisitorTeamTests.specialists

    def test_four_reported_controls_preserve_contextual_choices(self):
        controls = [('Have Pixel build a page.', self.owner, []),
                    ('Do not use Pixel. Let Cody build a page.', 'builtin', [self.owner]),
                    ('Pixel 빼고 Cody가 만들어줘', 'builtin', [self.owner]),
                    ('Pixel 말고 Cody로 만들어줘', 'builtin', [self.owner])]
        for prompt, chosen, excluded in controls:
            with self.subTest(prompt=prompt):
                self.adapter.selection['tasks'][0]['agent'] = chosen
                self.adapter.participation = {'requestedAgents': ['Cody' if chosen == 'builtin' else chosen],
                                              'excludedAgents': excluded}
                job = self.execute(self.start('/goal ' + prompt, teamMode='mixed'))
                self.assertEqual(job['status'], 'done')
                self.assertEqual(job['payload']['collaboration']['tasks'][0]['agent'], chosen)
                self.assertNotIn('teamSelectionRecovery', job['payload']['collaboration'])

    def test_reported_double_negations_and_missed_requests_dispatch_pixel(self):
        self.adapter.participation = {'requestedAgents': [self.owner]}
        for prompt, _ in B + C:
            with self.subTest(prompt=prompt):
                job = self.execute(self.start('/goal ' + prompt, teamMode='hired'))
                self.assertEqual(job['status'], 'done')
                self.assertEqual(job['payload']['collaboration']['calledRoles'], [5])
                self.assertEqual(self.specialists()[-1][0], 'bac-' + self.owner)
                self.assertNotIn('teamSelectionRecovery', job['payload']['collaboration'])

    def test_preparing_pixel_does_not_block_cody_and_legacy_required_hint_is_ignored(self):
        cody = self.app.add_agent(self.owner, {'name': 'Cody', 'skills': ['builder']})['agentId']
        self.app.enqueue(self.owner, {'kind': 'chat', 'prompt': 'Synthetic preparation'})
        with self.app.db() as db:
            db.execute("UPDATE jobs SET kind='prepare-agent',status='running' WHERE owner=?", (self.owner,))
        self.adapter.selection['tasks'][0]['agent'] = cody
        self.adapter.participation = {'requestedAgents': [cody], 'excludedAgents': [self.owner]}
        result = self.start('/goal Pixel 없이 Cody한테 맡겨줘. Build a counter.', teamMode='hired')
        with self.app.db() as db:
            payload = json.loads(db.execute('SELECT payload FROM jobs WHERE id=?', (result['id'],)).fetchone()[0])
            payload['requiredVisitors'] = [{'key': self.owner, 'name': 'Pixel', 'role': 5}]
            db.execute('UPDATE jobs SET payload=? WHERE id=?', (json.dumps(payload), result['id']))
        job = self.execute(result)
        self.assertEqual(job['status'], 'done')
        self.assertEqual(job['payload']['collaboration']['requiredAgents'][0]['key'], cody)
        self.assertEqual([c[0] for c in self.specialists()], ['bac-' + cody])
        prompt = self.adapter.calls[0][2]
        self.assertIn('Preparing.', prompt)
        self.assertNotIn('Required participants detected', prompt)
