import io
import sys
import unittest
from pathlib import Path
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from event_planner import plan, workbook, TEMPLATES
from event_dates import date_label, day_label
from nvidia_event_page import render

class EventDateTests(unittest.TestCase):
    def test_templates_use_organizer_schedule(self):
        self.assertEqual([t['id'] for t in TEMPLATES],['zurich','paris','london'])
        expected=[('2026-10-01','08:30','18:00',570,'21:30'),
                  ('2026-10-13','14:00','18:00',240,''),
                  ('2026-10-14','09:00','13:00',240,'')]
        for template,(date,start,end,duration,teardown) in zip(TEMPLATES,expected):
            for theme in (False,True):
                b,c=plan({**template,**({'themeCount':len(template['topics'])} if theme else {})})
                self.assertEqual((b['startDate'],b['endDate']),(date,date))
                self.assertEqual((b['startTime'],b['endTime'],b['duration'],b['teardownTime']),
                                 (start,end,duration,teardown))
                self.assertEqual(b['days'],1)
                self.assertTrue(all(start<=r['start']<r['end']<=end for r in c['schedule']))
                self.assertEqual({r['day'] for r in c['schedule']},{1})
                self.assertEqual(b['venue'],template['venue'])
        self.assertEqual(TEMPLATES[0]['venue'],'StageOne Event & Convention Hall')
        self.assertTrue(all(t['venue']=='' for t in TEMPLATES[1:]))
        b,c=plan(TEMPLATES[0])
        with ZipFile(io.BytesIO(workbook(b,c))) as z:
            xml=''.join(z.read(n).decode() for n in z.namelist() if n.endswith('.xml'))
        for value in ['08:30','18:00','21:30','Take down by (local)']:self.assertIn(value,xml)

    def test_teardown_does_not_extend_capacity_and_rejects_invalid_deadlines(self):
        b,c=plan(TEMPLATES[0]);_,without=plan({**TEMPLATES[0],'teardownTime':''})
        self.assertEqual(c['slots'],without['slots'])
        self.assertEqual(c['schedule'],without['schedule'])
        for deadline in ('17:59','24:00','bad',None,2130):
            with self.subTest(deadline=deadline),self.assertRaises(ValueError):
                plan({**TEMPLATES[0],'teardownTime':deadline})

    def test_dates_drive_days_and_flow_to_html_excel(self):
        b,c=plan({'themeCount':3,'days':5,'startDate':'2026-09-22','endDate':'2026-09-23','venue':'Raffles City Convention Centre'})
        self.assertEqual(b['days'],2)
        self.assertEqual(date_label(b),'22–23 Sep 2026')
        self.assertEqual(day_label(b,2),'Day 2 · 23 Sep 2026')
        self.assertEqual({r['day'] for r in c['schedule']},{1,2})
        html=render(b,c,{})
        self.assertIn('22–23 Sep 2026',html)
        self.assertIn('Day 2 · 23 Sep 2026',html)
        self.assertIn('Raffles City Convention Centre',html)
        self.assertNotIn('Date TBC',html)
        with ZipFile(io.BytesIO(workbook(b,c))) as z:
            xml=''.join(z.read(n).decode() for n in z.namelist() if n.endswith('.xml'))
        for value in ['2026-09-22','2026-09-23','Raffles City Convention Centre']:self.assertIn(value,xml)

    def test_optional_single_day_and_calendar_boundaries(self):
        b,_=plan({'days':3});self.assertEqual(b['days'],3);self.assertEqual(date_label(b),'Date TBC')
        b,_=plan({'startDate':'2026-11-09','days':2});self.assertEqual(b['days'],1);self.assertEqual(b['endDate'],'2026-11-09')
        b,_=plan({'startDate':'2028-02-28','endDate':'2028-03-01'});self.assertEqual(b['days'],3)
        b,_=plan({'startDate':'2026-12-31','endDate':'2027-01-01'});self.assertEqual(b['days'],2)
        self.assertEqual(date_label(b),'31 Dec 2026 – 01 Jan 2027')

    def test_invalid_dates_are_rejected(self):
        for fields in [{'startDate':'2026-02-29'},{'startDate':'2026-9-2'},{'startDate':True},{'endDate':'2026-09-23'},
                       {'startDate':'2026-09-23','endDate':'2026-09-22'},
                       {'startDate':'2026-09-22','endDate':'2026-09-27'}]:
            with self.subTest(fields=fields),self.assertRaises(ValueError):plan(fields)
