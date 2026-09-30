"""File handoff / validation / bounded repair tests, using explicit fake model tools."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_researched_event import EventAdapter, SOURCES, author_page
from studio import Studio, CREW_CATALOG
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
        # Exercise historical host-research assembly only; current protected runs are tested separately.
        with patch.dict(CREW_CATALOG[1], {'protection':'standard'}), patch('nvidia_research.discover',return_value=SOURCES):
            self.studio.execute(self.studio.next_job())
        return self.studio.state(self.owner)['jobs'][0]


if __name__=='__main__':unittest.main()
