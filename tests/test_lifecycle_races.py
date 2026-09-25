"""Deterministic lifecycle interleavings, not probabilistic sleep-based races."""
import concurrent.futures
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parent)]
from studio import Studio,Problem
from test_studio import Adapter

class LifecycleRaces(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.adapter=Adapter();self.studio=Studio(self.temp.name,self.adapter,start_worker=False)
  row,_=self.studio.session();self.owner=row['id']
  self.profile={'name':'Lifecycle','persona':'analyst','skills':['memory']}
  self.studio.onboard(self.owner,self.profile)
 def tearDown(self):self.temp.cleanup()
 def until(self,predicate):
  deadline=time.monotonic()+5
  while not predicate():
   if time.monotonic()>deadline:self.fail('Interleaving did not reach expected state')
   time.sleep(.005)
 def exists(self):return self.studio.profile(self.owner) is not None
 def test_failed_creation_rolls_back_files_and_database(self):
  before=set((Path(self.temp.name)/'workspaces').iterdir())
  def fail(db,owner,profile):
   (self.studio.workspace(owner)/'partial.txt').write_text('partial initialization')
   raise OSError('disk failure after workspace allocation')
  with patch.object(self.studio,'queue_agent_preparation',side_effect=fail):
   with self.assertRaises(OSError):self.studio.add_agent(self.owner,{**self.profile,'name':'Partial'})
  self.assertEqual(set((Path(self.temp.name)/'workspaces').iterdir()),before)
  with self.studio.db() as db:self.assertEqual(db.execute('select count(*) from agents where profile is not null').fetchone()[0],1)
 def test_creation_collision_never_removes_existing_files(self):
  existing='f'*24;path=self.studio.workspace(existing);path.mkdir();(path/'keep').write_text('keep')
  with patch('studio.secrets.token_hex',return_value=existing):
   with self.assertRaises(FileExistsError):self.studio.add_agent(self.owner,self.profile)
  self.assertEqual((path/'keep').read_text(),'keep')
 def test_policy_poll_racing_with_radar_delete_returns_controlled_status(self):
  # A policy read is deliberately outside the deletion lock and may be slow.
  self.studio.configure(self.owner,{**self.profile,'skills':['radar']})
  def report(*args):
   self.studio.delete_agent(self.owner,{'name':'Lifecycle'})
   return {'status':'applied','catalog':{},'logs':[]}
  with patch.object(self.adapter,'policy_status',side_effect=report,create=True):
   with self.assertRaises(Problem) as error:self.studio.policy_report(self.owner)
  self.assertEqual(error.exception.status,404)
 def test_error_during_stop_does_not_strand_deletion(self):
  self.studio.enqueue(self.owner,{'prompt':'In flight'})
  row=self.studio.next_job()
  def interrupted(_):
   self.studio.delete_agent(self.owner,{'name':'Lifecycle'},enqueue_only=True)
   raise RuntimeError('Native policy call returned after cancellation')
  with patch.object(self.studio,'_execute',side_effect=interrupted):self.studio.execute(row)
  with self.studio.db() as db:self.assertEqual(db.execute('select status from jobs where id=?',(row['id'],)).fetchone()[0],'cancelled')
  self.studio.finish_pending_deletions();self.assertFalse(self.exists())
  self.assertTrue(self.studio.stop_checkpoint(row['id']))
  self.studio.event(row['id'],'Late callback','Must not resurrect',status='done')
  with self.studio.db() as db:self.assertEqual(db.execute('select count(*) from jobs').fetchone()[0],0)
 def test_cancelled_job_cannot_be_revived_by_late_success(self):
  job=self.studio.enqueue(self.owner,{'prompt':'Queued'})
  self.studio.decision(self.owner,job['id'],'cancel')
  self.studio.event(job['id'],'Late success','Ignore',status='done')
  with self.studio.db() as db:self.assertEqual(db.execute('select status from jobs where id=?',(job['id'],)).fetchone()[0],'cancelled')
 def test_stale_runtime_has_actionable_cleanup_error(self):
  from deletion_residue import CleanupPrerequisiteError
  with patch.object(self.adapter,'remove',side_effect=CleanupPrerequisiteError('Restart the managed agent runtime.')):
   with self.assertRaises(Problem) as error:self.studio.delete_agent(self.owner,{'name':'Lifecycle'})
  self.assertIn('Restart',str(error.exception));self.assertTrue(self.exists())
 def test_edit_native_failure_does_not_publish_half_updated_profile(self):
  old=self.studio.profile(self.owner)
  with patch.object(self.studio.heartbeat,'disable',side_effect=RuntimeError('native unavailable')):
   with self.assertRaises(RuntimeError):self.studio.configure(self.owner,{**self.profile,'name':'Not committed','skills':['radar']})
  self.assertEqual(self.studio.profile(self.owner),old)
  with self.studio.db() as db:self.assertEqual(db.execute('select count(*) from jobs').fetchone()[0],0)
 def test_delete_wins_during_edit_without_orphan_warmup(self):
  entered=threading.Event();release=threading.Event()
  def pause(_):
   entered.set()
   if not release.wait(5):raise RuntimeError('Test timed out')
  with concurrent.futures.ThreadPoolExecutor(2) as pool,patch.object(self.studio.heartbeat,'disable',side_effect=pause):
   edit=pool.submit(self.studio.configure,self.owner,{**self.profile,'name':'Edited','skills':['radar']})
   self.assertTrue(entered.wait(5))
   removal=pool.submit(self.studio.delete_agent,self.owner,{'name':'Lifecycle'})
   try:self.until(lambda:not self.exists())
   finally:release.set()
   with self.assertRaises(Problem) as error:edit.result(5)
   self.assertEqual(error.exception.status,404)
   self.assertEqual(removal.result(5)['deleted'],self.owner)
  with self.studio.db() as db:
   for table in ('jobs','agent_deletions'):
    self.assertEqual(db.execute('select count(*) from '+table+' where owner=?',(self.owner,)).fetchone()[0],0)
  self.assertIsNone(self.studio.next_job())
 def test_new_job_during_edit_preserves_original_profile(self):
  entered=threading.Event();release=threading.Event()
  def pause(_):entered.set();self.assertTrue(release.wait(5))
  with concurrent.futures.ThreadPoolExecutor(1) as pool,patch.object(self.studio.heartbeat,'disable',side_effect=pause):
   edit=pool.submit(self.studio.configure,self.owner,{**self.profile,'name':'Edited','skills':['radar']})
   self.assertTrue(entered.wait(5))
   self.studio.enqueue(self.owner,{'prompt':'New task'})
   release.set()
   with self.assertRaises(Problem) as error:edit.result(5)
   self.assertEqual(error.exception.status,409)
  self.assertEqual(self.studio.profile(self.owner)['name'],'Lifecycle')
 def test_edit_coalesces_pending_warmups(self):
  for _ in range(5):self.studio.configure(self.owner,{**self.profile,'skills':['radar']})
  with self.studio.db() as db:self.assertEqual(db.execute("select count(*) from jobs where kind='prepare-agent' and status='queued'").fetchone()[0],1)
 def test_deleted_or_missing_owner_never_enters_worker(self):
  self.studio.delete_agent(self.owner,{'name':'Lifecycle'},enqueue_only=True)
  with self.studio.db() as db:
   for owner,job in ((self.owner,'fenced'),('absent','orphan')):
    db.execute('insert into jobs values (?,?,?,?,?,?,?,?,?,?)',(job,owner,'prepare-agent','queued','{}','{}','[]',0,0,0))
  self.assertIsNone(self.studio.next_job())
  with self.studio.db() as db:
   self.assertIsNone(db.execute("select 1 from jobs where id='orphan'").fetchone())
   self.assertEqual(db.execute("select status from jobs where id='fenced'").fetchone()[0],'cancelled')
 def test_stale_onboard_after_deletion_is_not_server_error(self):
  self.studio.delete_agent(self.owner,{'name':'Lifecycle'})
  with self.assertRaises(Problem) as error:self.studio.onboard(self.owner,self.profile)
  self.assertEqual(error.exception.status,404)
  self.assertFalse(self.studio.workspace(self.owner).exists())
 def test_heartbeat_cannot_enable_after_delete_disable(self):
  self.studio.heartbeat.presence(self.owner,'race-test-tab')
  self.studio.configure(self.owner,{**self.profile,'skills':['radar']})
  with self.studio.db() as db:db.execute('delete from jobs')
  native='bac-'+self.owner;self.studio.provisioned.add(native)
  entered=threading.Event();release=threading.Event();enabled=[False];calls=[]
  def toggle(agent,on):
   if on:
    entered.set()
    if not release.wait(5):raise RuntimeError('Test timed out')
   enabled[0]=on;calls.append(on);return True
  self.adapter.set_radar_heartbeat=toggle
  with patch('runtime_settings.model_available',return_value=True),concurrent.futures.ThreadPoolExecutor(2) as pool:
   tick=pool.submit(self.studio.heartbeat.tick);self.assertTrue(entered.wait(5))
   remove=pool.submit(self.studio.delete_agent,self.owner,{'name':'Lifecycle'})
   def fenced():
    with self.studio.db() as db:
     row=db.execute('select deleting from agents where id=?',(self.owner,)).fetchone()
     return row is None or row['deleting']!=0
   try:self.until(fenced)
   finally:release.set()
   tick.result(5);remove.result(5)
  self.assertFalse(enabled[0]);self.assertEqual(calls[-1],False)
  self.assertNotIn(self.owner,self.studio.heartbeat.statuses)
 def test_unavailable_heartbeat_does_not_prevent_server_start(self):
  self.studio.configure(self.owner,{**self.profile,'skills':['radar']})
  self.adapter.set_radar_heartbeat=lambda *args:(_ for _ in ()).throw(RuntimeError('unavailable'))
  with patch('runtime_settings.model_available',return_value=False):
   restarted=Studio(self.temp.name,self.adapter,start_worker=True)
   try:self.assertIsNotNone(restarted.profile(self.owner))
   finally:
    restarted.stop.set();restarted.signal.set();restarted.deletion_signal.set()
    for worker in (restarted.worker,restarted.deletion_worker,restarted.heartbeat_worker):worker.join(5)
    restarted.instance_lock.close()

if __name__=='__main__':unittest.main()
