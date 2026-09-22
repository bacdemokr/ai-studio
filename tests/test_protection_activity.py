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
