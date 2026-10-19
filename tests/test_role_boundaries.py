"""Planner-control fixtures: identity/scope refusals must not trigger fallback work.

These exercise app dispatch and prompts, not live-model semantic accuracy.
"""
import json
import tempfile
from pathlib import Path
import unittest

from agent_runtime import write_workspace
from collaboration_plan import read_plan, PlanSelectionError
from role_boundaries import ROLE_BOUNDARY, TEAM_ROLE_BOUNDARY, ROLE_TEMPLATES
import test_visitor_teams as fixture
from visitor_teams import validate_selection, TeamSelectionError


class RoleBoundaryTests(unittest.TestCase):
    setUp = fixture.VisitorTeamTests.setUp
    start = fixture.VisitorTeamTests.start
    execute = fixture.VisitorTeamTests.execute
    specialists = fixture.VisitorTeamTests.specialists

    def weather(self, skills=None):
        self.app.configure(self.owner, {**self.app.profile(self.owner), 'purpose': 'Weather and outdoor comfort.',
                                       'skills': skills if skills is not None else ['weather']})

    def test_named_weather_decline_is_not_repaired_or_replaced(self):
        self.weather()
        self.adapter.selection = {'summary': 'Pixel has no programming role or skill.', 'tasks': [],
            'outcome': 'unavailable', 'answer': 'Pixel handles weather. Hire a programmer or equip Coding.',
            'declinedAgents': [{'agent': self.owner, 'reason': 'Weather and Live weather do not cover game development.'}]}
        job = self.execute(self.start('/goal Have Pixel build a game.', teamMode='hired'))
        plan = job['payload']['collaboration']
        self.assertEqual(job['status'], 'done')
        self.assertEqual(plan['outcome'], 'unavailable')
        self.assertEqual(plan['calledRoles'], [])
        self.assertEqual(plan['requiredAgents'], [])
        self.assertFalse(self.specialists())
        self.assertFalse(any('-planning-team-repair' in c[1] for c in self.adapter.calls))

    def test_unnamed_weather_pool_can_decline_without_calling_casey_as_coder(self):
        self.weather()
        self.adapter.selection = {'summary': 'No programming expertise.', 'tasks': [], 'outcome': 'unavailable',
                                  'answer': 'Hire a Programmer or equip Coding for this game.'}
        job = self.execute(self.start('/goal Build a game.', teamMode='hired'))
        self.assertEqual(job['payload']['collaboration']['outcome'], 'unavailable')
        self.assertFalse(self.specialists())
        self.assertIn(TEAM_ROLE_BOUNDARY, self.adapter.calls[0][2])

    def test_explicit_coding_skill_extends_weather_role(self):
        self.weather(['weather', 'builder'])
        self.adapter.selection['tasks'][0]['roleFit'] = 'Pixel’s explicitly equipped Coding skill covers this small webpage.'
        job = self.execute(self.start('/goal Have Pixel build a counter.', teamMode='hired'))
        plan = job['payload']['collaboration']
        self.assertEqual(plan['calledRoles'], [5])
        self.assertEqual([c[0] for c in self.specialists()], ['bac-' + self.owner])
        self.assertIn('builder', plan['visitorBindings']['5']['skills'])
        self.assertIn(ROLE_BOUNDARY, self.specialists()[0][2])
        scope_prompt = next(prompt for _, session, prompt in self.adapter.calls
                            if session.endswith('-planning-scope-check'))
        contract = scope_prompt.rsplit('Decision output contract:', 1)[1]
        self.assertIn('"decisions"', contract)
        self.assertNotIn('JSON object with summary and tasks', contract)

    def test_upstream_analysis_repair_rechecks_unchanged_coding_assignment(self):
        coding = {'role': 5, 'agent': self.owner, 'task': 'Build a page using the supplied analysis and recommendations.',
                  'expected': 'HTML presenting the supplied findings.', 'inputs': [],
                  'requiredFiles': ['artifacts/counter.html'], 'roleFit': 'Coding implements the supplied analysis.'}
        analysis = {'role': 6, 'agent': 'builtin', 'task': 'Compare the supplied figures and recommend next actions.',
                    'expected': 'An analysis brief with findings and recommendations.', 'inputs': [],
                    'requiredFiles': ['artifacts/analysis.md'], 'roleFit': 'Data interpretation covers analysis.'}
        self.adapter.selection = {'summary': 'Build the dashboard.', 'tasks': [coding]}
        self.adapter.repaired_selection = {'summary': 'Analyze first, then implement.', 'tasks': [analysis, coding]}
        original = self.adapter.respond
        checks = []

        def respond(agent, session, prompt, **kwargs):
            if session.endswith('-planning-scope-check'):
                self.adapter.calls.append((agent, session, prompt))
                candidates, _ = json.JSONDecoder().raw_decode(prompt.rsplit('Scope candidates:\n', 1)[1])
                candidate = candidates[0]
                checks.append(candidate)
                upstream = candidate.get('upstreamAssignments', [])
                allowed = bool(upstream and 'data-analysis' in upstream[0]['skills'])
                decisions = [{'agent': self.owner, 'allowed': allowed,
                    'reason': 'Analysis is supplied by the preceding specialist.' if allowed else 'No analysis handoff is scheduled.'}]
                if upstream:
                    decisions.insert(0, {'agent': 'builtin', 'allowed': True, 'reason': 'Ada supplies analysis.'})
                return json.dumps({'decisions': decisions})
            if agent.endswith('-r6') and '-working' in session:
                self.adapter.calls.append((agent, session, prompt))
                path = self.adapter.agents[agent] / 'artifacts/analysis.md'
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('The supplied values are 10 and 20. The second is twice the first. Verify the source before acting.')
                return 'Saved analysis to artifacts/analysis.md.'
            return original(agent, session, prompt, **kwargs)

        self.adapter.respond = respond
        job = self.execute(self.start('/goal Compare supplied values 10 and 20, recommend an action, and build a dashboard.', teamMode='mixed'))
        plan = job['payload']['collaboration']
        self.assertEqual(len(checks), 2, 'Adding the analysis handoff must invalidate the cached scope rejection.')
        self.assertEqual(checks[0]['task'], checks[1]['task'])
        self.assertEqual(checks[0]['upstreamAssignments'], [])
        upstream = checks[1]['upstreamAssignments']
        self.assertEqual(upstream[0]['name'], 'Ada')
        self.assertEqual(upstream[0]['skills'], ['data-analysis'])
        self.assertEqual(upstream[0]['requiredFiles'], ['artifacts/analysis.md'])
        self.assertEqual(plan['teamSelectionRecovery']['status'], 'corrected')
        self.assertEqual(plan['calledRoles'], [6, 5])
        self.assertEqual(plan['outcome'], 'complete')

    def test_custom_programming_role_without_skills_cannot_contribute(self):
        self.app.configure(self.owner, {**self.app.profile(self.owner), 'skills': []})
        job = self.execute(self.start(teamMode='hired'))
        self.assertEqual(job['payload']['collaboration']['calledRoles'], [])
        self.assertEqual(job['payload']['collaboration']['outcome'], 'unavailable')
        self.assertFalse(self.specialists())

    def test_scope_comments_cannot_replace_duplicate_or_missing_candidate_decisions(self):
        allowed = {'agent': self.owner, 'allowed': True, 'reason': 'Coding covers implementation.'}
        for decisions in ([], [allowed, allowed],
                          [allowed, {'agent': 'unknown', 'allowed': True, 'reason': 'Unrecognized identity.'}]):
            with self.subTest(decisions=decisions):
                self.adapter.calls.clear()
                original = fixture.VisitorAdapter.respond.__get__(self.adapter)

                def respond(agent, session, prompt, **kwargs):
                    if session.endswith('-planning-scope-check'):
                        return json.dumps({'decisions': decisions})
                    if session.endswith('-planning-team-repair'):
                        return json.dumps({'summary': 'Could not verify suitability.', 'tasks': [],
                                           'outcome': 'unavailable', 'answer': 'No work assigned.'})
                    return original(agent, session, prompt, **kwargs)

                self.adapter.respond = respond
                job = self.execute(self.start(teamMode='hired'))
                self.assertEqual(job['payload']['collaboration']['outcome'], 'unavailable')
                self.assertFalse(self.specialists())

    def test_missing_suitability_is_rejected_before_binding(self):
        with self.assertRaisesRegex(TeamSelectionError, 'roleFit'):
            validate_selection({'tasks':[{'role':5,'agent':self.owner}]}, [{'key':self.owner, 'skills':['builder']}], [], 'hired')

    def test_researchers_file_tools_do_not_qualify_them_for_implementation(self):
        for preset in ROLE_TEMPLATES:
            if preset['label'] == 'Programmer':
                continue
            member = {**preset, 'key': self.owner, 'name': 'Orbit'}
            for role in (5, 8):
                task = {'role': role, 'agent': self.owner, 'requiredFiles': ['artifacts/index.html'],
                        'roleFit': 'Can write HTML/JS using file tools.'}
                with self.subTest(preset=preset['label'], role=role), self.assertRaisesRegex(TeamSelectionError, 'File tools'):
                    validate_selection({'tasks': [task]}, [member], [], 'hired')
            member['skills'] = [*member['skills'], 'builder']
            validate_selection({'tasks': [task]}, [member], [], 'hired')

    def test_implementation_guard_requires_coding_for_preset_and_custom_roles(self):
        programmer = next(p for p in ROLE_TEMPLATES if p['label'] == 'Programmer')
        task = {'role': 5, 'agent': self.owner, 'requiredFiles': ['artifacts/index.html'],
                'roleFit': 'The saved purpose covers frontend implementation.'}
        for purpose in (programmer['purpose'], 'I build accessible browser applications.'):
            member = {'key': self.owner, 'name': 'Pixel', 'purpose': purpose, 'skills': []}
            with self.assertRaisesRegex(TeamSelectionError, 'no equipped specialist skill'):
                validate_selection({'tasks': [task]}, [member], [], 'hired')
            member['skills'] = ['builder']
            validate_selection({'tasks': [task]}, [member], [], 'hired')

    def test_bad_research_assignment_gets_corrected_without_dispatch(self):
        researcher = next(p for p in ROLE_TEMPLATES if p['label'] == 'Web researcher')
        self.app.configure(self.owner, {**self.app.profile(self.owner), 'purpose': researcher['purpose'], 'skills': ['web']})
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            if '-planning-team-repair' in session:
                self.adapter.calls.append((agent, session, prompt))
                return json.dumps({'summary': 'No implementation expertise.', 'tasks': [], 'outcome': 'unavailable',
                                   'answer': 'Hire a Programmer or equip Coding for the game.'})
            return original(agent, session, prompt, **kwargs)
        self.adapter.respond = respond
        job = self.execute(self.start('/goal Build a game.', teamMode='hired'))
        self.assertEqual(job['payload']['collaboration']['outcome'], 'unavailable')
        self.assertEqual(job['payload']['collaboration']['teamSelectionRecovery']['status'], 'corrected')
        self.assertFalse(self.specialists())

    def test_data_interpretation_does_not_grant_implementation(self):
        self.app.configure(self.owner, {**self.app.profile(self.owner), 'purpose': 'Analyze supplied business figures.', 'skills': ['data-analysis']})
        self.adapter.selection['tasks'][0]['agent'] = self.owner
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            if session.endswith('-planning-scope-check'):
                self.adapter.calls.append((agent, session, prompt))
                return json.dumps({'decisions': [{'agent': self.owner, 'allowed': False, 'reason': 'Data analysis does not include frontend implementation.'}]})
            if session.endswith('-planning-team-repair'):
                self.adapter.calls.append((agent, session, prompt))
                return json.dumps({'summary': 'No implementation expertise.', 'tasks': [], 'outcome': 'unavailable',
                                   'answer': 'A programmer is needed.'})
            return original(agent, session, prompt, **kwargs)
        self.adapter.respond = respond
        job = self.execute(self.start('/goal Build a dashboard.', teamMode='hired'))
        self.assertEqual(job['payload']['collaboration']['outcome'], 'unavailable')
        self.assertFalse(self.specialists())
        self.assertEqual(len([c for c in self.adapter.calls if c[1].endswith('-planning-scope-check')]), 0)

    def test_unrelated_equipped_skill_is_rejected_before_dispatch(self):
        self.weather()
        self.adapter.selection['tasks'] = [{'role': 6, 'agent': self.owner, 'task': 'Analyze company earnings.',
            'roleFit': 'Can read data.', 'requiredFiles': ['artifacts/brief.md']}]
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            if session.endswith('-planning-scope-check'):
                self.adapter.calls.append((agent, session, prompt))
                return json.dumps({'decisions': [{'agent': self.owner, 'allowed': False,
                                                  'reason': 'Live weather does not cover earnings analysis.'}]})
            if session.endswith('-planning-team-repair'):
                self.adapter.calls.append((agent, session, prompt))
                return json.dumps({'summary': 'Missing data-analysis skill.', 'tasks': [], 'outcome': 'unavailable',
                                   'answer': 'Equip Data interpretation.'})
            return original(agent, session, prompt, **kwargs)
        self.adapter.respond = respond
        job = self.execute(self.start('/goal Analyze these earnings.', teamMode='hired'))
        self.assertEqual(job['payload']['collaboration']['outcome'], 'unavailable')
        self.assertFalse(self.specialists())
        self.assertFalse(job['payload']['collaboration']['skillScopeChecks'][0]['allowed'])

    def test_decline_cannot_hide_an_invalid_or_also_selected_identity(self):
        for key in ('f'*24, self.owner):
            plan = {'tasks':[{'role':5,'agent':self.owner,'roleFit':'Coding'}],
                    'declinedAgents':[{'agent':key,'reason':'Does not fit.'}]}
            with self.assertRaises(TeamSelectionError):
                validate_selection(plan, [{'key':self.owner}], [], 'hired')

    def test_partial_team_preserves_decline_in_final_result(self):
        weather = self.app.add_agent(self.owner, {'name':'Rain','purpose':'Weather advice.','skills':['weather']})['agentId']
        self.adapter.selection['tasks'][0]['agent'] = self.owner
        self.adapter.selection['declinedAgents'] = [{'agent':weather,'reason':'Weather does not cover earnings analysis.'}]
        job = self.execute(self.start('/goal Have Pixel build a counter. Ask Rain to analyze NVIDIA earnings.', teamMode='hired'))
        plan = job['payload']['collaboration']
        self.assertEqual(plan['outcome'], 'partial')
        self.assertEqual(plan['calledRoles'], [5])
        self.assertEqual([m['name'] for m in plan['requiredAgents']], ['Pixel'])
        self.assertTrue(any('Rain' in gap for gap in plan['remaining']))

    def test_final_success_cannot_hide_an_unassigned_deliverable(self):
        self.adapter.writes = False
        self.adapter.selection = {'summary': 'Only the announcement can be drafted.',
            'requestedFormats': ['html'], 'unassignedRequirements': ['No suitable HTML implementation agent.'],
            'tasks': [{'role': 8, 'agent': self.owner, 'task': 'Draft the supplied announcement.',
                       'roleFit': 'Supplied announcement copy.', 'requiredFiles': [], 'inputs': []}]}
        job = self.execute(self.start('/goal Save an event webpage and announcement.', teamMode='hired'))
        plan = job['payload']['collaboration']
        self.assertEqual(plan['outcome'], 'partial')
        self.assertIn('Requested HTML file was not saved.', plan['remaining'])
        self.assertIn('No suitable HTML implementation agent.', job['result']['answer'])
        self.assertIn('Saved contribution', job['result']['answer'])

    def test_requested_saved_format_accepts_a_verified_delivery(self):
        self.adapter.selection['requestedFormats'] = ['html']
        job = self.execute(self.start(teamMode='hired'))
        self.assertEqual(job['payload']['collaboration']['outcome'], 'complete')
        self.assertTrue(any(file.endswith('.html') for file in job['result']['files']))

    def test_stopped_partial_reply_cannot_promise_more_work(self):
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            answer = original(agent, session, prompt, **kwargs)
            if session.endswith('-reviewing'):
                return json.dumps({'done': True, 'outcome': 'partial', 'reason': 'Missing analysis skill.',
                    'remaining': ['Business analysis requires Data interpretation.'],
                    'answer': 'I will now read the full thread and complete the analysis.'})
            return answer
        self.adapter.respond = respond
        job = self.execute(self.start(teamMode='hired'))
        self.assertEqual(job['payload']['collaboration']['outcome'], 'partial')
        self.assertIn('Business analysis requires Data interpretation.', job['result']['answer'])
        self.assertIn('No further automatic work will be started.', job['result']['answer'])
        self.assertNotIn('I will now read', job['result']['answer'])

    def test_programmer_without_exact_planned_filename_still_needs_verified_html(self):
        self.adapter.selection['requestedFormats'] = ['html']
        self.adapter.selection['tasks'][0]['agent'] = self.owner
        self.adapter.selection['tasks'][0]['requiredFiles'] = []
        job = self.execute(self.start('/goal Build an HTML game.', teamMode='hired'))
        self.assertEqual(job['payload']['collaboration']['outcome'], 'complete')
        self.assertTrue(any(file.endswith('.html') for file in job['result']['files']))

    def test_retired_assignment_slot_is_recoverable_before_dispatch(self):
        with self.assertRaisesRegex(PlanSelectionError, 'available assignment slot'):
            read_plan(json.dumps({'summary': 'Draft an announcement.', 'tasks': [{'role': 1, 'task': 'Draft supplied copy.'}]}))

    def test_analysis_only_plan_cannot_omit_requested_webpage_silently(self):
        member = {'key': self.owner, 'name': 'Dana', 'purpose': 'Analyze business data.', 'skills': ['data-analysis']}
        plan = {'requestedFormats': ['html'], 'tasks': [{'role': 6, 'agent': self.owner,
                'roleFit': 'Business data analysis.', 'requiredFiles': ['artifacts/analysis.md']}]}
        with self.assertRaisesRegex(TeamSelectionError, 'no assignment produces it'):
            validate_selection(plan, [member], [], 'hired')
        plan['unassignedRequirements'] = ['No webpage implementation agent is available.']
        validate_selection(plan, [member], [], 'hired')

    def test_declared_formats_cannot_replace_a_deliverable_with_a_promise(self):
        self.adapter.selection = {'summary': 'No suitable agent.', 'requestedFormats': ['html'], 'tasks': [],
                                  'answer': 'Both deliverables ready. Creating the HTML now.'}
        job = self.execute(self.start('/goal Save an HTML event page.', teamMode='hired'))
        self.assertEqual(job['payload']['collaboration']['outcome'], 'unavailable')
        self.assertNotIn('Both deliverables ready', job['result']['answer'])
        self.assertFalse(self.specialists())

    def test_specialist_decline_does_not_trigger_missing_file_repair(self):
        self.weather(['weather', 'builder']);self.adapter.writes = False
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            answer = original(agent, session, prompt, **kwargs)
            return '[role-mismatch] I handle weather and have no Coding skill. Please choose a programmer.' if '-working' in session else answer
        self.adapter.respond = respond
        job = self.execute(self.start('/goal Have Pixel build a game.', teamMode='hired'))
        plan = job['payload']['collaboration']
        self.assertEqual(plan['outcome'], 'unavailable')
        self.assertIn('scopeDecline', plan)
        self.assertEqual(len(self.specialists()), 1)
        self.assertNotIn('repair', plan)

    def test_malformed_decline_cannot_reach_dispatch(self):
        for decline in ({'agent':self.owner}, {'agent':'unlisted','reason':'Wrong role'}, 'no'):
            with self.assertRaises(PlanSelectionError):
                read_plan(json.dumps({'summary':'No appropriate agent','tasks':[], 'answer':'Cannot assign.', 'declinedAgents':[decline]}))

    def test_personal_and_protected_workspace_share_role_or_skill_rule(self):
        for protection in ('standard', 'openshell'):
            with tempfile.TemporaryDirectory() as folder:
                workspace = Path(folder)
                write_workspace(workspace, {'name':'Rain','purpose':'Weather advice.','skills':['weather'],'protection':protection})
                self.assertIn(ROLE_BOUNDARY, (workspace/'SOUL.md').read_text())
                self.assertNotIn('Do not refuse merely', (workspace/'SOUL.md').read_text())


if __name__ == '__main__':
    unittest.main()
