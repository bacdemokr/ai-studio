"""A temporary SQLite writer must not permanently strand either job lane."""
import contextlib,sqlite3,tempfile,threading,time,unittest
from unittest.mock import patch
from studio import Studio
from test_hiring_preparation import ProtectedAdapter

class QueueRecoveryTests(unittest.TestCase):
 def test_both_lanes_survive_a_real_database_lock_without_replaying_work(self):
  for lane in ('background','chat'):
   with self.subTest(lane=lane),tempfile.TemporaryDirectory() as folder:
    adapter=ProtectedAdapter();studio=Studio(folder,adapter,start_worker=False)
    personal=studio.session()[0]['id']
    if lane=='background':
     owner=studio.crew_owner(personal,'event-brief');job=studio.prepare_demo(owner,{'background':True})
    else:
     studio.onboard(personal,{'name':'Test','skills':['memory'],'persona':'guide','protection':'standard'})
     job=studio.enqueue(personal,{'prompt':'Hello'})
    original=studio.db;attempts=[]
    @contextlib.contextmanager
    def impatient_db():
     with original() as db:
      db.execute('PRAGMA busy_timeout=20')
      attempts.append(time.monotonic())
      yield db
    blocker=sqlite3.connect(studio.db_path);blocker.execute('BEGIN IMMEDIATE')
    with patch.object(studio,'db',side_effect=impatient_db):
     thread=threading.Thread(target=studio.work,args=(lane,));thread.start()
     try:
      time.sleep(.7)
      self.assertTrue(thread.is_alive(),'Queue died on database contention')
      blocker.rollback();blocker.close()
      deadline=time.monotonic()+5
      while time.monotonic()<deadline:
       with original() as db:status=db.execute('SELECT status FROM jobs WHERE id=?',(job['id'],)).fetchone()[0]
       if status=='done':break
       time.sleep(.03)
      self.assertEqual(status,'done')
      self.assertGreater(len(attempts),2)
      self.assertEqual(len(adapter.calls),1 if lane=='chat' else 0)
     finally:
      studio.stop.set();studio.signal.set();thread.join(3)
      blocker.close()
     self.assertFalse(thread.is_alive())

 def test_observer_instance_does_not_cancel_live_event_jobs(self):
  with tempfile.TemporaryDirectory() as folder:
   adapter=ProtectedAdapter();studio=Studio(folder,adapter,start_worker=False)
   participant=studio.session()[0]['id'];owner=studio.crew_owner(participant,'event-brief')
   job=studio.prepare_demo(owner,{'background':True})
   for state in ('queued','running','waiting','stopping'):
    with studio.db() as db:db.execute('UPDATE jobs SET status=? WHERE id=?',(state,job['id']))
    observer=Studio(folder,adapter,start_worker=False)
    with observer.db() as db:self.assertEqual(db.execute('SELECT status FROM jobs WHERE id=?',(job['id'],)).fetchone()[0],state)
   restarted=Studio(folder,adapter,start_worker=False,recover=True)
   with restarted.db() as db:self.assertEqual(db.execute('SELECT status FROM jobs WHERE id=?',(job['id'],)).fetchone()[0],'cancelled')

if __name__=='__main__':unittest.main()
