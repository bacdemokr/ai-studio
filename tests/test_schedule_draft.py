"""Deterministic schedules across editable inputs; no model or network calls."""
import itertools
import math
import random
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from event_planner import plan, TEMPLATES
from event_agent_tools import draft_schedule, compile_schedule


class DraftTests(unittest.TestCase):
    def check_schedule(self, data):
        themes=data['themeCount'];attendees=data['attendees'];size=data['groupSize']
        max_groups=math.ceil(math.ceil(attendees/themes)/size)
        impossible=max_groups>(data['duration']//5)*data['days']
        if impossible:
            with self.assertRaisesRegex(ValueError,'Add event time or days'):
                plan(data)
            return
        b,c=plan(data)
        spec=draft_schedule(b,c)
        result=compile_schedule(b,c,spec)
        self.assertEqual(c['schedule'],result['schedule'])
        self.assertEqual(sum(r['attendees'] for r in result['schedule']),attendees)
        self.assertEqual(len(spec['booths']),themes)
        session=result['session'];daily=b['duration']//session
        occupied=set();assignments={}
        for row in result['schedule']:
            self.assertTrue(1<=row['attendees']<=size)
            key=row['day'],row['start'],row['booth']
            self.assertNotIn(key,occupied);occupied.add(key)
            assignments.setdefault(row['presenter'],set()).add(row['topicId'])
        self.assertTrue(all(len(topics)==1 for topics in assignments.values()))
        for topic,booth in zip(result['topics'],spec['booths']):
            slots=sorted((d['day']-1)*daily+s for d in booth['days'] for s in d['slots'])
            self.assertEqual(len(slots),topic['groups'])
            self.assertTrue(all(0<=s<daily*b['days'] for s in slots))
            if len(slots)>1:
                gaps=[slots[0]]+[y-x-1 for x,y in zip(slots,slots[1:])]+[daily*b['days']-slots[-1]-1]
                self.assertLessEqual(max(gaps),math.ceil(daily*b['days']/len(slots))+math.ceil(15/session)-1)
        # Independently accumulate work between complete 15-minute rests.
        for person in {r['presenter'] for r in result['presenterDuty']}:
            for day in range(1,b['days']+1):
                work=0;rest=15
                for row in result['presenterDuty']:
                    if row['presenter']!=person or row['day']!=day:continue
                    if row['status']=='Presenting':
                        if rest>=15:work=0
                        work+=session;rest=0
                        self.assertLessEqual(work,max(45,session))
                    else:rest+=session

    def test_previously_failing_inputs(self):
        for data in (
            dict(themeCount=2,attendees=65,groupSize=2,duration=240,session=15,days=1),
            dict(themeCount=2,attendees=129,groupSize=4,duration=240,session=15,days=1),
            dict(themeCount=3,attendees=19,groupSize=4,duration=30,session=15,days=1),
            dict(themeCount=2,attendees=192,groupSize=4,duration=120,session=5,days=1),
        ):
            with self.subTest(data=data):self.check_schedule(data)

    def test_default_templates_are_repeatable(self):
        for t in TEMPLATES:
            b,c=plan({**t,'themeCount':len(t['topics'])})
            self.assertEqual(draft_schedule(b,c),draft_schedule(b,c))
            self.assertEqual(c['session'],15)
            self.assertEqual(c['presenterCount'],2)

    def test_editable_input_grid(self):
        for session,duration,days,themes,attendees in itertools.product(
            (5,10,15,20,30,45,60),(30,60,90,120,180,240,570),(1,2,3),(2,3,4,6),
            (1,8,19,32,48,64,96,120,192,280,420)):
            data=dict(session=session,duration=duration,days=days,themeCount=themes,attendees=attendees,groupSize=4)
            with self.subTest(data=data):self.check_schedule(data)

    def test_seeded_inputs_cover_odd_minutes_large_groups_and_five_days(self):
        rng=random.Random(20260924)
        for _ in range(750):
            data=dict(session=rng.randint(5,60),duration=rng.randint(30,720),days=rng.randint(1,5),
                      themeCount=rng.randint(2,6),attendees=rng.randint(1,3000),groupSize=rng.randint(1,30))
            with self.subTest(data=data):self.check_schedule(data)


if __name__=='__main__':unittest.main()
