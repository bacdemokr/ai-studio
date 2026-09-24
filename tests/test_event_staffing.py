"""Demand changes, short groups and hourly presenter-rest constraints."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from event_planner import plan,TEMPLATES
from event_agent_tools import compile_schedule
from event_staffing import work_slots


def authored(b,c):
    booths=[]
    for booth in c['booths']:
        names=booth['presenter'].split(' / ');days=[]
        for d in range(1,b['days']+1):
            visits=[r for r in c['schedule'] if r['booth']==booth['booth'] and r['day']==d]
            if visits:
                start=int(b['startTime'][:2])*60+int(b['startTime'][3:])
                days.append({'day':d,'slots':[(int(r['start'][:2])*60+int(r['start'][3:])-start)//c['session'] for r in visits],
                             'rotation':[names.index(r['presenter']) for r in visits]})
        booths.append({'topicId':booth['topicId'],'presenters':names,'days':days})
    return {'sessionMinutes':c['session'],'maxConsecutiveSessions':work_slots(c['session']),
            'criteria':['Size the roster to demand','Reserve hourly rest'],'booths':booths}


class StaffingTests(unittest.TestCase):
    def test_templates_have_varied_group_sizes_and_realistic_utilization(self):
        for template,group,themes,attendees in zip(TEMPLATES,(5,2,4),(2,2,2),(280,48,96)):
            self.assertEqual(len(template['topics']),themes)
            b,c=plan({**template,'themeCount':len(template['topics'])})
            self.assertEqual((b['groupSize'],b['attendees']),(group,attendees))
            self.assertEqual(c['presenterCount'],themes)
            usage=len(c['schedule'])/(themes*(b['duration']//c['session']))
            self.assertGreaterEqual(usage,.7);self.assertLessEqual(usage,.8)
            validated=compile_schedule(b,c,authored(b,c))
            self.assertEqual(sum(r['attendees'] for r in validated['schedule']),attendees)
            for person in {r['presenter'] for r in validated['presenterDuty']}:
                run=0
                for r in [r for r in validated['presenterDuty'] if r['presenter']==person]:
                    run=run+1 if r['status']=='Presenting' else 0
                    self.assertLessEqual(run,3)

    def test_user_attendance_changes_roster_without_changing_input(self):
        # Four hours: one presenter handles 12 two-person visits per booth.
        for attendees,expected in ((24,2),(48,2),(64,4)):
            b,c=plan({'themeCount':2,'groupSize':2,'duration':240,'attendees':attendees})
            self.assertEqual(b['attendees'],attendees)
            self.assertEqual(c['presenterCount'],expected)
            result=compile_schedule(b,c,authored(b,c))
            self.assertEqual(result['presenterCount'],expected)
            self.assertEqual(sum(r['attendees'] for r in result['schedule']),attendees)

    def test_sparse_unused_slots_are_not_all_labelled_breaks(self):
        b,c=plan({'themeCount':2,'groupSize':2,'duration':240,'attendees':8})
        statuses=[r['status'] for r in c['presenterDuty']]
        self.assertIn('No visit',statuses);self.assertIn('Break',statuses)
        self.assertEqual(c['presenterCount'],2)
        spec=authored(b,c);spec['booths'][0]['presenters'].append('Presenter 99 (unassigned)')
        with self.assertRaisesRegex(ValueError,'unnecessary relief'):compile_schedule(b,c,spec)

    def test_partial_groups_and_multiple_days_conserve_attendance(self):
        for days in (1,2,5):
            b,c=plan({'themeCount':2,'groupSize':2,'days':days,'attendees':19})
            compiled=compile_schedule(b,c,authored(b,c))
            self.assertEqual(sum(r['attendees'] for r in compiled['schedule']),19)
            self.assertTrue(all(1<=r['attendees']<=2 for r in compiled['schedule']))

    def test_two_hours_without_rest_is_rejected_even_with_declared_four_sessions(self):
        b,c=plan({'themeCount':2,'groupSize':2,'duration':120,'attendees':32})
        spec=authored(b,c);spec['maxConsecutiveSessions']=4
        for booth in spec['booths']:
            booth['days']=[{'day':1,'slots':list(range(8)),'rotation':[0]}]
        with self.assertRaisesRegex(ValueError,'15 minutes of rest'):compile_schedule(b,c,spec)

    def test_five_minute_gap_does_not_count_as_full_rest(self):
        b,c=plan({'themeCount':2,'groupSize':2,'duration':90,'session':5,'attendees':40})
        spec=authored(b,c)
        for booth in spec['booths']:
            booth['days']=[{'day':1,'slots':list(range(9))+[10],'rotation':[0]}]
        with self.assertRaisesRegex(ValueError,'15 minutes of rest'):compile_schedule(b,c,spec)

    def test_session_lengths_and_demand_boundaries(self):
        for session in (5,10,15,20,30,45,60):
            for attendees in (2,17,48,64):
                with self.subTest(session=session,attendees=attendees):
                    b,c=plan({'themeCount':2,'groupSize':2,'duration':240,'session':session,'attendees':attendees})
                    compiled=compile_schedule(b,c,authored(b,c))
                    self.assertEqual(sum(r['attendees'] for r in compiled['schedule']),attendees)


if __name__=='__main__':unittest.main()
