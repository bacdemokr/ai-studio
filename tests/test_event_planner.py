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
from studio_events import survey_page
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
                    self.assertLessEqual(end,600+b['duration'])
                self.assertEqual(set(r['day'] for r in c['schedule']),set(range(1,b['days']+1)))
        _,austin=planner.plan(planner.TEMPLATES[1]);self.assertTrue(austin['adjusted']);self.assertEqual(austin['session'],10)

    def test_weights_boundaries_and_invalid_briefs(self):
        b,c=planner.plan({'attendees':101,'topicWeights':[8,1,1]})
        self.assertEqual([t['attendees'] for t in c['topics']],[81,10,10])
        for data in ({'attendees':True},{'duration':3.5},{'topics':['physical','physical']},{'topics':[]},{'harnesses':['bogus']},{'topicWeights':[0,0,0]}, {'boothLimit':7},{'boothLimit':2},{'startTime':'23:30','duration':60},{'attendees':3000,'duration':30,'groupSize':1},{'city':'bad\nheader'}):
            with self.subTest(data=data),self.assertRaises(ValueError):planner.plan(data)
        b,c=planner.plan({'attendees':1});self.assertEqual(sum(r['attendees'] for r in c['schedule']),1)
        _,c=planner.plan({'attendees':15,'duration':30,'session':60});self.assertEqual(c['session'],30)

    def test_xlsx_numeric_cells_and_csv_export_all_visits(self):
        b,c=planner.plan(planner.TEMPLATES[2]);blob=planner.workbook(b,c)
        with ZipFile(io.BytesIO(blob)) as z:
            for name in z.namelist():ET.fromstring(z.read(name))
            ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            rows=ET.fromstring(z.read('xl/worksheets/sheet3.xml')).findall('s:sheetData/s:row',ns)
            self.assertEqual(len(rows)-1,len(c['schedule']))
            total=sum(int(row.find("s:c[@r='G%s']/s:v"%row.attrib['r'],ns).text) for row in rows[1:])
            self.assertEqual(total,b['attendees'])
            self.assertFalse(ET.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('.//s:f',ns))
        self.assertEqual(len(planner.rota_csv(c).splitlines())-1,len(c['schedule']))

class EventPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.adapter=Adapter();self.studio=Studio(self.temp.name,self.adapter,start_worker=False)
        self.owner=self.studio.session()[0]['id']
        self.job=self.studio.enqueue(self.owner,{'kind':'crew','preset':True,'brief':{'schema':2}})['id']
        self.studio.execute(self.studio.next_job())
        self.state=self.studio.state(self.owner)['jobs'][0]

    def test_package_files_native_web_skill_and_limited_shared_context(self):
        self.assertEqual(self.state['status'],'done')
        p=self.state['payload'];self.assertEqual(len(p['handoffs']),5)
        self.assertEqual(len(p['assignments']),4)
        self.assertTrue(all(a['input']==p['handoffs']['0']['output'] for a in p['assignments']))
        self.assertIn('web',p['roster'][3]['skills'])
        self.assertNotIn('web',p['roster'][1]['skills'])
        files=p['packageFiles'];self.assertTrue(any(f.endswith('.xlsx') for f in files))
        self.assertTrue(any(f.endswith('.eml') for f in files))
        mail=BytesParser(policy=policy.default).parsebytes((self.studio.workspace(self.owner)/next(f for f in files if f.endswith('.eml'))).read_bytes())
        self.assertEqual(mail['X-Unsent'],'1');self.assertIsNone(mail['To']);self.assertIn('DRAFT',mail.get_body().get_content())
        self.assertLessEqual(len(p['handoffs']['2']['sharedState']['capacity']['schedule']),24)
        self.assertIn('venueResearch',p['handoffs']['3']['sharedState'])

    def test_producer_refines_export_without_changing_calculated_capacity(self):
        p=self.state['payload'];before=[(r['booth'],r['start'],r['attendees']) for r in p['capacity']['schedule']]
        answer='```json\n'+json.dumps({'demos':[{'topic':'agents','title':'Build a travel companion','presenterExpertise':'Agent memory and tools'},{'topic':'unknown','title':'Ignore me'}]})+'\n```'
        self.studio.event_stage_files(self.owner,self.job,p,1,answer)
        self.studio.event_stage_files(self.owner,self.job,p,2,'Rota reviewed')
        self.assertEqual(before,[(r['booth'],r['start'],r['attendees']) for r in p['capacity']['schedule']])
        self.assertEqual(p['capacity']['topics'][0]['demo'],'Build a travel companion')
        self.assertEqual(p['capacity']['booths'][0]['presenterExpertise'],'Agent memory and tools')
        self.assertIn('1 of 3',p['capacity']['demoSource'])
        artifact=next(f for f in p['packageFiles'] if f.endswith('.xlsx'))
        with ZipFile(self.studio.workspace(self.owner)/artifact) as z:
            self.assertIn('Build a travel companion',z.read('xl/worksheets/sheet2.xml').decode())

    def test_survey_is_anonymous_persistent_owner_scoped_and_replans(self):
        token=self.state['payload']['survey']['path'].split('/')[-1]
        self.studio.survey_answer(token,{'visitor':'a'*32,'topic':'agents','experience':'new','rating':5})
        self.studio.survey_answer(token,{'visitor':'a'*32,'topic':'multiagent','experience':'new','rating':4})
        restarted=Studio(self.temp.name,self.adapter,start_worker=False)
        report=restarted.survey_report(self.owner,self.job);self.assertEqual(report['total'],1);self.assertEqual(report['rating'],4)
        self.assertEqual([t['count'] for t in report['topics']],[0,1,0])
        other=restarted.session()[0]['id']
        with self.assertRaises(Problem):restarted.survey_report(other,self.job)
        with self.assertRaises(Problem):restarted.survey_replan(other,{'id':self.job})
        with self.assertRaises(Problem):restarted.survey_answer(token,{'visitor':'b'*32,'topic':'bad','experience':'new','rating':5})
        new=restarted.survey_replan(self.owner,{'id':self.job});self.assertNotEqual(new['id'],self.job)
        state=restarted.state(self.owner)['jobs'][0];self.assertEqual(state['payload']['brief']['topicWeights'],[0,1,0]);self.assertEqual(state['payload']['brief']['attendees'],120)
        self.assertEqual(state['payload']['source'],'survey:'+self.job)
        page=survey_page(token,{**restarted.survey_definition(token),'title':'<script>bad()</script>'})
        self.assertIn('&lt;script&gt;',page);self.assertNotIn('<script>bad()',page)

    def test_deletion_revokes_survey_and_removes_responses(self):
        self.studio.onboard(self.owner,{'name':'Test','persona':'guide','skills':['writer']})
        token=self.state['payload']['survey']['path'].split('/')[-1]
        self.studio.survey_answer(token,{'visitor':'a'*32,'topic':'agents','experience':'new','rating':5})
        self.studio.delete_agent(self.owner,{'name':'Test'})
        with self.assertRaises(Problem):self.studio.survey_definition(token)
        with self.studio.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM survey_responses').fetchone()[0],0)

if __name__=='__main__':unittest.main()
