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
    def test_empty_invalid_duplicate_and_personal_assignment_rejected(self):
        for roles in [[],[6],[-1],[True],['2'],[0,0],None]:
            with self.subTest(roles=roles),self.assertRaises(Problem):
                self.studio.enqueue(self.owner, {'kind':'crew','preset':True,'brief':{'schema':2},'enabledRoles':roles})
        with self.assertRaises(Problem):
            self.studio.enqueue(self.owner, {'kind':'crew','preset':True,'brief':{'schema':2},'enabledRoles':[0], 'members':{'1':'personal'}})
        self.assertFalse(self.adapter.stages)


if __name__ == '__main__':
    unittest.main()
