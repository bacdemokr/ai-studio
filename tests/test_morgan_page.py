"""File handoff / validation / bounded repair tests, using explicit fake model tools."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_researched_event import EventAdapter, SOURCES, author_page
from studio import Studio
import morgan_page

class FileAdapter(EventAdapter):
    def __init__(self, faults=()):
        super().__init__();self.faults=list(faults);self.calls=[]
    def respond(self, agent, session, prompt):
        role=int(agent.rsplit('-r',1)[1]);self.calls.append((role,session,prompt))
        if role!=3:return super().respond(agent,session,prompt)
        work=Path(self.agents[agent]);contract=json.loads((work/'inbox/morgan-page.json').read_text());target=work/contract['files']['html']
        # Simulate a file-tool editing pass, then selected failures.
        target.write_text((work/'inbox/morgan-page-starter.html').read_text())
        author_page(work)
        fault=self.faults.pop(0) if self.faults else ''
        if fault=='missing':target.unlink()
        elif fault=='unchanged':target.write_text((work/'inbox/morgan-page-starter.html').read_text())
        elif fault=='schedule':target.write_text(target.read_text().replace('Booth coverage','Incorrect schedule'))
        elif fault=='date':target.write_text(target.read_text().replace('1 October 2026','2 October 2026').replace('2026-10-01','2026-10-02').replace('StageOne Event','Wrong Event'))
        elif fault=='source':target.write_text(target.read_text().replace('https://blogs.nvidia.com/blog/fixture-1/','https://example.com/'))
        elif fault=='script':target.write_text(target.read_text().replace('</head>','<script>alert(1)</script></head>'))
        elif fault=='anchor':target.write_text(target.read_text().replace('href="#program"','href="#missing"'))
        elif fault=='post':(work/contract['files']['post']).write_text('This entirely different social post must never pass consistency validation.')
        elif fault=='transport':raise RuntimeError('Test model disconnected')
        elif fault=='json':target.write_text('{"headline":"Not an HTML file"}')
        elif fault=='symlink':target.unlink();target.symlink_to(work/'inbox/morgan-page-starter.html')
        return 'I saved the event webpage and LinkedIn post.'

class MorganPageTests(unittest.TestCase):
    def run_event(self,faults=()):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.adapter=FileAdapter(faults);self.studio=Studio(temp.name,self.adapter,start_worker=False);self.owner=self.studio.session()[0]['id']
        self.studio.enqueue(self.owner,{'kind':'crew','preset':True,'workflow':'showcase','brief':{'schema':2,'themeCount':3,'city':'Zurich','startDate':'2026-10-01','endDate':'2026-10-01','venue':'StageOne Event & Convention Hall'}})
        with patch('nvidia_research.discover',return_value=SOURCES):
            self.studio.execute(self.studio.next_job())
        return self.studio.state(self.owner)['jobs'][0]

    def test_actual_file_is_published_unchanged_and_roundtable_cannot_overwrite(self):
        job=self.run_event();p=job['payload'];self.assertEqual(job['status'],'done');self.assertTrue(p['website']['authored']);self.assertEqual(p['website']['author'],'Morgan')
        source=self.studio.workspace(self.owner,3)/morgan_page.paths(job['id'])['html'];published=self.studio.workspace(self.owner)/p['website']['path']
        before=published.read_bytes();self.assertEqual(before,source.read_bytes());self.assertEqual(hashlib.sha256(before).hexdigest(),p['website']['sha256'])
        self.assertEqual(p['pageDraft']['attempts'],1);self.assertEqual(len(self.adapter.calls),4)
        self.assertEqual(set(p['handoffs']['3']['receivedFrom']),{'0','1','2'})
        p['roundtable']={'status':'done','members':[],'replies':{}}
        self.studio.event_stage_files(self.owner,job['id'],p,-1,'')
        self.assertEqual(before,published.read_bytes())
        self.assertIn(b'StageOne Event &amp; Convention Hall',before)
        self.assertEqual(p['brief']['days'],1)

    def test_one_repair_for_invalid_file_outputs(self):
        for fault in ('missing','unchanged','schedule','date','source','script','anchor','post','json'):
            with self.subTest(fault=fault):
                job=self.run_event([fault]);self.assertEqual(job['status'],'done');self.assertEqual(job['payload']['pageDraft']['attempts'],2)
                calls=[c for c in self.adapter.calls if c[0]==3];self.assertEqual(len(calls),2);self.assertEqual(calls[0][1],calls[1][1]);self.assertIn('Repair your existing',calls[1][2])

    def test_second_failure_does_not_claim_a_completed_page(self):
        with self.assertRaisesRegex(RuntimeError,'one repair'):
            self.run_event(['unchanged','unchanged'])
        p=self.studio.state(self.owner)['jobs'][0]['payload']
        self.assertEqual(p['pageDraft']['status'],'failed');self.assertEqual(p['pageDraft']['attempts'],2)
        self.assertFalse(p['website'].get('authored'));self.assertNotIn('3',p['outputs']);self.assertIn('1',p['outputs']);self.assertIn('2',p['outputs'])

    def test_transport_failure_is_not_shown_as_pending_webpage(self):
        with self.assertRaisesRegex(RuntimeError,'Test model disconnected'):
            self.run_event(['transport'])
        p=self.studio.state(self.owner)['jobs'][0]['payload']
        self.assertEqual(p['pageDraft']['status'],'failed');self.assertNotIn('3',p['outputs'])

    def test_symlink_is_a_repairable_validation_error(self):
        with self.assertRaisesRegex(RuntimeError,'one repair'):
            self.run_event(['symlink','symlink'])
        p=self.studio.state(self.owner)['jobs'][0]['payload'];self.assertEqual(p['pageDraft']['attempts'],2)

if __name__=='__main__':unittest.main()
