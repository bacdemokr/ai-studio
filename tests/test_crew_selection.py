import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts'), str(Path(__file__).resolve().parent)]
from studio import Studio, Problem, ROLES
from fixture_studio import BrowserAdapter

class TrackingAdapter(BrowserAdapter):
    def __init__(self):
        super().__init__()
        self.stages = []
        self.prompts = {}
    def respond(self, agent, session, prompt):
        stage = int(agent.rsplit('-r', 1)[-1])
        self.stages.append(stage)
        self.prompts[stage] = prompt
        return super().respond(agent, session, prompt)

class CrewSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.adapter = TrackingAdapter()
        self.studio = Studio(self.tmp.name, self.adapter, start_worker=False)
        self.owner = self.studio.session()[0]['id']
    def run_selection(self, roles):
        self.studio.enqueue(self.owner, {'kind':'crew','preset':True,'brief':{'schema':2},'enabledRoles':roles})
        self.studio.execute(self.studio.next_job())
        return self.studio.state(self.owner)['jobs'][0]
    def test_only_selected_roles_run_and_export(self):
        job = self.run_selection([0,2,4])
        self.assertEqual(job['status'], 'done')
        self.assertEqual(set(self.adapter.stages), {0,2,4})
        p = job['payload']
        self.assertEqual(set(p['outputs']), {'0','2','4'})
        self.assertEqual([a['name'] for a in p['assignments']], ['Alex','Riley'])
        self.assertEqual(p['handoffs']['4']['receivedFrom'], ['0','2'])
        for stage in (0,2,4):
            handoff=p['handoffs'][str(stage)]
            self.assertIn(handoff['task'], self.adapter.prompts[stage])
            self.assertEqual(handoff['senderRole'], None if stage==0 else 0)
            self.assertEqual(handoff['recipientName'],p['roster'][stage]['name'])
        self.assertTrue(any(f.endswith('.xlsx') for f in p['packageFiles']))
        self.assertNotIn('campaign', p)
        self.assertNotIn('website', p)
        self.assertIn('3 selected', job['events'][-1]['detail'])
    def test_no_captain_or_operations_needed_for_web_draft(self):
        job = self.run_selection([5])
        self.assertEqual(self.adapter.stages, [5])
        p = job['payload']
        self.assertEqual(job['status'], 'done')
        self.assertEqual(p['handoffs']['5']['receivedFrom'], [])
        self.assertIsNone(p['handoffs']['5']['senderRole'])
        self.assertEqual(p['handoffs']['5']['sharedState']['selectedCrew'][0]['name'], 'Wade')
        self.assertIn('BaC Captain', p['handoffs']['5']['sharedState']['omittedRoles'])
        self.assertIn('Omitted roles will not run', self.adapter.prompts[5])
        self.assertNotIn('assignments', p)
        self.assertTrue(p['website']['path'].endswith('.html'))
        self.assertFalse(any(f.endswith('.xlsx') for f in p['packageFiles']))
    def test_empty_invalid_duplicate_and_personal_assignment_rejected(self):
        for roles in [[],[6],[-1],[True],['2'],[0,0],None]:
            with self.subTest(roles=roles),self.assertRaises(Problem):
                self.studio.enqueue(self.owner, {'kind':'crew','preset':True,'brief':{'schema':2},'enabledRoles':roles})
        with self.assertRaises(Problem):
            self.studio.enqueue(self.owner, {'kind':'crew','preset':True,'brief':{'schema':2},'enabledRoles':[0], 'members':{'1':'personal'}})
        self.assertFalse(self.adapter.stages)
    def test_showcase_requires_casey(self):
        with self.assertRaisesRegex(Problem,'Casey is required'):
            self.studio.enqueue(self.owner, {'kind':'crew','preset':True,'workflow':'showcase','brief':{'schema':2},'enabledRoles':[1,2,3]})
        self.studio.enqueue(self.owner, {'kind':'crew','preset':True,'workflow':'showcase','brief':{'schema':2},'enabledRoles':[0,2]})
        self.assertEqual(self.studio.state(self.owner)['jobs'][0]['payload']['enabledRoles'],[0,2])

    def test_defaults_remain_all_six(self):
        self.studio.enqueue(self.owner, {'kind':'crew','preset':True,'brief':{'schema':2}})
        self.studio.execute(self.studio.next_job())
        self.assertEqual(set(self.adapter.stages), set(range(6)))
        self.assertEqual(len(self.studio.state(self.owner)['jobs'][0]['payload']['roster']),6)

if __name__ == '__main__':
    unittest.main()
