import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_studio import Studio, Adapter, Problem, safe_file
from agent_runtime import GatewayError
from visitor_teams import requirements


BARCELONA_REQUEST = '''/goal Have Pixel and the built-in researcher Scout work together on a small Barcelona travel guide.

Scout: Find three interesting places to visit, using official tourism sources. Keep the research brief and provide one useful fact and a source link for each place.

Pixel: Turn Scout's findings into one self-contained HTML page with three attractive cards and a button to show or hide each place's details. Use no external libraries.'''


class NamedAssignmentTests(unittest.TestCase):
    def test_prose_never_determines_a_named_agents_runtime_role(self):
        for request in (BARCELONA_REQUEST,
                        'Have Pixel and the built-in researcher Scout work together on a travel guide.',
                        "Have Scout find places, then get Pixel to turn the findings into a page.",
                        'Pixel이 코딩을 맡아줘. Scout가 조사해서 바르셀로나 여행 페이지 만들어줘.'):
            with self.subTest(request=request):
                self.assertEqual(requirements(request, [{'name': 'Pixel', 'key': 'pixel'}]),
                                 [{'key': 'pixel', 'name': 'Pixel', 'role': None}])



class VisitorAdapter(Adapter):
    def __init__(self):
        super().__init__()
        self.selection = {'summary': 'Build the requested page.', 'tasks': [
            {'role': 5, 'task': 'Build the requested counter.', 'inputs': [], 'requiredFiles': ['artifacts/counter.html']}]}
        self.auto_agents = True
        self.repaired_selection = None
        self.writes = True
        self.fail_once = False
        self.check_done = False
        self.check_partial = False
        self.after = None

    def respond(self, agent, session, prompt, **kwargs):
        self.calls.append((agent, session, prompt))
        if self.after:
            self.after(agent, session)
        if session.endswith('-planning') or '-planning-' in session:
            selection = json.loads(json.dumps(self.repaired_selection if '-planning-team-repair' in session
                                              and self.repaired_selection is not None else self.selection))
            # Simulated planner identities, not natural-language interpretation.
            if self.auto_agents and 'Hired agents:\n' in prompt:
                required, _ = json.JSONDecoder().raw_decode(prompt.split('Required participants detected from the direct request:\n', 1)[1])
                preferred_role = 5 if any(t['role'] == 5 for t in selection['tasks']) else next((t['role'] for t in selection['tasks']), None)
                for task in selection['tasks']:
                    task.setdefault('agent', required[0]['key'] if required and task['role'] == preferred_role else 'builtin')
            return json.dumps(selection)
        if '-checking-' in session:
            return json.dumps({'done': self.check_done, 'reason': 'Fixture checkpoint.', 'answer': 'Saved work.',
                               'outcome': 'partial' if self.check_partial else 'complete', 'remaining': ['Evidence is incomplete.']})
        if session.endswith(('-reviewing', '-finalizing')):
            return json.dumps({'done': True, 'reason': 'Actual contributions returned.', 'answer': 'The team delivered the counter.', 'outcome': 'complete'})
        if '-working' in session or '-recovering' in session:
            if self.writes:
                safe_file(self.agents[agent], 'artifacts/counter.html').write_text(
                    '<!doctype html><html><body><h1>Counter</h1><button onclick="this.textContent=Number(this.textContent)+1">0</button></body></html>')
            if self.fail_once:
                self.fail_once = False
                raise GatewayError('Fixture context overflow', 'context-overflow')
            return 'My actual contribution is artifacts/counter.html.'
        return 'Fixture personal reply.'


class VisitorTeamTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, {'BAC_DATA_DIR': self.temp.name})
        env.start(); self.addCleanup(env.stop)
        self.adapter = VisitorAdapter()
        self.app = Studio(Path(self.temp.name) / 'studio', self.adapter, start_worker=False)
        self.owner = self.app.session()[0]['id']
        self.app.onboard(self.owner, {'name': 'Pixel', 'skills': ['weather'], 'purpose': 'Weather advice.', 'tonePrompt': 'Dry and funny.'})
        self.manager = self.app.crew_owner(self.owner)

    def start(self, prompt='/goal Pixel이 Coding작업들을 대신하게 해줘. Build a counter.', **options):
        return self.app.enqueue(self.manager, {'kind': 'crew-chat', 'crewRole': 0, 'prompt': prompt,
                                               'includeHiredAgents': True, **options})

    def execute(self, result):
        with self.app.db() as db:
            db.execute("UPDATE jobs SET status='running' WHERE id=? AND status='queued'", (result['id'],))
            row = db.execute('SELECT * FROM jobs WHERE id=?', (result['id'],)).fetchone()
        self.app.execute(row)
        with self.app.db() as db:
            return self.app.public_job(db.execute('SELECT * FROM jobs WHERE id=?', (result['id'],)).fetchone())

    def specialists(self):
        return [c for c in self.adapter.calls if '-working' in c[1] or '-recovering' in c[1]]

    def test_default_and_explicit_off_use_only_builtins_with_suitable_hires(self):
        self.app.configure(self.owner, {**self.app.profile(self.owner), 'skills': ['builder']})
        for options in ({}, {'includeHiredAgents': False}):
            with self.subTest(options=options), patch('visitor_teams.capture', side_effect=AssertionError('Must not capture hired team')):
                result = self.app.enqueue(self.manager, {'kind': 'crew-chat', 'crewRole': 0,
                                                         'prompt': '/goal Build a counter.', **options})
                job = self.execute(result)
                self.assertEqual(job['status'], 'done')
                self.assertIs(job['payload']['includeHiredAgents'], False)
                self.assertNotIn('roster', job['payload'])
                self.assertEqual(job['payload']['roundtable']['replies'][self.owner]['status'], 'done')
                self.assertFalse(job['payload']['collaboration'].get('visitorBindings'))
                self.assertTrue(self.specialists()[-1][0].endswith('-r5'))
        personal_calls = [c for c in self.adapter.calls if c[0] == 'bac-' + self.owner]
        self.assertEqual(len(personal_calls), 2)
        self.assertTrue(all(c[1].startswith('bac-roundtable-') for c in personal_calls))
        self.assertIn('The team delivered the counter.', personal_calls[-1][2])
        self.assertIn('not as an assigned specialist', personal_calls[-1][2])
        self.assertFalse(any('VISITOR TEAM SELECTION' in c[2] for c in self.adapter.calls))

    def test_off_named_agent_explains_opt_in_before_queuing_any_work(self):
        with self.assertRaisesRegex(Problem, 'Choose Mixed team or Hired agents only to assign Pixel'):
            self.start(includeHiredAgents=False)
        with self.app.db() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM jobs WHERE kind='crew-chat'").fetchone()[0], 0)

    def test_off_ignores_names_in_quotes_and_negative_requests(self):
        for prompt in ('/goal Build a counter.\n> Ask Pixel to code.', "/goal Don't use Pixel. Build a counter."):
            job = self.execute(self.start(prompt, includeHiredAgents=False))
            self.assertEqual(job['status'], 'done')

    def test_off_does_not_require_lounge_model_or_idle_hired_agents(self):
        self.app.enqueue(self.owner, {'kind': 'chat', 'prompt': 'Weather now?'})
        status = {'ready': False, 'gateway': True, 'model': False, 'teamReady': True, 'teamModel': True}
        with patch.object(self.app, 'runtime_status', return_value=status):
            job = self.execute(self.start('/goal Build a counter.', includeHiredAgents=False))
        self.assertEqual(job['status'], 'done')
        self.assertTrue(self.specialists()[-1][0].endswith('-r5'))

    def test_off_keeps_existing_reaction_guest_reservation_and_deletion_rules(self):
        result = self.start('/goal Build a counter.', includeHiredAgents=False)
        with self.assertRaises(Problem):
            self.app.configure(self.owner, {**self.app.profile(self.owner), 'tonePrompt': 'Concise.'})
        with self.assertRaises(Problem):
            self.app.enqueue(self.owner, {'kind': 'chat', 'prompt': 'Weather now?'})
        self.app.delete_agent(self.owner, {'name': 'Pixel'}, enqueue_only=True)
        self.assertEqual(self.execute(result)['status'], 'cancelled')

    def test_flag_is_boolean_and_client_cannot_inject_a_roster_when_off(self):
        for value in ('false', 'true', 0, 1, None, []):
            with self.subTest(value=value), self.assertRaisesRegex(Problem, 'must be on or off'):
                self.start('/goal Build a counter.', includeHiredAgents=value)
        job = self.execute(self.start('/goal Build a counter.', includeHiredAgents=False,
                                     roster=[{**self.app.profile(self.owner), 'key': self.owner}],
                                     requiredVisitors=[{'key': self.owner, 'name': 'Pixel', 'role': 5}]))
        self.assertNotIn('roster', job['payload'])
        self.assertTrue(self.specialists()[-1][0].endswith('-r5'))

    def test_switching_on_then_off_does_not_reuse_visitor_bindings(self):
        first = self.execute(self.start())
        second = self.execute(self.start('/goal Build a counter.', includeHiredAgents=False))
        third = self.execute(self.start())
        self.assertEqual([call[0] for call in self.specialists()],
                         ['bac-' + self.owner, 'bac-' + self.manager + '-r5', 'bac-' + self.owner])
        self.assertTrue(first['payload']['collaboration']['visitorBindings'])
        self.assertFalse(second['payload']['collaboration'].get('visitorBindings'))
        self.assertTrue(third['payload']['collaboration']['visitorBindings'])
        self.assertFalse(first['payload']['roundtable']['members'])
        self.assertEqual(second['payload']['roundtable']['replies'][self.owner]['status'], 'done')
        self.assertFalse(third['payload']['roundtable']['members'])

    def test_pre_toggle_queued_job_retains_its_captured_team(self):
        result = self.start()
        with self.app.db() as db:
            payload = json.loads(db.execute('SELECT payload FROM jobs WHERE id=?', (result['id'],)).fetchone()[0])
            del payload['includeHiredAgents']
            db.execute('UPDATE jobs SET payload=? WHERE id=?', (json.dumps(payload), result['id']))
        job = self.execute(result)
        self.assertEqual(job['payload']['collaboration']['visitorBindings']['5']['key'], self.owner)

    def test_named_weather_agent_replaces_coder_with_same_identity_and_workspace(self):
        before = self.app.profile(self.owner)
        job = self.execute(self.start())
        self.assertEqual(job['status'], 'done')
        plan = job['payload']['collaboration']
        self.assertEqual(plan['visitorBindings']['5']['key'], self.owner)
        self.assertEqual([c[0] for c in self.specialists()], ['bac-' + self.owner])
        self.assertEqual(self.app.profile(self.owner), before)
        self.assertEqual(self.adapter.agents['bac-' + self.owner], self.app.workspace(self.owner))
        self.assertIn('outside your usual expertise', self.specialists()[0][2])
        self.assertIn('DEMO CODING PACE', self.specialists()[0][2])
        self.assertTrue(plan['webpages']['5'])
        self.assertFalse(job['payload']['roundtable']['members'])

    def test_suitable_hired_builder_is_preferred_without_explicit_name(self):
        builder = self.app.add_agent(self.owner, {'name': 'Maker', 'skills': ['builder']})['agentId']
        self.adapter.selection['tasks'][0]['agent'] = builder
        job = self.execute(self.start('/goal Build a counter.'))
        self.assertEqual(job['payload']['collaboration']['visitorBindings']['5']['key'], builder)

    def test_no_suitable_visitor_keeps_builtin_backup(self):
        job = self.execute(self.start('/goal Build a counter.'))
        self.assertEqual(job['payload']['collaboration']['visitorBindings'], {})
        self.assertTrue(self.specialists()[0][0].endswith('-r5'))

    def test_explicitly_excluded_builder_is_not_automatically_selected(self):
        self.app.configure(self.owner, {**self.app.profile(self.owner), 'skills': ['builder']})
        for request in ("Don't let Pixel do the coding. Build a counter.", 'Pixel은 빼고 코딩해줘.'):
            with self.subTest(request=request):
                job = self.execute(self.start('/goal ' + request))
                self.assertEqual(job['payload']['roster'], [])
                self.assertEqual(job['payload']['collaboration']['visitorBindings'], {})
                self.assertTrue(self.specialists()[-1][0].endswith('-r5'))
                self.assertFalse(any(call[0] == 'bac-' + self.owner for call in self.adapter.calls))

    def test_personal_openshell_identity_and_policy_are_preserved(self):
        self.app.configure(self.owner, {**self.app.profile(self.owner), 'name': 'Weather buddy'})
        self.owner = self.app.add_agent(self.owner, {'name': 'Pixel', 'skills': ['weather'], 'protection': 'openshell'})['agentId']
        with patch.object(self.app, 'protected_response', wraps=self.app.protected_response) as response:
            job = self.execute(self.start())
        calls = [c for c in response.call_args_list if c.args[0] == 'bac-' + self.owner]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[3:5], (self.owner, None))
        self.assertEqual(job['payload']['collaboration']['visitorBindings']['5']['protection'], 'openshell')
        self.assertEqual(self.adapter.profiles['bac-' + self.owner]['protection'], 'openshell')

    def test_explicit_builtin_name_keeps_that_agent(self):
        self.app.add_agent(self.owner, {'name': 'Maker', 'skills': ['builder']})
        job = self.execute(self.start('/goal Ask Cody to build a counter.'))
        self.assertTrue(self.specialists()[0][0].endswith('-r5'))

    def test_reported_mixed_team_dispatches_scout_then_pixel_with_verified_handoff(self):
        # Replay Casey's observed response: correct role tasks, but no agent IDs.
        # Also cover a complete initial response needing no extra model call.
        for missing_ids in (True, False):
            with self.subTest(missing_ids=missing_ids):
                self.adapter.selection = {'summary': 'Scout researches; Pixel builds the page.', 'tasks': [
                    {'role': 8, 'task': 'Research three Barcelona places.', 'inputs': [],
                     'requiredFiles': ['artifacts/research-brief.md']},
                    {'role': 5, 'task': 'Build the page from the research brief.', 'inputs': [],
                     'requiredFiles': ['artifacts/counter.html']}]}
                self.adapter.auto_agents = False
                corrected = json.loads(json.dumps(self.adapter.selection))
                corrected['tasks'][0]['agent'] = 'builtin'
                corrected['tasks'][1]['agent'] = self.owner
                self.adapter.repaired_selection = corrected
                if not missing_ids:
                    self.adapter.selection = corrected
                original = self.adapter.respond
                def reply(agent, session, prompt, **kwargs):
                    if agent.endswith('-r8') and '-working' in session:
                        self.adapter.calls.append((agent, session, prompt))
                        safe_file(self.adapter.agents[agent], 'artifacts/research-brief.md').write_text(
                            '# Fixture research\nThree fixture places with source https://example.org/tourism.')
                        return 'Saved artifacts/research-brief.md.'
                    return original(agent, session, prompt, **kwargs)
                with patch.object(self.adapter, 'respond', side_effect=reply):
                    job = self.execute(self.start(BARCELONA_REQUEST))
                plan = job['payload']['collaboration']
                self.assertEqual(job['status'], 'done')
                self.assertEqual(plan['outcome'], 'complete', plan.get('finalAnswer'))
                self.assertEqual(plan['calledRoles'], [8, 5])
                self.assertEqual(plan.get('teamSelectionRecovery', {}).get('status'), 'corrected' if missing_ids else None)
                self.assertEqual({role: m['name'] for role, m in plan['visitorBindings'].items()}, {'5': 'Pixel'})
                self.assertEqual([c[0] for c in self.specialists()[-2:]],
                                 ['bac-' + self.manager + '-r8', 'bac-' + self.owner])
                self.assertTrue(plan['verifiedSources']['8'])
                self.assertTrue(plan['webpages']['5'])
                self.assertNotIn('Cody', [p['name'] for p in self.adapter.profiles.values()])
                self.app.reset_crew_chats(self.manager)

    def test_missing_identities_are_not_guessed_after_one_failed_repair(self):
        self.adapter.auto_agents = False
        job = self.execute(self.start(BARCELONA_REQUEST))
        plan = job['payload']['collaboration']
        self.assertEqual(plan['teamSelectionRecovery']['status'], 'failed')
        self.assertEqual(plan['outcome'], 'partial')
        self.assertEqual(self.specialists(), [])
        self.assertEqual(sum('-planning-team-repair' in c[1] for c in self.adapter.calls), 1)

    def test_explicit_model_bindings_are_not_rewritten_by_old_role_hints(self):
        from visitor_teams import bind
        pixel = {**self.app.profile(self.owner), 'key': self.owner}
        with self.app.db() as db:
            roster = self.app.crew_roster(db, self.manager, {}, preset=True)
        plan = {'summary': 'Scout researches and Pixel codes.', 'tasks': [
            {'role': 8, 'agent': 'builtin', 'task': 'Find places.'},
            {'role': 5, 'agent': self.owner, 'task': 'Build the guide.'}]}
        required = [{'key': self.owner, 'name': 'Pixel', 'role': 8}]
        bind(plan, roster, [pixel], required, BARCELONA_REQUEST)
        self.assertEqual([t['name'] for t in plan['tasks']], ['Scout', 'Pixel'])
        self.assertEqual([t['role'] for t in plan['tasks']], [8, 5])

    def test_confirmed_builtin_choice_is_not_replaced_by_a_suitable_hire(self):
        self.app.configure(self.owner, {**self.app.profile(self.owner), 'skills': ['builder']})
        self.adapter.selection['tasks'][0]['agent'] = 'builtin'
        job = self.execute(self.start('/goal Let Cody build a counter.'))
        self.assertEqual(job['payload']['collaboration']['visitorBindings'], {})
        self.assertTrue(self.specialists()[0][0].endswith('-r5'))

    def test_required_participant_is_added_when_casey_attempts_direct_answer(self):
        self.adapter.repaired_selection = self.adapter.selection
        self.adapter.selection = {'summary': 'No help needed.', 'tasks': [], 'answer': 'Here is a draft.'}
        job = self.execute(self.start())
        self.assertEqual([c[0] for c in self.specialists()], ['bac-' + self.owner])
        self.assertEqual(job['payload']['collaboration']['tasks'][0]['role'], 5)

    def test_missing_or_foreign_agent_id_cannot_be_dispatched(self):
        self.adapter.selection['tasks'][0]['agent'] = 'f' * 24
        with self.assertRaisesRegex(RuntimeError, 'outside the available'):
            self.execute(self.start('/goal Build a counter.'))
        self.assertEqual(self.specialists(), [])

    def test_named_busy_agent_is_not_silently_replaced(self):
        self.app.enqueue(self.owner, {'kind': 'chat', 'prompt': 'Weather now?'})
        with self.assertRaisesRegex(Problem, 'Pixel is busy'):
            self.start()

    def test_disconnected_lounge_uses_backups_unless_personal_agent_is_named(self):
        status = {'ready': False, 'gateway': True, 'model': False, 'teamReady': True, 'teamModel': True}
        with patch.object(self.app, 'runtime_status', return_value=status):
            with self.assertRaisesRegex(Problem, 'Local model is not connected'):
                self.start()
            job = self.execute(self.start('/goal Build a counter.'))
        self.assertEqual(job['payload']['roster'], [])
        self.assertTrue(self.specialists()[-1][0].endswith('-r5'))

    def test_unnamed_busy_agent_is_not_reserved(self):
        self.app.enqueue(self.owner, {'kind': 'chat', 'prompt': 'Weather now?'})
        job = self.execute(self.start('/goal Build a counter.'))
        self.assertEqual(job['payload']['roster'], [])

    def test_cancelled_plan_never_calls_named_agent(self):
        result = self.start()
        self.app.decision(self.manager, result['id'], 'cancel')
        self.execute(result)
        self.assertEqual(self.specialists(), [])

    def test_scenario_reset_keeps_personal_agent_and_original_files(self):
        self.execute(self.start())
        profile = self.app.profile(self.owner)
        self.app.reset_crew_chats(self.manager)
        self.assertEqual(self.app.profile(self.owner), profile)
        self.assertTrue(safe_file(self.app.workspace(self.owner), 'artifacts/counter.html').is_file())
        with self.app.db() as db:
            self.assertFalse(db.execute("SELECT 1 FROM jobs WHERE owner=? AND kind='crew-chat'", (self.manager,)).fetchone())
        job = self.execute(self.start())
        self.assertEqual(job['payload']['collaboration']['visitorBindings']['5']['id'], profile['id'])

    def test_deletion_cancels_pending_plan_instead_of_leaving_a_reserved_agent(self):
        result = self.start()
        self.app.delete_agent(self.owner, {'name': 'Pixel'}, enqueue_only=True)
        with self.app.db() as db:
            job = db.execute('SELECT status FROM jobs WHERE id=?', (result['id'],)).fetchone()
        self.assertEqual(job['status'], 'cancelled')
        self.execute(result)
        self.assertEqual(self.specialists(), [])

    def test_named_agent_keeps_context_recovery_and_saved_work(self):
        self.adapter.fail_once = True
        job = self.execute(self.start())
        plan = job['payload']['collaboration']
        self.assertEqual(plan['outputLimitRetry']['status'], 'recovered')
        self.assertEqual([c[0] for c in self.specialists()], ['bac-' + self.owner] * 2)
        self.assertIn('CONTEXT RECOVERY', self.specialists()[1][2])
        self.assertTrue(plan['webpages']['5'])

    def test_changed_profile_rejected_before_specialist_call(self):
        def change(agent, session):
            if session.endswith('-planning'):
                with self.app.db() as db:
                    profile = self.app.profile(self.owner)
                    profile['tonePrompt'] = 'Changed.'
                    db.execute('UPDATE agents SET profile=? WHERE id=?', (json.dumps(profile), self.owner))
        self.adapter.after = change
        with self.assertRaisesRegex(Problem, 'changed after'):
            self.execute(self.start())
        self.assertEqual(self.specialists(), [])

    def test_reservation_blocks_edits_and_new_chat(self):
        self.start()
        with self.assertRaises(Problem):
            self.app.configure(self.owner, {**self.app.profile(self.owner), 'name': 'Other'})
        with self.assertRaises(Problem):
            self.app.enqueue(self.owner, {'kind': 'chat', 'prompt': 'Overlap'})

    def test_required_peer_cannot_be_skipped_by_success_checkpoint(self):
        self.adapter.check_done = True
        self.adapter.selection['tasks'].insert(0, {'role': 6, 'agent': 'builtin', 'task': 'Describe the counter.'})
        job = self.execute(self.start())
        self.assertEqual(job['payload']['collaboration']['calledRoles'], [6, 5])
        self.assertEqual(self.specialists()[-1][0], 'bac-' + self.owner)

    def test_research_budget_is_shared_with_hired_agent(self):
        self.adapter.selection['tasks'] = [{'role': 8, 'task': 'Research.', 'requiredFiles': []}]
        job = self.execute(self.start('/goal Ask Pixel to research the weather.'))
        self.assertEqual(job['payload']['collaboration']['researchBudgetSeconds'], 150)
        self.assertEqual(self.specialists()[0][0], 'bac-' + self.owner)

    def test_named_agent_still_attempts_work_after_missing_upstream_handoff(self):
        self.adapter.selection['tasks'].insert(0, {'role': 8, 'agent': 'builtin', 'task': 'Research counter design.',
                                                 'requiredFiles': ['artifacts/research.md']})
        job = self.execute(self.start())
        plan = job['payload']['collaboration']
        self.assertEqual(plan['calledRoles'], [8, 5])
        self.assertEqual(self.specialists()[-1][0], 'bac-' + self.owner)
        self.assertIn('Upstream work is incomplete', self.specialists()[-1][2])
        self.assertTrue(plan['webpages']['5'])
        self.assertEqual(plan['outcome'], 'partial')
        self.assertIn('artifacts/research.md', plan['finalAnswer'])

    def test_named_agent_cannot_be_skipped_by_partial_checkpoint(self):
        self.adapter.check_done = self.adapter.check_partial = True
        self.adapter.selection['tasks'].insert(0, {'role': 6, 'agent': 'builtin', 'task': 'Describe the counter.'})
        job = self.execute(self.start())
        self.assertEqual(job['payload']['collaboration']['calledRoles'], [6, 5])
        self.assertEqual(job['payload']['collaboration']['outcome'], 'partial')
        self.assertEqual(self.specialists()[-1][0], 'bac-' + self.owner)

    def test_name_in_quote_code_negative_or_substring_is_not_forced(self):
        members = [{'name': 'Pixel', 'key': self.owner}]
        for task in ('> Ask Pixel to code.', '```Ask Pixel to code.```', 'Do not use Pixel to code.',
                     'Pixel은 제외하고 만들어줘.', 'Use Pixelated graphics.'):
            with self.subTest(task=task):
                self.assertEqual(requirements(task, members), [])
