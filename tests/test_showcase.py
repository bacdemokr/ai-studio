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
    def test_four_calls_parallel_handoffs_and_artifacts(self):
        job=self.run_job();p=job['payload']
        self.assertEqual(job['status'],'done')
        self.assertEqual(sorted(self.adapter.calls),[0,1,2,3]);self.assertEqual(self.adapter.maximum,2)
        for i in (1,2):self.assertEqual(p['handoffs'][str(i)]['receivedFrom'],['0'])
        self.assertEqual(set(p['handoffs']['3']['receivedFrom']),{'0','1','2'})
        self.assertIn('Meet your agent',self.adapter.prompts[3])
        self.assertIn('Booth slots checked',self.adapter.prompts[3])
        self.assertGreaterEqual(p['handoffs']['3']['started'],max(p['handoffs']['1']['completed'],p['handoffs']['2']['completed']))
        self.assertNotIn('survey',p);self.assertNotIn('telegramDelivery',p)
        files=p['packageFiles'];self.assertTrue(any(f.endswith('.eml') for f in files));self.assertTrue(any(f.endswith('.xlsx') for f in files))
        page=(self.studio.workspace(self.owner)/p['website']['path']).read_text()
        self.assertIn('Join us &lt;script&gt;',page);self.assertNotIn('<script>',page)
        self.assertIn('Same assignments as the Excel rota',page)
        self.assertIn('Your experience floor',page)
        self.assertIn('not a venue floor plan',page)
        self.assertIn('YOUR CREW’S PROGRESS',page)
        self.assertEqual(page.count('class="floor-booth"'),p['capacity']['boothCount'])
        self.assertEqual(p['website']['author'],'Studio assembly')
        for row in p['capacity']['schedule']:
            self.assertIn(row['start'],page);self.assertIn(row['presenter'],page)
        from event_planner import rota_grids
        self.assertTrue(rota_grids(p['brief'],p['capacity']))
        with zipfile.ZipFile(io.BytesIO(workbook(p['brief'],p['capacity']))) as z:
            self.assertTrue(any('worksheets/sheet' in n for n in z.namelist()))
    def test_failure_preserves_finished_work_without_launching_next(self):
        original=self.adapter.respond
        def fail(agent,session,prompt):
            if agent.endswith('-r1'): raise RuntimeError('Demo failure')
            return original(agent,session,prompt)
        self.adapter.respond=fail
        self.studio.enqueue(self.owner,{'kind':'crew','preset':True,'workflow':'showcase','brief':{'schema':2}})
        with self.assertRaisesRegex(RuntimeError,'Demo failure'):
            self.studio.execute(self.studio.next_job())
        p=self.studio.state(self.owner)['jobs'][0]['payload']
        self.assertIn('2',p['outputs']);self.assertNotIn('3',p['handoffs'])
        self.assertTrue(any(f.endswith('.xlsx') for f in p['packageFiles']))
        self.assertEqual(p['activeStages'],[])

    def test_all_six_experiences_are_accepted(self):
        from event_planner import TOPICS
        job=self.studio.enqueue(self.owner,{'kind':'crew','preset':True,'workflow':'showcase','brief':{'schema':2,'topics':list(TOPICS),'boothLimit':2}})
        self.studio.execute(self.studio.next_job())
        result=self.studio.state(self.owner)['jobs'][0]
        self.assertEqual(result['status'],'done')
        self.assertEqual(len(result['payload']['capacity']['topics']),6)

    def test_reject_extra_roles(self):
        with self.assertRaises(Problem):self.studio.enqueue(self.owner,{'kind':'crew','preset':True,'workflow':'showcase','brief':{'schema':2},'enabledRoles':[0,5]})
    def test_assembly_works_before_specialists(self):
        from event_planner import plan
        b,c=plan({'schema':2,'days':2})
        page=render_showcase(b,c,{'0':'brief'})
        self.assertIn('Day 2',page);self.assertIn('Calculated preview',page);self.assertIn('will appear here',page)

if __name__=='__main__':unittest.main()
