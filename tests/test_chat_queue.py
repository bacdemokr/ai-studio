import contextlib
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from studio import Studio

class ChatQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'queue.sqlite'
        self.app=Studio.__new__(Studio)
        self.app.execution_lock=threading.RLock();self.app.executing_jobs={};self.app.agent_locks={}
        self.app.executing_owners=set();self.app.executing_bac_owners=set();self.app.signal=threading.Event()
        @contextlib.contextmanager
        def db():
            c=sqlite3.connect(self.path);c.row_factory=sqlite3.Row
            try:
                with c:yield c
            finally:c.close()
        self.app.db=db
        with db() as c:c.executescript("CREATE TABLE agents(id, deleting); INSERT INTO agents VALUES('team',0),('other',0); CREATE TABLE agent_policies(owner,updating); CREATE TABLE jobs(id,owner,kind,status,payload,due,created,updated);")
    def add(self,ident,role,status='queued',plan=False,owner='team'):
        payload={'crewRole':role}
        if plan:payload['collaboration']={'activeRole':role}
        with self.app.db() as c:c.execute('INSERT INTO jobs VALUES(?,?,?,?,?,0,?,0)',(ident,owner,'crew-chat',status,json.dumps(payload),len(ident)))
    def test_chat_bypasses_plan_but_not_same_agent(self):
        self.add('plan',8,'running',True);self.add('a',8);self.add('bb',5)
        self.assertEqual(self.app.next_job('chat')['id'],'bb')
        self.assertIsNone(self.app.next_job('chat'))
    def test_independent_account_and_lane(self):
        self.add('plan',8,'running',True);self.add('b',8,owner='other');self.add('p2',0,plan=True,owner='other')
        self.assertEqual(self.app.next_job('chat')['id'],'b')
        self.assertIsNone(self.app.next_job('background'))
    def test_postprocessing_keeps_same_agent_fenced(self):
        self.add('old',5,'done');self.app.executing_jobs['old']=({'team'},True);self.add('new',5)
        self.assertIsNone(self.app.next_job('chat'))
        self.app.executing_jobs.clear();self.assertEqual(self.app.next_job('chat')['id'],'new')
    def test_parallel_execution_preserves_other_owner_fence(self):
        started=threading.Event();release=threading.Event()
        self.app.stop_checkpoint=lambda _:False
        self.app._execute=lambda r: (started.set(),release.wait(2)) if r['id']=='first' else None
        first={'id':'first','owner':'team','kind':'chat','payload':'{}'}
        t=threading.Thread(target=self.app.execute,args=(first,));t.start();self.assertTrue(started.wait(1))
        try:
            self.app.execute({'id':'second','owner':'other','kind':'chat','payload':'{}'})
            self.assertEqual(self.app.executing_owners,{'team'})
        finally:release.set();t.join(2)
        self.assertEqual(self.app.executing_owners,set())
    def test_identity_lock_is_shared(self):
        self.assertIs(self.app.agent_lock('a'),self.app.agent_lock('a'))
        self.assertIsNot(self.app.agent_lock('a'),self.app.agent_lock('b'))
