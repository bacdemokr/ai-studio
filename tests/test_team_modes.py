import unittest
from unittest.mock import patch
import test_visitor_teams as fixtures
from studio import Problem
from visitor_teams import team_mode, instructions, validate_selection, TeamSelectionError


class TeamModeTests(unittest.TestCase):
    setUp = fixtures.VisitorTeamTests.setUp
    start = fixtures.VisitorTeamTests.start
    execute = fixtures.VisitorTeamTests.execute
    specialists = fixtures.VisitorTeamTests.specialists
    def test_hired_only_keeps_casey_and_runs_named_hire(self):
        # Weather is sufficient to join: role/skill labels are not admission requirements.
        self.assertEqual(self.app.profile(self.owner)['skills'], ['weather'])
        job = self.execute(self.start(teamMode='hired'))
        self.assertEqual(job['status'], 'done')
        self.assertEqual(job['payload']['teamMode'], 'hired')
        self.assertEqual([c[0] for c in self.specialists()], ['bac-' + self.owner])
        self.assertIn('HIRED AGENTS ONLY', self.adapter.calls[0][2])
        self.assertEqual(self.app.profile(self.owner)['skills'], ['weather'])
        self.assertEqual(job['payload']['collaboration']['visitorBindings']['5']['key'], self.owner)

    def test_hired_only_rejects_builtin_selection_before_work_and_repairs_once(self):
        self.adapter.auto_agents = False
        self.adapter.selection['tasks'][0]['agent'] = 'builtin'
        self.adapter.repaired_selection = {**self.adapter.selection, 'tasks': [
            {**self.adapter.selection['tasks'][0], 'agent': self.owner}]}
        job = self.execute(self.start(teamMode='hired'))
        self.assertEqual(job['payload']['collaboration']['teamSelectionRecovery']['status'], 'corrected')
        self.assertEqual([c[0] for c in self.specialists()], ['bac-' + self.owner])

    def test_hired_only_never_falls_back_after_invalid_repair(self):
        self.adapter.auto_agents = False
        for role in (4, 5, 6, 7, 8):
            with self.subTest(role=role):
                self.adapter.selection['tasks'][0].update(role=role, agent='builtin')
                job = self.execute(self.start(teamMode='hired'))
                self.assertFalse(self.specialists())
                self.assertEqual(job['payload']['collaboration']['teamSelectionRecovery']['status'], 'failed')
        self.assertEqual({c[0] for c in self.adapter.calls}, {'bac-' + self.manager + '-r0'})

    def test_hired_only_missing_identity_is_not_treated_as_standby(self):
        self.adapter.auto_agents = False
        job = self.execute(self.start(teamMode='hired'))
        self.assertFalse(self.specialists())
        self.assertEqual(job['payload']['collaboration']['teamSelectionRecovery']['status'], 'failed')

    def test_hired_only_dispatch_guard_survives_missing_binding(self):
        # Simulate a binding regression after a valid plan: the execution boundary
        # must still reject the built-in occupant of this assignment's role.
        with patch('visitor_teams.bind', return_value=None), self.assertRaisesRegex(RuntimeError, 'built-in specialist cannot be started'):
            self.execute(self.start(teamMode='hired'))
        self.assertFalse(self.specialists())
        self.assertEqual({c[0] for c in self.adapter.calls}, {'bac-' + self.manager + '-r0'})

    def test_hired_only_context_recovery_keeps_the_same_hired_agent(self):
        self.adapter.fail_once = True
        job = self.execute(self.start(teamMode='hired'))
        self.assertEqual(job['payload']['collaboration']['outputLimitRetry']['status'], 'recovered')
        self.assertEqual([c[0] for c in self.specialists()], ['bac-' + self.owner] * 2)
        self.assertEqual({c[0] for c in self.adapter.calls}, {'bac-' + self.manager + '-r0', 'bac-' + self.owner})

    def test_hired_only_missing_handoff_does_not_recruit_standby(self):
        self.adapter.writes = False
        job = self.execute(self.start(teamMode='hired'))
        self.assertEqual(job['payload']['collaboration']['outcome'], 'partial')
        self.assertTrue(self.specialists())
        self.assertEqual({c[0] for c in self.specialists()}, {'bac-' + self.owner})
        self.assertEqual({c[0] for c in self.adapter.calls}, {'bac-' + self.manager + '-r0', 'bac-' + self.owner})

    def test_hired_only_requires_an_available_hire_before_enqueue(self):
        with patch('visitor_teams.capture', return_value=([], [], [])), self.assertRaisesRegex(Problem, r'No hired agents are ready. Hire an agent or choose Hired \+ Standby\.'):
            self.start(teamMode='hired')
        with self.app.db() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM jobs WHERE kind='crew-chat'").fetchone()[0], 0)

    def test_unavailable_hires_are_not_told_to_hire_a_specific_role(self):
        unavailable = [{'name': 'Pixel', 'reason': 'Busy or unavailable.'}]
        with patch('visitor_teams.capture', return_value=([], [], unavailable)), self.assertRaisesRegex(
                Problem, r'Check their status in the Lounge or choose Hired \+ Standby\.'):
            self.start(teamMode='hired')

    def test_modes_and_old_client_flag_are_validated(self):
        self.assertEqual(team_mode({}), 'builtin')
        self.assertEqual(team_mode({'includeHiredAgents': True}), 'mixed')
        self.assertEqual(team_mode({'teamMode': 'hired', 'includeHiredAgents': False}), 'hired')
        for value in ('auto', '', None, [], True):
            with self.subTest(value=value), self.assertRaises(Problem):
                self.start(teamMode=value)

    def test_hired_only_independent_review_cannot_be_self_review_or_builtin(self):
        members=[{'key':self.owner,'name':'Pixel'}]
        plan={'tasks':[{'role':5,'agent':self.owner},{'role':4,'agent':self.owner}]}
        with self.assertRaises(TeamSelectionError):validate_selection(plan,members,[], 'hired')
        plan['tasks'][1]['agent']='builtin'
        with self.assertRaises(TeamSelectionError):validate_selection(plan,members,[], 'hired')
        plan['tasks'][1]['agent']='reviewer';members.append({'key':'reviewer','name':'Review'})
        validate_selection(plan,members,[], 'hired')

    def test_modes_remain_isolated_on_followup(self):
        hired=self.execute(self.start(teamMode='hired'))
        built=self.execute(self.start('/goal Build a counter.',teamMode='builtin'))
        mixed=self.execute(self.start(teamMode='mixed'))
        self.assertEqual([c[0] for c in self.specialists()],['bac-'+self.owner,'bac-'+self.manager+'-r5','bac-'+self.owner])
        self.assertEqual([j['payload']['teamMode'] for j in (hired,built,mixed)],['hired','builtin','mixed'])
