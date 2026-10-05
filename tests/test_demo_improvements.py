"""Readiness, scoped recovery, and reset isolation; no live model calls."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'scripts'), str(Path(__file__).resolve().parent)]
from studio import Studio, Problem
from test_roundtable import ReviewAdapter
from test_researched_event import SOURCES, demos
from event_planner import plan
from event_theme_content import apply_themes, theme_issues


class DemoImprovements(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.adapter=ReviewAdapter();self.studio=Studio(self.folder.name,self.adapter,start_worker=False)
        self.owner=self.studio.session()[0]['id']
        self.studio.onboard(self.owner,dict(name='Weather',persona='analyst',skills=['weather'],tonePrompt='Warm, concise, specific.',protection='standard'))
        self.guest=self.studio.add_agent(self.owner,dict(name='Orbit',persona='analyst',skills=['weather'],tonePrompt='Dry and skeptical.'))['agentId']

    def run_next(self):
        self.studio.execute(self.studio.next_job())

    def event(self):
        self.studio.enqueue(self.owner,{'kind':'crew','preset':True,'workflow':'showcase','brief':{'schema':2}})
        self.run_next();return self.studio.state(self.owner)['jobs'][0]


    def test_theme_checks_reject_vague_duplicate_and_unsupported_brand(self):
        b,c=plan({'themeCount':3});items=demos(b)
        items[0]['title']='Brief-to-Plan Agent';items[1]['title']='Nemotron Agent — Review the launch notes';items[2]['title']=items[1]['title']
        self.assertEqual(set(theme_issues(b,items,SOURCES)),set(b['topics']))
        apply_themes(b,c,items,SOURCES)
        self.assertTrue(all(t['researchStatus']=='unverified' for t in c['topics']))

if __name__=='__main__':unittest.main()
