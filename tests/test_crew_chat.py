import json
import tempfile
import unittest
from test_studio import Adapter, Studio, Problem

class CrewChatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.adapter = Adapter()
        self.studio = Studio(self.temp.name, self.adapter, start_worker=False)
        self.person, _ = self.studio.session()
        self.owner = self.person['id']

    def send(self, role, prompt):
        job = self.studio.enqueue(self.studio.crew_owner(self.owner), {'kind': 'crew-chat', 'crewRole': role, 'prompt': prompt})
        self.studio.execute(self.studio.next_job())
        return job

    def test_roles_have_native_identity_and_separate_persistent_conversations(self):
        self.send(0, 'Help plan my event')
        self.send(8, 'Research a topic')
        self.send(0, 'Make the plan shorter')
        state = self.studio.state(self.owner)
        self.assertEqual(state['jobs'], [])
        self.assertEqual(len(state['crewChats']), 3)
        self.assertTrue(all(j['status'] == 'done' for j in state['crewChats']))
        self.assertEqual(len(self.adapter.agents), 2)
        profiles = list(self.adapter.profiles.values())
        self.assertEqual([p['name'] for p in profiles], ['Casey', 'Scout'])
        self.assertIn('Choose the specialists', profiles[0]['purpose'])
        calls = self.adapter.calls
        self.assertEqual(calls[0][1], calls[2][1])
        self.assertNotEqual(calls[0][1], calls[1][1])
        restarted = Studio(self.temp.name, self.adapter, start_worker=False)
        self.assertEqual(len(restarted.state(self.owner)['crewChats']), 3)
        other, _ = self.studio.session()
        self.assertEqual(self.studio.state(other['id'])['crewChats'], [])


    def test_reset_covers_collection_but_not_other_participants_or_personal_chat(self):
        self.studio.onboard(self.owner, {'name':'Personal','skills':['documents']})
        second=self.studio.add_agent(self.owner, {'name':'Second','skills':['documents']})['agentId']
        outsider=self.studio.session()[0]['id']
        for owner in (self.owner,second,outsider):
            self.studio.enqueue(self.studio.crew_owner(owner), {'kind':'crew-chat','crewRole':0,'prompt':'Hello'})
            self.studio.execute(self.studio.next_job())
        personal=self.studio.enqueue(self.owner, {'kind':'chat','prompt':'Keep my personal conversation'})
        self.studio.execute(self.studio.next_job())
        self.studio.reset_crew_chats(second)
        self.assertEqual(self.studio.state(self.owner)['crewChats'],[])
        self.assertEqual(self.studio.state(second)['crewChats'],[])
        self.assertEqual(len(self.studio.state(outsider)['crewChats']),1)
        self.assertEqual(self.studio.state(outsider)['crewChatReset']['epoch'],'')
        self.assertEqual(self.studio.state(self.owner)['jobs'][0]['id'],personal['id'])

    def test_personal_agent_deletion_does_not_block_crew_chat_reset(self):
        self.studio.onboard(self.owner, {'name':'Personal','skills':['documents']})
        other=self.studio.add_agent(self.owner, {'name':'Other','skills':['documents']})['agentId']
        for deletion_state in (1,2):
            with self.subTest(deletion_state=deletion_state):
                self.send(0,'Old crew conversation')
                with self.studio.db() as db:
                    db.execute('UPDATE agents SET deleting=? WHERE id=?',(deletion_state,other))
                before=self.studio.state(self.owner)
                result=self.studio.reset_crew_chats(other)
                after=self.studio.state(self.owner)
                self.assertEqual(result['removed'],1)
                self.assertEqual(after['crewChats'],[])
                self.assertNotEqual(after['crewChatReset']['epoch'],before['crewChatReset']['epoch'])
                self.assertEqual(after['agents'],before['agents'])
                self.assertEqual(after['jobs'],before['jobs'])
                self.assertEqual(after['files'],before['files'])
                with self.studio.db() as db:
                    self.assertEqual(db.execute('SELECT deleting FROM agents WHERE id=?',(other,)).fetchone()[0],deletion_state)


    def test_invalid_roles_and_offline_requests_do_not_enqueue(self):
        for role in [-1, 9, True, '0', None]:
            with self.assertRaises(Problem):
                self.studio.enqueue(self.owner, {'kind':'crew-chat', 'crewRole':role, 'prompt':'Hello'})
        self.studio.runtime_status = lambda: {'ready':False}
        with self.assertRaises(Problem):
            self.send(0, 'Hello')
        self.assertEqual(self.studio.state(self.owner)['crewChats'], [])
