import sys,time,unittest,threading
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from protection_activity import ProtectionActivity

class ProtectionActivityTests(unittest.TestCase):
    def test_native_denials_only_deduplicated_and_scoped(self):
        tracker=ProtectionActivity();now=time.time()
        deny={'action':'deny','reason':'policy-denied','host':'example.com','time':now,'fingerprint':'one'}
        tracker.observe('owner',1,'crew',[deny,deny,{**deny,'reason':'dns-failed','fingerprint':'dns'},
                        {**deny,'action':'allow','fingerprint':'allow'}, {**deny,'time':now-10,'fingerprint':'old'},
                        {**deny,'time':None,'fingerprint':'no-time'}],now-1)
        self.assertEqual(len(tracker.snapshot({'owner'},'owner')),1)
        self.assertEqual(tracker.snapshot({'owner'},'other'),[])
        tracker.observe('personal',None,'native-personal',[deny],now-1)
        events=tracker.snapshot({'personal'},'owner')
        self.assertEqual(len(events),2)
        self.assertTrue(all(e['source']=='OpenShell policy log' for e in events))
        self.assertEqual(tracker.snapshot({'stranger'},'stranger'),[])
        with patch('protection_activity.time.time',return_value=now+40):
            self.assertEqual(tracker.snapshot({'personal'},'owner'),[])

    def test_subsecond_sandbox_clock_skew_does_not_hide_real_denial(self):
        tracker=ProtectionActivity();now=time.time()
        tracker.observe('owner',1,'crew',[{'action':'deny','reason':'policy-denied','host':'example.com','time':now-.15,'fingerprint':'skew'}],now)
        self.assertEqual(len(tracker.snapshot(set(),'owner')),1)

    def test_allowed_requests_are_real_fresh_scoped_policy_events(self):
        tracker=ProtectionActivity();now=time.time()
        allowed={'action':'allow','reason':None,'host':'blogs.nvidia.com','time':now,'fingerprint':'allow'}
        tracker.observe('owner',1,'crew',[allowed,allowed,
                        {**allowed,'reason':'dns-failed','fingerprint':'dns'},
                        {**allowed,'time':None,'fingerprint':'no-time'},
                        {**allowed,'host':'','fingerprint':'no-host'},
                        {**allowed,'host':'127.0.0.1','fingerprint':'loopback'},
                        {**allowed,'host':'inference.local','fingerprint':'runtime'},
                        {**allowed,'time':now-10,'fingerprint':'old'}],now-1)
        events=tracker.snapshot(set(),'owner')
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['action'],'allow')
        self.assertEqual(events[0]['source'],'OpenShell policy log')
        self.assertEqual(events[0]['host'],'blogs.nvidia.com')
        self.assertEqual(tracker.snapshot({'owner'},'other'),[])

    def test_final_read_catches_fast_call_without_blocking_response(self):
        tracker=ProtectionActivity();done=threading.Event()
        def reader(agent):
            tracker.observe('owner',1,agent,[{'time':time.time(),'host':'example.com','action':'deny','reason':'policy-denied'}],0)
            done.set();return []
        with tracker.watch('owner',1,'crew',reader):pass
        self.assertTrue(done.wait(1))
        self.assertEqual(len(tracker.snapshot(set(),'owner')),1)

    def test_native_read_failure_does_not_replace_model_result(self):
        tracker=ProtectionActivity();done=threading.Event()
        def reader(agent):done.set();raise RuntimeError('offline')
        with tracker.watch('owner',None,'personal',reader):result='model result'
        self.assertEqual(result,'model result');self.assertTrue(done.wait(1))
        self.assertEqual(tracker.snapshot({'owner'},'owner'),[])

    def test_policy_reads_share_current_evidence_without_waiting_for_sampler(self):
        tracker = ProtectionActivity()
        with patch('protection_activity.threading.Thread'), tracker.watch('owner', None, 'native', lambda _: []):
            now = time.time()
            deny = {'time': now, 'host': 'example.com', 'action': 'deny',
                    'reason': 'policy-denied', 'fingerprint': 'shared'}
            tracker.observe_active('owner', None, 'native', [deny])
            tracker.observe_active('owner', None, 'native', [deny])
            tracker.observe('owner', None, 'native', [deny], now)
            self.assertEqual(len(tracker.snapshot({'owner'}, 'owner')), 1)
        tracker.forget('owner')

    def test_policy_read_reuse_preserves_identity_freshness_and_native_evidence(self):
        tracker = ProtectionActivity()
        now = time.time()
        deny = {'time': now, 'host': 'example.com', 'action': 'deny',
                'reason': 'policy-denied', 'fingerprint': 'fresh'}
        tracker.observe_active('owner', None, 'native', [deny])
        self.assertEqual(tracker.snapshot({'owner'}, 'owner'), [])
        with patch('protection_activity.threading.Thread'), tracker.watch('owner', None, 'native', lambda _: []):
            for owner, role, agent in [('other', None, 'native'), ('owner', 8, 'native'), ('owner', None, 'other')]:
                tracker.observe_active(owner, role, agent, [deny])
            tracker.observe_active('owner', None, 'native', [
                {**deny, 'time': now-10}, {**deny, 'time': now+60},
                {**deny, 'reason': 'dns-failed'}, {'host': 'example.com'}])
            self.assertEqual(tracker.snapshot({'owner'}, 'owner'), [])
            tracker.forget('owner')
            tracker.observe_active('owner', None, 'native', [deny])
            self.assertEqual(tracker.snapshot({'owner'}, 'owner'), [])

    def test_removed_owner_cancels_an_inflight_shared_read(self):
        tracker = ProtectionActivity()
        with patch('protection_activity.threading.Thread'), tracker.watch('owner', 8, 'native', lambda _: []):
            original = tracker.observe
            def race(*args):
                tracker.forget('owner')
                return original(*args)
            with patch.object(tracker, 'observe', side_effect=race):
                tracker.observe_active('owner', 8, 'native', [
                    {'time': time.time(), 'host': 'example.com', 'action': 'deny', 'reason': 'policy-denied'}])
            self.assertEqual(tracker.snapshot(set(), 'owner'), [])

    def test_shared_window_closes_after_the_existing_final_reads(self):
        tracker = ProtectionActivity()
        real_thread, threads = threading.Thread, []
        def thread(*args, **kwargs):
            result = real_thread(*args, **kwargs)
            threads.append(result)
            return result
        with patch('protection_activity.threading.Thread', side_effect=thread):
            with tracker.watch('owner', None, 'native', lambda _: []):
                pass
        threads[0].join(4)
        self.assertFalse(threads[0].is_alive())
        self.assertEqual(tracker.watchers, {})
        tracker.observe_active('owner', None, 'native', [
            {'time': time.time(), 'host': 'example.com', 'action': 'deny', 'reason': 'policy-denied'}])
        self.assertEqual(tracker.snapshot({'owner'}, 'owner'), [])
