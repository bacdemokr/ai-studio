"""Bound research failures without changing native policy or inventing outputs."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_agent_workflow import AgentToolsAdapter
from test_researched_event import SOURCES
from event_agent_tools import run
from studio import Studio
from telemetry import Reply
import agent_workflow


class ResearchFailureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.work=Path(self.temp.name)
        (self.work/'inbox').mkdir();(self.work/'artifacts').mkdir()
        self.contract={'job':'one','files':agent_workflow.paths('one')}
        self.save_contract()

    def save_contract(self):
        (self.work/'inbox/agent-task.json').write_text(json.dumps(self.contract))

    def test_failed_batch_allows_one_retry_then_no_more_network_or_validation(self):
        with patch('nvidia_research.search_one',side_effect=RuntimeError('curl 22, HTTP 403')) as fetch:
            first=run(self.work,'search',['AI','agents'])
            self.assertTrue(first['retryAllowed'])
            self.assertIn('HTTP 403',first['failedQueries'][0]['error'])
            second=run(self.work,'search',['AI','agents'])
            self.assertFalse(second['retryAllowed'])
            count=fetch.call_count
            for action,values in [('search',['another']),('read',['S1']),('validate-themes',[])]:
                self.assertEqual(run(self.work,action,values)['status'],'stopped')
            self.assertEqual(fetch.call_count,count)
        self.assertTrue(agent_workflow.research_stopped(self.work,'one'))
        self.contract={'job':'two','files':agent_workflow.paths('two')};self.save_contract()
        with patch('nvidia_research.search_one',return_value=[]):
            self.assertEqual(run(self.work,'search',['AI'])['networkFailures'],0)

    def test_successful_retry_can_read_and_empty_results_are_not_access_failure(self):
        with patch('nvidia_research.search_one',side_effect=[RuntimeError('timeout'),copy.deepcopy(SOURCES['sources'])]):
            run(self.work,'search',['AI'])
            result=run(self.work,'search',['AI'])
        self.assertNotIn('retryAllowed',result)
        with patch('event_agent_tools.read_article',return_value='actual article'):
            self.assertNotIn('retryAllowed',run(self.work,'read',['S1']))
        self.assertFalse(agent_workflow.research_stopped(self.work,'one'))

    def test_empty_search_is_not_a_connection_failure(self):
        with patch('nvidia_research.search_one',return_value=[]):
            for _ in range(3):
                result=run(self.work,'search',['AI'])
                self.assertEqual(result['networkFailures'],0)
                self.assertNotIn('retryAllowed',result)

    def test_read_failure_retains_good_articles_and_stops_after_retry(self):
        with patch('nvidia_research.search_one',return_value=copy.deepcopy(SOURCES['sources'])):
            run(self.work,'search',['AI'])
        with patch('event_agent_tools.read_article',return_value='saved article'):
            run(self.work,'read',['S1'])
        with patch('event_agent_tools.read_article',side_effect=RuntimeError('HTTP 403')) as fetch:
            self.assertTrue(run(self.work,'read',['S1','S2'])['retryAllowed'])
            self.assertFalse(run(self.work,'read',['S1','S2'])['retryAllowed'])
            self.assertEqual(fetch.call_count,2)
        research=json.loads((self.work/self.contract['files']['research']).read_text())
        self.assertEqual(research['sources'][0]['article'],'saved article')
