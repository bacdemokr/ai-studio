import sqlite3,tempfile,unittest
from studio import Studio
from test_hiring_preparation import ProtectedAdapter

class QueueRecoveryTests(unittest.TestCase):
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
