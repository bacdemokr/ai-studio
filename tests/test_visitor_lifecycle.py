"""Exercise late completions and autonomous agents across real dispatcher boundaries."""
import json
import threading
import time
import unittest
from unittest.mock import patch

import test_visitor_teams as fixtures
from studio import Problem, safe_file
from telemetry import Reply


class VisitorLifecycleTests(unittest.TestCase):
    setUp = fixtures.VisitorTeamTests.setUp
    start = fixtures.VisitorTeamTests.start
    execute = fixtures.VisitorTeamTests.execute
    specialists = fixtures.VisitorTeamTests.specialists

    def block_specialist(self):
        entered, release = threading.Event(), threading.Event()
        def delay(agent, session):
            if '-working' in session:
                entered.set()
                if not release.wait(10):
                    raise RuntimeError('Test did not release the pending model call')
        self.adapter.after = delay
        result = self.start()
        errors = []
        def run():
            try:
                self.execute(result)
            except Exception as error:
                errors.append(error)
        thread = threading.Thread(target=run)
        thread.start()
        self.addCleanup(lambda: (release.set(), thread.join(10)))
        self.assertTrue(entered.wait(10), errors)
        return result, release, thread, errors

    def test_cancel_and_immediate_off_retry_waits_for_late_call_without_reset(self):
        first, release, thread, errors = self.block_specialist()
        self.assertEqual(self.app.decision(self.manager, first['id'], 'cancel')['status'], 'stopping')
        with self.assertRaises(Problem):
            self.start('/goal Build a counter.', includeHiredAgents=False)
        release.set(); thread.join(10)
        self.assertFalse(thread.is_alive()); self.assertEqual(errors, [])
        with self.app.db() as db:
            self.assertEqual(db.execute('SELECT status FROM jobs WHERE id=?', (first['id'],)).fetchone()[0], 'cancelled')
        # The late call may save its own file, but must not start more roles or reactions.
        self.assertFalse(any('-reviewing' in c[1] or 'roundtable' in c[1] for c in self.adapter.calls))
        self.adapter.after = None
        second = self.execute(self.start('/goal Build a counter.', includeHiredAgents=False))
        self.assertEqual(second['status'], 'done')
        self.assertFalse(second['payload']['collaboration'].get('visitorBindings'))
        self.assertEqual(self.specialists()[-1][0], 'bac-' + self.manager + '-r5')
        self.assertEqual(second['payload']['roundtable']['replies'][self.owner]['status'], 'done')
        self.assertFalse(self.app.executing_owners)

    def test_reset_during_late_call_finishes_before_off_retry_and_preserves_other_room(self):
        event = self.app.crew_owner(self.owner, 'event-brief')
        sentinel = safe_file(self.app.workspace(event, 0), 'artifacts/event-sentinel.txt')
        sentinel.write_text('Keep Event Brief')
        personal = safe_file(self.app.workspace(self.owner), 'inbox/personal.txt')
        personal.write_text('Keep personal upload')
        first, release, thread, errors = self.block_specialist()
        reset = self.app.reset_crew_chats(self.manager, reset_event=True)
        self.assertTrue(reset['resetting'])
        self.app.finish_pending_bac_resets()
        with self.assertRaisesRegex(Problem, 'resetting'):
            self.start('/goal Build a counter.', includeHiredAgents=False)
        release.set(); thread.join(10)
        self.assertFalse(thread.is_alive()); self.assertEqual(errors, [])
        self.app.finish_pending_bac_resets()
        with self.app.db() as db:
            self.assertIsNone(db.execute('SELECT id FROM jobs WHERE id=?', (first['id'],)).fetchone())
        self.assertEqual(sentinel.read_text(), 'Keep Event Brief')
        self.assertEqual(personal.read_text(), 'Keep personal upload')
        self.assertFalse(list(self.app.workspace(self.manager).glob('artifacts/*')))
        self.adapter.after = None
        second = self.execute(self.start('/goal Build a counter.', includeHiredAgents=False))
        self.assertEqual(second['status'], 'done')
        self.assertFalse(second['payload']['collaboration'].get('visitorBindings'))
        self.assertEqual(sentinel.read_text(), 'Keep Event Brief')

    def radar(self):
        self.app.configure(self.owner, {**self.app.profile(self.owner), 'skills': ['radar', 'builder']})
        while (row := self.app.next_job()) is not None:
            self.app.execute(row)
        cadence = {}
        def toggle(agent, enabled):
            cadence[agent] = enabled
            return agent in self.adapter.agents
        self.adapter.set_radar_heartbeat = toggle
        self.app.heartbeat.presence(self.owner, 'visitor-lifecycle')
        with self.app.db() as db:
            db.execute("UPDATE jobs SET created=? WHERE kind='prepare-agent'", (time.time()-30,))
        self.tick()
        self.assertTrue(cadence['bac-' + self.owner])
        return cadence

    def tick(self):
        with patch('runtime_settings.model_available', return_value=True):
            self.app.heartbeat.tick()

    def test_radar_is_suspended_before_selected_specialist_and_resumes_after(self):
        cadence = self.radar()
        observed = []
        def observe(agent, session):
            if agent == 'bac-' + self.owner and '-working' in session:
                observed.append(cadence[agent])
                self.tick()
                self.assertFalse(cadence[agent])
        self.adapter.after = observe
        result = self.execute(self.start())
        self.assertEqual(result['status'], 'done')
        self.assertEqual(observed, [False], 'Heartbeat remained enabled until the next background tick')
        self.tick()
        self.assertTrue(cadence['bac-' + self.owner])
        self.assertEqual(self.app.heartbeat.status(self.owner, self.app.profile(self.owner))['state'], 'watching')

    def test_user_pause_during_assignment_survives_completion(self):
        cadence = self.radar()
        def pause(agent, session):
            if '-working' in session:
                self.app.heartbeat.control(self.owner, {'paused': True})
        self.adapter.after = pause
        self.assertEqual(self.execute(self.start())['status'], 'done')
        self.tick()
        self.assertFalse(cadence['bac-' + self.owner])
        self.assertTrue(self.app.heartbeat.status(self.owner, self.app.profile(self.owner))['paused'])

    def test_cancel_releases_radar_after_call_drains(self):
        cadence = self.radar()
        first, release, thread, errors = self.block_specialist()
        self.tick(); self.assertFalse(cadence['bac-' + self.owner])
        self.app.decision(self.manager, first['id'], 'cancel')
        self.tick(); self.assertFalse(cadence['bac-' + self.owner])
        release.set(); thread.join(10)
        self.assertEqual(errors, [])
        self.tick(); self.assertTrue(cadence['bac-' + self.owner])

    def test_off_reaction_failure_preserves_completed_builtin_deliverable(self):
        def fail(agent, session):
            if session.startswith('bac-roundtable-'):
                raise RuntimeError('Fixture Lounge model disconnected')
        self.adapter.after = fail
        with self.assertLogs(level='ERROR'):
            result = self.execute(self.start('/goal Build a counter.', includeHiredAgents=False))
        self.assertEqual(result['status'], 'done')
        self.assertEqual(result['payload']['collaboration']['outcome'], 'complete')
        self.assertEqual(result['payload']['roundtable']['replies'][self.owner]['status'], 'error')
        self.assertTrue(result['result']['files'])
        self.assertIn('team delivered', result['result']['answer'])

    def test_same_person_changes_role_without_reset_and_gets_new_assignment(self):
        self.execute(self.start())
        self.adapter.selection['tasks'][0]['role'] = 6
        result = self.execute(self.start('/goal Have Pixel analyze store sales: 2 plus 3.'))
        bindings = result['payload']['collaboration']['visitorBindings']
        self.assertEqual(list(bindings), ['6'])
        self.assertEqual(bindings['6']['key'], self.owner)
        self.assertNotIn('-5-working', self.specialists()[-1][1])
        self.assertIn('-6-working', self.specialists()[-1][1])
        self.assertEqual(self.specialists()[-1][0], 'bac-' + self.owner)

    def read_existing_instead_of_writing(self, *, observed=True, status='completed', target='artifacts/counter.html'):
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            if '-working' in session or '-recovering' in session:
                self.adapter.calls.append((agent, session, prompt))
                safe_file(self.adapter.agents[agent], 'artifacts/counter.html', True).read_text()
                answer = Reply('The existing artifacts/counter.html already meets the request. Static inspection only.', {})
                if observed:
                    answer.activity = {'source': 'OpenClaw transcript', 'available': True,
                                       'calls': [{'tool': 'read', 'target': target, 'status': status}]}
                return answer
            return original(agent, session, prompt, **kwargs)
        return patch.object(self.adapter, 'respond', side_effect=respond)

    def test_off_on_off_can_reuse_the_inspected_builtin_page_without_a_rewrite(self):
        first = self.execute(self.start('/goal Build a counter.', includeHiredAgents=False))
        self.execute(self.start())
        with self.read_existing_instead_of_writing():
            last = self.execute(self.start('/goal Build a counter.', includeHiredAgents=False))
        plan = last['payload']['collaboration']
        self.assertEqual(plan['outcome'], 'complete')
        self.assertEqual(plan['reusedSources']['5'], ['artifacts/counter.html'])
        self.assertNotIn('handoffRecovery', plan)
        self.assertEqual(last['payload']['roundtable']['replies'][self.owner]['status'], 'done')
        self.assertTrue(last['result']['files'])
        self.assertNotEqual(first['result']['files'], last['result']['files'])
        self.assertEqual((self.app.workspace(self.manager)/first['result']['files'][0]).read_bytes(),
                         (self.app.workspace(self.manager)/last['result']['files'][0]).read_bytes())

    def test_existing_page_claim_requires_current_successful_read(self):
        self.execute(self.start('/goal Build a counter.', includeHiredAgents=False))
        for options in ({'observed': False}, {'status': 'failed'}, {'target': 'artifacts/other.html'}):
            with self.subTest(options=options), self.read_existing_instead_of_writing(**options):
                job = self.execute(self.start('/goal Build a counter.', includeHiredAgents=False))
                self.assertEqual(job['payload']['collaboration']['outcome'], 'partial')
                self.assertFalse(job['payload']['collaboration']['outputs']['5']['files'])

    def test_old_export_must_match_current_source_and_cannot_cross_identities(self):
        self.execute(self.start('/goal Build a counter.', includeHiredAgents=False))
        original = safe_file(self.app.workspace(self.manager, 5), 'artifacts/counter.html').read_bytes()
        safe_file(self.app.workspace(self.manager, 5), 'artifacts/counter.html').write_text('<html>Unverified change</html>')
        with self.read_existing_instead_of_writing():
            result = self.execute(self.start('/goal Build a counter.', includeHiredAgents=False))
        self.assertEqual(result['payload']['collaboration']['outcome'], 'partial')
        # Pixel did not produce the earlier verified export, even if its local file is identical.
        safe_file(self.app.workspace(self.owner), 'artifacts/counter.html').write_bytes(original)
        with self.read_existing_instead_of_writing():
            result = self.execute(self.start())
        self.assertEqual(result['payload']['collaboration']['outcome'], 'partial')

    def test_reset_does_not_reuse_old_hired_agent_exports(self):
        self.execute(self.start())
        self.app.reset_crew_chats(self.manager, reset_event=True)
        self.assertTrue(safe_file(self.app.workspace(self.owner), 'artifacts/counter.html', True).is_file())
        with self.read_existing_instead_of_writing():
            result = self.execute(self.start())
        self.assertEqual(result['payload']['collaboration']['outcome'], 'partial')
        self.assertFalse(result['payload']['collaboration']['outputs']['5']['files'])

    def test_partial_history_cannot_certify_unchanged_code(self):
        first = self.execute(self.start())
        payload = first['payload']; payload['collaboration']['outcome'] = 'partial'
        with self.app.db() as db:
            db.execute('UPDATE jobs SET payload=? WHERE id=?', (json.dumps(payload), first['id']))
        with self.read_existing_instead_of_writing():
            result = self.execute(self.start())
        self.assertEqual(result['payload']['collaboration']['outcome'], 'partial')
