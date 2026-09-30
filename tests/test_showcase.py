import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parent)]
from studio import Studio, Problem
from fixture_studio import BrowserAdapter
from event_showcase import render_showcase
from event_planner import workbook
import zipfile
import io

class Adapter(BrowserAdapter):
    def __init__(self):
        super().__init__();self.calls=[];self.prompts={};self.current=0;self.maximum=0;self.lock=threading.Lock()
    def respond(self,agent,session,prompt):
        stage=int(agent.rsplit('-r',1)[1])
        with self.lock:
            self.calls.append(stage);self.prompts[stage]=prompt;self.current+=1;self.maximum=max(self.maximum,self.current)
        time.sleep(.04 if stage==2 else .1)
        with self.lock:self.current-=1
        if stage==1:return json.dumps({'demos':[{'topic':'agents','title':'Meet your agent','action':'Ask for live weather','outcome':'A grounded short answer','presenterExpertise':'OpenClaw'}]})
        if stage==3:return json.dumps({'subject':'Join us <script>','body':'Hello [Attendee],\nJoin us on [Date].\n[Registration link]'})
        return 'Brief and assignments.' if stage==0 else 'Booth slots checked; presenter names are unassigned.'

class ShowcaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.adapter=Adapter();self.studio=Studio(self.tmp.name,self.adapter,start_worker=False)
        self.owner=self.studio.session()[0]['id']
    def run_job(self):
        self.studio.enqueue(self.owner,{'kind':'crew','preset':True,'workflow':'showcase','brief':{'schema':2}})
        self.studio.execute(self.studio.next_job())
        return self.studio.state(self.owner)['jobs'][0]


    def test_reject_extra_roles(self):
        with self.assertRaises(Problem):self.studio.enqueue(self.owner,{'kind':'crew','preset':True,'workflow':'showcase','brief':{'schema':2},'enabledRoles':[0,5]})
    def test_assembly_works_before_specialists(self):
        from event_planner import plan
        b,c=plan({'schema':2,'days':2})
        page=render_showcase(b,c,{'0':'brief'})
        self.assertIn('Day 2',page);self.assertIn('Calculated preview',page);self.assertIn('will appear here',page)

if __name__=='__main__':unittest.main()
