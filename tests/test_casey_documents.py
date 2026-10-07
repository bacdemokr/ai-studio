import tempfile
import unittest
from pathlib import Path
from studio import Studio, Problem
from test_studio import Adapter
from plan_inputs import requested_inputs

class CaseyDocumentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.app=Studio(Path(self.temp.name)/'studio',Adapter(),start_worker=False)
        self.owner=self.app.session()[0]['id'];self.team=self.app.crew_owner(self.owner)
    def test_attachment_scoped_to_casey_and_selected_task(self):
        self.app.upload(self.owner,{'crewRole':0,'name':'budget (1).csv','content':'item,cost\nA,120\nB,80'})
        self.app.upload(self.owner,{'crewRole':0,'name':'private.txt','content':'DO NOT SHARE'})
        items=requested_inputs(self.app,{'owner':self.team,'role':0},'Summarize budget (1).csv')
        self.assertEqual([i['name'] for i in items],['budget (1).csv'])
        self.assertIn(b'120',items[0]['data'])
        self.assertFalse((self.app.workspace(self.team,6)/'inbox/budget (1).csv').exists())
        other=self.app.session()[0]['id'];team2=self.app.crew_owner(other)
        self.assertEqual(requested_inputs(self.app,{'owner':team2,'role':0},'budget (1).csv'),[])
        self.assertEqual(len(self.app.state(self.owner)['crewDocuments']),2)
    def test_invalid_role_and_path_are_rejected(self):
        for role in (1,False,'0'):
            with self.assertRaises(Problem):self.app.upload(self.owner,{'crewRole':role,'name':'a.txt','content':'hello'})
        with self.assertRaises(Problem):self.app.upload(self.owner,{'crewRole':0,'name':'../a.txt','content':'hello'})

    def test_internal_event_handoffs_never_become_user_attachments(self):
        for scenario in ('plan', 'event-brief'):
            team = self.app.crew_owner(self.owner, scenario)
            work = self.app.workspace(team, 0)
            for name in ('handoffs.md', 'shared-brief.json'):
                (work / 'inbox' / name).write_text('Internal team context')
                with self.assertRaisesRegex(Problem, 'reserved'):
                    self.app.upload(team, {'crewRole':0, 'name':name, 'content':'Replacement'})
            self.app.upload(team, {'crewRole':0, 'name':'notes.md', 'content':'User notes'})
            self.assertEqual([f['path'] for f in self.app.state(self.owner, scenario)['crewDocuments']], ['inbox/notes.md'])
            self.assertEqual(requested_inputs(self.app, {'owner':team, 'role':0}, 'Read handoffs.md'), [])
            self.assertEqual((work / 'inbox/handoffs.md').read_text(), 'Internal team context')
        self.app.onboard(self.owner, {'name':'Guest', 'skills':['documents']})
        self.app.upload(self.owner, {'name':'handoffs.md', 'content':'Personal uploaded notes'})
        self.assertEqual(requested_inputs(self.app, {'owner':self.owner}, 'Read handoffs.md')[0]['data'], b'Personal uploaded notes')

    def test_user_plan_and_chat_filenames_remain_available(self):
        for name in ('plan-notes.md','chat-notes.txt'):
            self.app.upload(self.owner,{'crewRole':0,'name':name,'content':'User supplied evidence'})
            items=requested_inputs(self.app,{'owner':self.team,'role':0},'Summarize '+name)
            self.assertEqual([i['name'] for i in items],[name])
        generated='plan-'+'a'*24+'-r8-0.md'
        self.app.upload(self.owner,{'crewRole':0,'name':generated,'content':'Old handoff'})
        self.assertEqual(requested_inputs(self.app,{'owner':self.team,'role':0},generated),[])
