"""Real queue/identity/protection boundaries for optional /plan audience reactions."""
import json
import unittest
from unittest.mock import patch
import test_collaboration_plan as fixture
from studio import Problem


class PlanRoundtableTests(unittest.TestCase):
    setUp = fixture.CollaborationTests.setUp
    start = fixture.CollaborationTests.start
    job = fixture.CollaborationTests.job

    def test_guest_reacts_to_repaired_result_without_stale_contribution(self):
        from crew_roundtable import reaction_context
        plan = {'task': 'Calculate total', 'finalAnswer': 'Total is 450',
                'outputs': {'6': {'name': 'Ada', 'answer': 'Total is 999'}},
                'revision': {'role': 6, 'status': 'delivered',
                             'output': {'name': 'Ada', 'answer': 'Corrected total is 450'}}}
        context = reaction_context({'collaboration': plan})
        self.assertIn('Corrected total is 450', context)
        self.assertNotIn('999', context)
        plan['revision']['status'] = 'failed'
        self.assertIn('999', reaction_context({'collaboration': plan}))

    def hire(self, name='Muse', **values):
        return self.app.add_agent(self.owner, dict(name=name, skills=['writer'], purpose='Poetry and unexpected metaphors.',
            tonePrompt='Gentle and dreamy. Never sarcastic.', **values))['agentId']

    def test_actual_result_then_personal_voices_and_durable_history(self):
        muse = self.hire()
        other = self.app.session()[0]['id']
        self.app.onboard(other, {'name':'Private', 'skills':['web']})
        (self.app.workspace(muse)/'inbox/private.txt').write_text('PRIVATE_UPLOAD')
        result = self.start()
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            if session.startswith('bac-roundtable-'):
                current = self.job(result)
                self.assertEqual(current['status'], 'running')
                self.assertIn('combined proposal', current['result']['answer'])
                self.assertTrue(current['payload']['collaboration']['responseReady'])
                self.assertTrue(self.app.available_file(self.owner, current['result']['files'][0]).exists())
            return original(agent, session, prompt, **kwargs)
        self.adapter.respond = respond
        self.app.execute(self.app.next_job())
        job = self.job(result)
        self.assertEqual(job['status'], 'done')
        replies = job['payload']['roundtable']['replies']
        self.assertEqual(set(replies), {self.owner, muse})
        prompt = self.adapter.reaction_calls[-1][2]
        for text in ('Gentle and dreamy', 'Poetry and unexpected metaphors', 'combined proposal',
                     'Verified contribution from Scout', 'No browsing, file changes', 'not as an assigned specialist'):
            self.assertIn(text, prompt)
        self.assertIn(replies[self.owner]['answer'], prompt)
        self.assertNotIn('PRIVATE_UPLOAD', prompt)
        self.assertEqual(self.app.state(other)['roundtableTurns'], [])
        restarted = fixture.Studio(self.temp.name, self.adapter, start_worker=False)
        self.assertEqual(restarted.state(muse)['roundtableTurns'][0]['result']['answer'], replies[muse]['answer'])

    def test_failure_retry_only_guest_preserves_answer_and_specialists(self):
        guest = self.hire()
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            if session.startswith('bac-roundtable-') and agent == 'bac-'+guest:
                raise RuntimeError('Temporary guest failure')
            return original(agent, session, prompt, **kwargs)
        self.adapter.respond = respond
        result = self.start()
        with self.assertLogs(level='ERROR'): self.app.execute(self.app.next_job())
        before = self.job(result)
        self.assertEqual(before['status'], 'done')
        self.assertEqual(before['payload']['roundtable']['replies'][guest]['status'], 'error')
        calls = list(self.adapter.calls)
        self.adapter.respond = original
        self.app.retry_reaction(self.app.crew_owner(self.owner), {'id':result['id'],'member':guest})
        self.app.execute(self.app.next_job())
        after = self.job(result)
        self.assertEqual(after['result'], before['result'])
        self.assertEqual(self.adapter.calls, calls)
        self.assertEqual(after['payload']['roundtable']['replies'][guest]['status'], 'done')
        self.assertEqual(after['payload']['roundtable']['replies'][guest]['attempt'], 2)

    def test_protection_not_verified_skips_guest_without_bypass(self):
        guest = self.hire(protection='openshell')
        original = self.app.check_protected_run
        def check(key, profile):
            if key == guest:
                from studio_policy import ProtectionNotVerified
                raise ProtectionNotVerified('unavailable')
            return original(key, profile)
        result = self.start()
        # Drain the hired agent's queued preparation separately if necessary.
        with patch.object(self.app, 'check_protected_run', check), self.assertLogs(level='ERROR'):
            self.app.execute(self.app.next_job())
        self.assertEqual(self.job(result)['status'], 'done')
        self.assertFalse(any(agent=='bac-'+guest for agent,_,_ in self.adapter.reaction_calls))
        self.assertIn('OpenShell protection', self.job(result)['payload']['roundtable']['replies'][guest]['error'])

    def test_cancel_during_guest_discards_late_reply_and_keeps_result(self):
        self.hire()
        result = self.start()
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            if session.startswith('bac-roundtable-'):
                self.app.decision(self.app.crew_owner(self.owner), result['id'], 'cancel')
            return original(agent, session, prompt, **kwargs)
        self.adapter.respond = respond
        self.app.execute(self.app.next_job())
        job = self.job(result)
        self.assertEqual(job['status'], 'cancelled')
        self.assertIn('combined proposal', job['result']['answer'])
        self.assertEqual(len(self.adapter.reaction_calls), 1)
        self.assertFalse(any(r.get('answer') for r in job['payload']['roundtable']['replies'].values()))

    def test_reset_during_guest_stops_next_guest_and_clears_history(self):
        self.hire()
        self.start()
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            if session.startswith('bac-roundtable-'):
                self.assertTrue(self.app.reset_crew_chats(self.owner, reset_event=True)['resetting'])
            return original(agent, session, prompt, **kwargs)
        self.adapter.respond = respond
        self.app.execute(self.app.next_job())
        self.app.finish_pending_bac_resets()
        self.assertEqual(len(self.adapter.reaction_calls), 1)
        self.assertEqual(self.app.state(self.owner)['crewChats'], [])
        self.assertEqual(self.app.state(self.owner)['roundtableTurns'], [])

    def test_queued_guest_is_fenced_and_delete_cancels_before_any_call(self):
        guest = self.hire()
        result = self.start()
        with self.app.db() as db, self.assertRaises(Problem): self.app.require_idle(db, guest)
        self.app.delete_agent(guest, {'name':'Muse'})
        self.assertEqual(self.job(result)['status'], 'cancelled')
        self.assertEqual(self.adapter.reaction_calls, [])
        self.assertFalse(self.app.workspace(guest).exists())

    def test_busy_deleted_other_collection_guests_are_not_invited(self):
        busy = self.hire('Busy')
        deleting = self.hire('Deleting')
        self.app.enqueue(busy, {'kind':'chat','prompt':'An existing task'})
        with self.app.db() as db: db.execute('UPDATE agents SET deleting=1 WHERE id=?', (deleting,))
        result = self.start()
        meeting = self.job(result)['payload']['roundtable']
        self.assertEqual([m['key'] for m in meeting['members']], [self.owner])
        self.assertIn(busy, [m['key'] for m in meeting['skipped']])

    def test_unavailable_capability_and_empty_lounge_do_not_add_model_calls(self):
        self.adapter.plan = {'summary':'No capability.', 'tasks':[], 'outcome':'unavailable','answer':'Cannot deploy.'}
        result = self.start(); self.app.execute(self.app.next_job())
        self.assertEqual(self.job(result)['status'], 'done')
        self.assertEqual(self.adapter.reaction_calls, [])
        empty = self.app.session()[0]['id']
        self.adapter.plan = {'summary':'Simple answer.', 'tasks':[], 'answer':'Four.'}
        self.app.enqueue(self.app.crew_owner(empty), {'kind':'crew-chat','crewRole':0,'prompt':'/plan Two plus two?'})
        self.app.execute(self.app.next_job())
        self.assertEqual(self.adapter.reaction_calls, [])


if __name__ == '__main__': unittest.main()
