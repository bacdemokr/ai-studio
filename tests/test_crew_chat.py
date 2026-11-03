import json
import tempfile
import unittest
from unittest.mock import patch
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

    def test_korean_captain_chat_keeps_reminder_without_dispatching_a_team(self):
        with patch.object(self.adapter, 'respond', return_value='팀의 작업을 조율할 수 있어요.'):
            self.send(0, '너는 어떤 일을 할 수 있어?')
            self.send(0, 'Can you help our team?')
        chats = self.studio.state(self.owner)['crewChats']
        self.assertEqual(len(chats), 2)
        for job in chats:
            self.assertNotIn('collaboration', job['payload'])
            self.assertTrue(job['result']['answer'].endswith(
                '참고로, 팀 프로젝트를 원한다면 메시지 앞에 `/goal`을 추가해줘.'))
        self.assertEqual(len(self.adapter.agents), 1)

    def test_explicit_english_reply_keeps_english_reminder(self):
        with patch.object(self.adapter, 'respond', return_value='I can coordinate your team.'):
            self.send(0, '영어로 답변해줘.')
        answer = self.studio.state(self.owner)['crewChats'][0]['result']['answer']
        self.assertTrue(answer.endswith('For a team project, add `/goal` at the start of your message.'))

    def test_roles_have_native_identity_and_separate_persistent_conversations(self):
        self.send(0, 'Help plan my event')
        self.send(8, 'Research a topic')
        self.send(0, 'Make the plan shorter')
        state = self.studio.state(self.owner)
        self.assertEqual(state['jobs'], [])
        self.assertEqual(len(state['crewChats']), 3)
        self.assertTrue(all(j['status'] == 'done' for j in state['crewChats']))
        for job in state['crewChats']:
            answer = job['result']['answer']
            if job['payload']['crewRole'] == 0:
                self.assertTrue(answer.endswith('For a team project, add `/goal` at the start of your message.'))
            else:
                self.assertNotIn('For a team project', answer)
        self.assertEqual(len(self.adapter.agents), 2)
        profiles = list(self.adapter.profiles.values())
        self.assertEqual([p['name'] for p in profiles], ['Casey', 'Scout'])
        self.assertIn('Casey leads the team', profiles[0]['purpose'])
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
