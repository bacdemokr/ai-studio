"""BaC reset drains in-flight work without resetting unrelated workspaces."""
import concurrent.futures
import json
import tempfile
import threading
import unittest

from test_studio import Adapter, Studio, Problem
from test_parallel_crew import ParallelAdapter


class BacResetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.adapter = Adapter()
        self.app = Studio(self.temp.name, self.adapter, start_worker=False)
        self.owner = self.app.session()[0]['id']
        self.team = self.app.crew_owner(self.owner)

    def chat(self, owner=None):
        return self.app.enqueue(owner or self.team, {'kind': 'crew-chat', 'crewRole': 0, 'prompt': 'Hello'})

    def test_running_chat_blocks_new_bac_work_until_drain_and_drops_late_reply(self):
        entered, release = threading.Event(), threading.Event()
        original = self.adapter.respond

        def respond(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('Test did not release the model call')
            return original(*args, **kwargs)

        self.adapter.respond = respond
        job = self.chat()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(self.app.execute, self.app.next_job())
            try:
                self.assertTrue(entered.wait(5))
                reset = self.app.reset_crew_chats(self.owner, reset_event=True)
                self.assertTrue(reset['resetting'])
                state = self.app.state(self.owner)
                self.assertTrue(state['bacResetting'])
                self.assertEqual(state['crewChats'][0]['status'], 'stopping')
                for submit in (
                    self.chat,
                    lambda: self.app.prepare_demo(self.team, {}),
                    lambda: self.app.enqueue(self.team, {'kind': 'crew', 'preset': True, 'brief': {'schema': 2}}),
                ):
                    with self.assertRaises(Problem) as error:
                        submit()
                    self.assertEqual(error.exception.status, 409)
                self.app.finish_pending_bac_resets()
                self.assertTrue(self.app.state(self.owner)['bacResetting'])
            finally:
                release.set()
            running.result(timeout=5)
        self.app.finish_pending_bac_resets()
        state = self.app.state(self.owner)
        self.assertFalse(state['bacResetting'])
        self.assertEqual(state['crewChats'], [])
        self.app.event(job['id'], 'Late result', '', status='done', result=json.dumps({'answer': 'STALE'}))
        self.assertEqual(self.app.state(self.owner)['crewChats'], [])
        self.chat()
        self.app.execute(self.app.next_job())
        self.assertEqual(self.app.state(self.owner)['crewChats'][0]['status'], 'done')
        self.assertNotEqual(self.adapter.calls[0][1], self.adapter.calls[1][1])

    def test_parallel_specialists_drain_without_starting_next_role(self):
        self.adapter = ParallelAdapter()
        self.app.adapter = self.adapter
        job = self.app.enqueue(self.team, {'kind': 'crew', 'preset': True, 'brief': {'schema': 2}})
        resets = []

        def reset():
            resets.append(self.app.reset_crew_chats(self.owner, reset_event=True))
            self.app.finish_pending_bac_resets()
            self.assertTrue(self.app.state(self.owner)['bacResetting'])

        self.adapter.on_pair = reset
        self.app.execute(self.app.next_job())
        self.assertTrue(resets[0]['resetting'])
        self.assertEqual(set(self.adapter.finished), {0, 1, 2})
        with self.app.db() as db:
            self.assertEqual(db.execute('SELECT status FROM jobs WHERE id=?', (job['id'],)).fetchone()['status'], 'cancelled')
        self.app.finish_pending_bac_resets()
        self.assertFalse(self.app.state(self.owner)['bacResetting'])
        self.assertEqual(self.app.state(self.owner)['jobs'], [])

    def test_reset_waits_for_post_processing_even_after_job_is_marked_done(self):
        job = self.chat()
        self.app.next_job()
        self.app.event(job['id'], 'Reply saved', '', status='done')
        self.app.executing_bac_owners = {self.team}
        self.assertTrue(self.app.reset_crew_chats(self.owner, reset_event=True)['resetting'])
        self.app.finish_pending_bac_resets()
        self.assertTrue(self.app.state(self.owner)['bacResetting'])
        self.app.executing_bac_owners.clear()
        self.app.finish_pending_bac_resets()
        self.assertEqual(self.app.state(self.owner)['crewChats'], [])
        fresh = self.chat()
        self.app.reset_crew_chats(self.owner, reset_event=True, pending_only=True)
        with self.app.db() as db:
            self.assertEqual(db.execute('SELECT status FROM jobs WHERE id=?', (fresh['id'],)).fetchone()['status'], 'queued')

    def test_pending_reset_survives_restart_and_preserves_personal_and_other_accounts(self):
        self.app.onboard(self.owner, {'name': 'Personal', 'skills': ['documents']})
        personal = self.app.enqueue(self.owner, {'kind': 'chat', 'prompt': 'Keep personal history'})
        self.app.execute(self.app.next_job())
        other = self.app.session()[0]['id']
        other_job = self.chat(self.app.crew_owner(other))
        self.app.execute(self.app.next_job())
        self.chat()
        self.app.next_job()
        self.assertTrue(self.app.reset_crew_chats(self.owner, reset_event=True)['resetting'])
        restarted = Studio(self.temp.name, self.adapter, start_worker=False, recover=True)
        restarted.finish_pending_bac_resets()
        state = restarted.state(self.owner)
        self.assertFalse(state['bacResetting'])
        self.assertEqual(state['crewChats'], [])
        self.assertEqual(state['jobs'][0]['id'], personal['id'])
        self.assertEqual(restarted.state(other)['crewChats'][0]['id'], other_job['id'])

    def test_queued_and_waiting_work_is_cancelled_without_model_calls(self):
        for status in ('queued', 'waiting'):
            with self.subTest(status=status):
                job = self.app.enqueue(self.team, {'kind': 'crew', 'preset': True, 'brief': {'schema': 2}})
                with self.app.db() as db:
                    db.execute('UPDATE jobs SET status=? WHERE id=?', (status, job['id']))
                self.assertTrue(self.app.reset_crew_chats(self.owner, reset_event=True)['reset'])
                self.assertIsNone(self.app.next_job())
                self.assertEqual(self.adapter.calls, [])
                self.assertEqual(self.app.state(self.owner)['jobs'], [])

    def test_running_preparation_stops_before_preparing_next_agent(self):
        original = self.app.prepare_builtin_crew
        prepared = []

        def prepare(*args):
            result = original(*args)
            prepared.append(args[1])
            self.assertTrue(self.app.reset_crew_chats(self.owner, reset_event=True)['resetting'])
            return result

        self.app.prepare_builtin_crew = prepare
        self.app.prepare_demo(self.team, {})
        self.app.execute(self.app.next_job())
        self.app.finish_pending_bac_resets()
        self.assertEqual(prepared, [0])
        self.assertEqual(self.adapter.calls, [])
        self.assertFalse(self.app.state(self.owner)['preparation'])
        self.assertFalse(self.app.state(self.owner)['bacResetting'])


if __name__ == '__main__':
    unittest.main()
