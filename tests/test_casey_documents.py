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
