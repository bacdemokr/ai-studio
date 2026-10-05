import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from email import policy
from email.parser import BytesParser
from zipfile import ZipFile
from xml.etree import ElementTree as ET
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parent)]
import event_planner as planner
from studio import Studio,Problem
from test_studio import Adapter

class PlanningTests(unittest.TestCase):
    def test_templates_conserve_attendance_stay_within_six_and_have_no_conflicts(self):
        for template in planner.TEMPLATES:
            with self.subTest(template=template['id']):
                b,c=planner.plan(template)
                self.assertLessEqual(c['boothCount'],6)
                self.assertEqual(sum(r['attendees'] for r in c['schedule']),b['attendees'])
                self.assertEqual(sum(t['attendees'] for t in c['topics']),b['attendees'])
                self.assertEqual(c['presenterCount'],len(c['booths']))
                self.assertEqual(c['staff'],len(c['booths'])+c['floorHosts']+1)
                visits=set()
                for r in c['schedule']:
                    key=(r['day'],r['start'],r['booth'])
                    self.assertNotIn(key,visits);visits.add(key)
                    self.assertLessEqual(r['attendees'],b['groupSize'])
                    self.assertLessEqual(r['day'],b['days'])
                    start,end=[int(t[:2])*60+int(t[3:]) for t in (r['start'],r['end'])]
                    self.assertEqual(end-start,c['session'])
                    event_start=int(b['startTime'][:2])*60+int(b['startTime'][3:])
                    self.assertGreaterEqual(start,event_start)
                    self.assertLessEqual(end,event_start+b['duration'])
                self.assertEqual(set(r['day'] for r in c['schedule']),set(range(1,b['days']+1)))
        _,busy=planner.plan({'attendees':240,'duration':120,'days':1,'topics':['physical','vision','cudax','agents']});self.assertTrue(busy['adjusted']);self.assertEqual(busy['session'],10)

    def test_weights_boundaries_and_invalid_briefs(self):
        b,c=planner.plan({'attendees':101,'topics':['agents','multiagent','cudax'],'topicWeights':[8,1,1]})
        self.assertEqual([t['attendees'] for t in c['topics']],[81,10,10])
        for data in ({'attendees':True},{'duration':3.5},{'topics':['physical','physical']},{'topics':[]},{'harnesses':['bogus']},{'topicWeights':[0,0,0]}, {'boothLimit':7},{'startTime':'23:30','duration':60},{'attendees':3000,'duration':30,'groupSize':1},{'city':'bad\nheader'}):
            with self.subTest(data=data),self.assertRaises(ValueError):planner.plan(data)
        b,c=planner.plan({'attendees':1});self.assertEqual(sum(r['attendees'] for r in c['schedule']),1)
        _,c=planner.plan({'attendees':15,'duration':30,'session':60});self.assertEqual(c['session'],30)

    def test_six_experiences_rotate_across_two_booths(self):
        b,c=planner.plan({'topics':list(planner.TOPICS),'boothLimit':2})
        self.assertEqual(len(c['topics']),6)
        self.assertEqual(c['boothCount'],2)
        self.assertEqual(sum(r['attendees'] for r in c['schedule']),b['attendees'])
        self.assertEqual(len({(r['day'],r['booth'],r['start']) for r in c['schedule']}),len(c['schedule']))
        self.assertEqual(len({r['topic'] for r in c['schedule']}),6)
        for r in c['schedule']:
            self.assertLessEqual(r['end'],'13:00')
        self.assertEqual(len(planner.rota_grids(b,c)),b['days'])

    def test_xlsx_matrices_and_numeric_details_cover_all_visits(self):
        b,c=planner.plan(planner.TEMPLATES[2]);blob=planner.workbook(b,c)
        with ZipFile(io.BytesIO(blob)) as z:
            for name in z.namelist():ET.fromstring(z.read(name))
            ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            rows=ET.fromstring(z.read('xl/worksheets/sheet%d.xml' % (b['days']+3))).findall('s:sheetData/s:row',ns)
            self.assertEqual(len(rows)-1,len(c['schedule']))
            total=sum(int(row.find("s:c[@r='G%s']/s:v"%row.attrib['r'],ns).text) for row in rows[1:])
            self.assertEqual(total,b['attendees'])
            self.assertFalse(ET.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('.//s:f',ns))
            grids=planner.rota_grids(b,c)
            self.assertEqual(len(grids),b['days'])
            self.assertEqual(sum(bool(v) for _,rows in grids for row in rows[1:] for v in row[1:]),len(c['schedule']))
            for day,(_,rows) in enumerate(grids,1):
                for visit in (r for r in c['schedule'] if r['day']==day):
                    row=next(r for r in rows[1:] if r[0]==visit['booth'])
                    self.assertEqual(row[rows[0].index(visit['start'])],visit['presenter'])
            pane=ET.fromstring(z.read('xl/worksheets/sheet1.xml')).find('s:sheetViews/s:sheetView/s:pane',ns)
            self.assertEqual(pane.attrib['topLeftCell'],'B2')

class EventPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.adapter=Adapter();self.studio=Studio(self.temp.name,self.adapter,start_worker=False)
        self.owner=self.studio.session()[0]['id']
        self.job=self.studio.enqueue(self.owner,{'kind':'crew','preset':True,'brief':{'schema':2}})['id']
        self.studio.execute(self.studio.next_job())
        self.state=self.studio.state(self.owner)['jobs'][0]


if __name__ == '__main__':
    unittest.main()
