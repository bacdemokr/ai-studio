import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from live_plan_activity import snapshot
from test_collaboration_plan import CollaborationTests


class SnapshotTests(unittest.TestCase):
    def test_sanitizes_observed_metadata(self):
        reader=Mock(return_value={'available':True,'calls':[
            {'tool':'web_fetch','target':'https://user:secret@example.com/page?token=secret','status':'completed','text':'PRIVATE'},
            {'tool':'write','target':'/Users/person/private/artifacts/result.md','status':'completed'},
            {'tool':'exec','target':'secret command','status':'running'},
            {'tool':'web_search','target':'private query','status':'failed'}]})
        observation={'agent':'a','session':'s','started':time.time()-12,'role':8}
        value=snapshot(SimpleNamespace(observed_activity=reader),observation)
        reader.assert_called_once_with('a','s',observation['started'])
        self.assertEqual([c['target'] for c in value['calls']],['example.com','result.md','',''])
        self.assertNotIn('secret',str(value));self.assertNotIn('PRIVATE',str(value))
        self.assertGreaterEqual(value['elapsed'],12)

    def test_unavailable_and_bounded(self):
        observation={'agent':'a','session':'s','started':time.time(),'role':8}
        self.assertIsNone(snapshot(object(),observation))
        reader=Mock(side_effect=RuntimeError('private'))
        self.assertFalse(snapshot(SimpleNamespace(observed_activity=reader),observation)['available'])
        reader.side_effect=None;reader.return_value={'available':True,'calls':[{'tool':'read','status':'completed'}]*30}
        self.assertEqual(len(snapshot(SimpleNamespace(observed_activity=reader),observation)['calls']),12)


class StateActivityTests(CollaborationTests):
    def test_personal_job_exposes_live_web_activity_only_while_running(self):
        observed=[]
        self.adapter.observed_activity=Mock(return_value={'available':True,'calls':[
            {'tool':'web_fetch','target':'https://example.com/private?token=secret','status':'running'}]})
        original=self.adapter.respond
        def respond(agent,session,prompt,**kwargs):
            if session == 'bac-' + self.owner:
                job=self.app.state(self.owner)['jobs'][0]
                self.assertEqual(job['liveActivity']['role'],None)
                self.assertEqual(job['liveActivity']['calls'][0]['target'],'example.com')
                self.assertNotIn('secret',str(job['liveActivity']))
                observed.append(job['liveActivity'])
            return original(agent,session,prompt,**kwargs)
        self.adapter.respond=respond
        self.app.enqueue(self.owner,{'kind':'chat','prompt':'Read example.com','source':'test'})
        self.app.execute(self.app.next_job())
        self.assertTrue(observed)
        self.assertNotIn('liveActivity',self.app.state(self.owner)['jobs'][0])

    def test_live_activity_is_scoped_and_stops_after_completion(self):
        observed=[]
        self.adapter.observed_activity=Mock(return_value={'available':True,'calls':[{'tool':'web_fetch','target':'https://example.com/','status':'completed'}]})
        original=self.adapter.respond
        def respond(agent,session,prompt,**kwargs):
            if session.endswith('-working'):
                state=self.app.state(self.owner)
                p=state['crewChats'][0]['payload']['collaboration']
                self.assertNotIn('observation',p)
                self.assertEqual(p['liveActivity']['role'],int(agent.rsplit('-r',1)[1]))
                self.assertEqual(p['liveActivity']['calls'][0]['target'],'example.com')
                observed.append(p['liveActivity'])
                outsider=self.app.session()[0]['id']
                before=self.adapter.observed_activity.call_count
                self.assertEqual(self.app.state(outsider)['crewChats'],[])
                self.assertEqual(self.adapter.observed_activity.call_count,before)
            return original(agent,session,prompt,**kwargs)
        self.adapter.respond=respond
        result=self.start();self.app.execute(self.app.next_job())
        self.assertTrue(observed)
        before=self.adapter.observed_activity.call_count
        self.assertNotIn('liveActivity',self.job(result)['payload']['collaboration'])
        self.assertEqual(self.adapter.observed_activity.call_count,before)
