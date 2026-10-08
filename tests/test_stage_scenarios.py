"""Scenario isolation and restored Event Brief execution with offline tool fixtures."""
import copy
import json
import tempfile
import unittest
from unittest.mock import patch
from test_studio import Studio, Problem
from test_agent_workflow import AgentToolsAdapter
from test_researched_event import SOURCES

class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.adapter=AgentToolsAdapter();self.app=Studio(self.tmp.name,self.adapter,start_worker=False)
        self.owner=self.app.session()[0]['id']
        self.plan=self.app.crew_owner(self.owner)
        self.event=self.app.crew_owner(self.owner,'event-brief')
    def finish(self):
        while (row:=self.app.next_job()) is not None:self.app.execute(row)
    def test_independent_chats_files_models_and_reset(self):
        for owner,label in [(self.plan,'plan'),(self.event,'event')]:
            self.app.upload(owner,{'crewRole':0,'name':'notes.md','content':label})
            self.app.enqueue(owner,{'kind':'crew-chat','crewRole':0,'prompt':'Hello '+label})
        self.finish()
        self.assertEqual(len(self.app.state(self.owner)['crewChats']),1)
        self.assertEqual(len(self.app.state(self.owner,'event-brief')['crewChats']),1)
        self.assertNotEqual(self.app.crew_native_id(self.plan,0),self.app.crew_native_id(self.event,0))
        self.app.reset_crew_chats(self.event,reset_event=True)
        self.assertEqual(len(self.app.state(self.owner)['crewChats']),1)
        self.assertEqual(self.app.state(self.owner,'event-brief')['crewChats'],[])
        self.assertEqual((self.app.workspace(self.plan,0)/'inbox/notes.md').read_text(),'plan')
        self.assertFalse((self.app.workspace(self.event,0)/'inbox/notes.md').exists())
        self.app.reset_crew_chats(self.owner,reset_event=True)
        self.assertEqual(self.app.state(self.owner)['crewChats'],[])
        self.assertFalse((self.app.workspace(self.plan,0)/'inbox/notes.md').exists())
    def test_context_migration_preserves_native_identity(self):
        with self.app.db() as db:
            db.execute('DROP TABLE crew_contexts')
            db.execute('CREATE TABLE crew_contexts(owner TEXT PRIMARY KEY, participant TEXT NOT NULL UNIQUE)')
            db.execute('INSERT INTO crew_contexts VALUES (?,?)',(self.plan,self.owner))
        native=self.app.crew_native_id(self.plan,0)
        upgraded=Studio(self.tmp.name,self.adapter,start_worker=False)
        self.assertEqual(upgraded.crew_owner(self.owner),self.plan)
        self.assertEqual(upgraded.crew_native_id(self.plan,0),native)
        event=upgraded.crew_owner(self.owner,'event-brief')
        self.assertNotEqual(event,self.plan)
        self.assertNotEqual(upgraded.crew_native_id(event,0),native)
    def test_scenario_routing_and_busy_event_fence(self):
        with self.assertRaises(Problem):self.app.enqueue(self.plan,{'kind':'crew','preset':True})
        with self.assertRaises(Problem):self.app.enqueue(self.event,{'kind':'crew-chat','crewRole':0,'prompt':'/plan something'})
        self.app.prepare_demo(self.event,{'enabledRoles':[0]})
        with self.assertRaises(Problem):self.app.enqueue(self.event,{'kind':'crew-chat','crewRole':0,'prompt':'hi'})
        self.app.enqueue(self.plan,{'kind':'crew-chat','crewRole':0,'prompt':'hi'})
        with self.assertRaises(Problem):self.app.crew_owner(self.owner,'unknown')
    def test_full_event_tool_workflow_preserves_plan_workspace(self):
        self.app.upload(self.plan,{'crewRole':0,'name':'keep.md','content':'Preserve me'})
        prep=self.app.prepare_demo(self.event,{'enabledRoles':[0,1,2,3]})
        self.finish()
        self.assertEqual(self.app.demo_preparation(self.event)['status'],'done')
        job=self.app.enqueue(self.event,{'kind':'crew','preset':True,'workflow':'showcase','executionMode':'agent-led-v1','brief':{'schema':2,'themeCount':2},'enabledRoles':[0,1,2,3],'preparationId':prep['id']})
        with patch('nvidia_research.discover',side_effect=AssertionError('No host research')),patch('nvidia_research.search_one',return_value=copy.deepcopy(SOURCES['sources'])),patch('event_agent_tools.read_article',return_value='Fixture article read by the agent tool.'):
            self.finish()
        result=self.app.evidence(self.event,job['id'])['mission']
        self.assertEqual(result['status'],'done',result['result'])
        self.assertTrue(result['payload']['website']['path'])
        self.assertEqual(set(result['payload']['outputs']),{'0','1','2','3'})
        self.assertEqual(self.app.state(self.owner)['jobs'],[])
        self.assertEqual(len(self.app.state(self.owner,'event-brief')['jobs']),1)
        self.assertEqual((self.app.workspace(self.plan,0)/'inbox/keep.md').read_text(),'Preserve me')
        fresh=Studio(self.tmp.name,self.adapter,start_worker=False)
        self.assertEqual(len(fresh.state(self.owner,'event-brief')['jobs']),1)
        self.assertEqual(fresh.state(self.owner)['jobs'],[])
        fresh.reset_crew_chats(self.event,reset_event=True)
        fresh.reset_crew_chats(self.owner,reset_event=True)
        self.assertEqual(fresh.state(self.owner,'event-brief')['jobs'],[])

if __name__=='__main__':unittest.main()
