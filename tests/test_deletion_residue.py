"""Residue ownership, partial permanent purge and post-native crash recovery."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import deletion_residue as residue
from studio import Studio, Problem
from test_studio import Adapter

class ResidueTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name).resolve()/'runtime';self.root.mkdir()
        self.work=self.root.parent/'workspace';self.work.mkdir()
        self.nid='bac-'+'a'*24
        self.trash=self.root.parent/'trash';self.trash.mkdir()
        for leaf in ('agent','sessions'):(self.root/'state/agents'/self.nid/leaf).mkdir(parents=True)
        residue.prepare(self.root,self.nid,self.work)
    def tearDown(self):self.temp.cleanup()
    def move(self):
        receipt=json.loads(residue.receipt_path(self.root,self.nid).read_text())
        boxes=[]
        for source in map(Path,receipt['paths']):
            box=self.trash/(source.name+'-123456-Abc123');box.mkdir()
            shutil.move(str(source),str(box/source.name));boxes.append(box)
        receipt['routed']=receipt['marked']
        receipt['trash']=[{'name':box.name,'dev':box.stat().st_dev,'ino':box.stat().st_ino} for box in boxes]
        residue.atomic_json(residue.receipt_path(self.root,self.nid),receipt)
        return boxes
    def test_ten_cycles_leave_no_copies_receipts_or_other_owner_changes(self):
        other=self.trash/'agent-123456-Other1';(other/'agent').mkdir(parents=True)
        (other/'agent/keep').write_text('unrelated')
        for cycle in range(10):
            if cycle:
                self.work.mkdir()
                for leaf in ('agent','sessions'):(self.root/'state/agents'/self.nid/leaf).mkdir(exist_ok=True)
                residue.prepare(self.root,self.nid,self.work)
            self.move();residue.purge(self.root,self.nid,self.trash);residue.forget_receipt(self.root,self.nid)
            self.assertEqual(list(self.trash.iterdir()),[other])
            self.assertFalse((self.root/'deletion-receipts').exists())
    def test_pending_native_data_never_purges_trash(self):
        with self.assertRaisesRegex(RuntimeError,'remain'):residue.purge(self.root,self.nid,self.trash)
        self.assertTrue(self.work.exists())
    def test_crash_after_marker_removed_resumes_from_inode_receipt(self):
        boxes=self.move();original=shutil.rmtree
        def interrupted(path):
            for marker in Path(path).rglob(residue.MARKER):marker.unlink()
            raise OSError('injected partial removal')
        with patch.object(residue.shutil,'rmtree',side_effect=interrupted) as remove:
            remove.avoids_symlink_attacks=True
            with self.assertRaises(OSError):residue.purge(self.root,self.nid,self.trash)
        residue.purge(self.root,self.nid,self.trash)
        self.assertTrue(all(not p.exists() for p in boxes))
    def test_replaced_trash_container_is_never_removed(self):
        boxes=self.move()
        with patch.object(residue.shutil,'rmtree',side_effect=OSError('stop')) as remove:
            remove.avoids_symlink_attacks=True
            with self.assertRaises(OSError):residue.purge(self.root,self.nid,self.trash)
        moved=boxes[0].with_name('keep-replaced-original');boxes[0].rename(moved);boxes[0].mkdir()
        with self.assertRaisesRegex(RuntimeError,'replaced'):residue.purge(self.root,self.nid,self.trash)
        self.assertTrue(moved.exists());self.assertTrue(boxes[0].exists())
    def test_symlink_inside_owned_trash_never_deletes_target(self):
        boxes=self.move();outside=self.root.parent/'outside';outside.mkdir();(outside/'keep').write_text('keep')
        (boxes[0]/'external-link').symlink_to(outside,target_is_directory=True)
        residue.purge(self.root,self.nid,self.trash)
        self.assertFalse(boxes[0].exists());self.assertTrue((outside/'keep').exists())
        with self.assertRaises(RuntimeError):residue.purge(self.root,self.nid,self.trash/'../trash')
    def test_old_gateway_without_routing_proof_cannot_report_success(self):
        self.move();path=residue.receipt_path(self.root,self.nid)
        value=json.loads(path.read_text());value['routed']=[];residue.atomic_json(path,value)
        with self.assertRaisesRegex(RuntimeError,'runtime'):residue.purge(self.root,self.nid,self.trash)

    def test_invalid_container_names_cannot_delete_staging_parent(self):
        self.move();receipt=residue.receipt_path(self.root,self.nid)
        value=json.loads(receipt.read_text())
        for name in ('','.', '..', '../outside', '/absolute'):
            with self.subTest(name=name):
                value['trash']=[{'name':name,'dev':self.trash.stat().st_dev,'ino':self.trash.stat().st_ino}]
                residue.atomic_json(receipt,value)
                with self.assertRaisesRegex(RuntimeError,'Invalid'):residue.purge(self.root,self.nid,self.trash)
                self.assertTrue(self.trash.exists())

class StagingReadinessTests(unittest.TestCase):
    def test_old_or_dead_gateway_is_rejected_before_deletion(self):
        import agent_runtime as rt
        with tempfile.TemporaryDirectory() as temp,patch.object(rt,'root',return_value=Path(temp)):
            root=Path(temp);pkg=root/'package/node_modules/openclaw';pkg.mkdir(parents=True)
            (pkg/'package.json').write_text('{"version":"2026.9.4"}')
            workspace=root/'workspace';workspace.mkdir();(workspace/'keep').write_text('keep')
            nid='bac-'+'a'*24;config=rt.initial_config();config['agents']['entries'][nid]={'workspace':str(workspace)};rt.save_config(config)
            for value in (None,[],{}, {'version':1,'pid':123,'integration':'outdated'}):
                with self.subTest(value=value):
                    (root/'cleanup-capability.json').write_text(json.dumps(value))
                    with patch.object(rt,'quiesce_native') as quiesce,patch.object(rt,'delete_native') as delete:
                        with self.assertRaisesRegex(RuntimeError,'Restart'):rt.remove(nid,workspace)
                        quiesce.assert_not_called();delete.assert_not_called()
                    self.assertEqual((workspace/'keep').read_text(),'keep')
    def test_matching_live_capability_is_required(self):
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);pkg=root/'package/node_modules/openclaw';pkg.mkdir(parents=True);(pkg/'package.json').write_text('{}')
            digest=hashlib.sha256()
            for name in ('native_cleanup_loader.mjs','native_cleanup_trash.mjs'):digest.update(Path(residue.__file__).with_name(name).read_bytes())
            (root/'cleanup-capability.json').write_text(json.dumps({'version':1,'pid':123,'integration':digest.hexdigest()}))
            with patch.object(residue.os,'kill') as alive:residue.require_staging_runtime(root);alive.assert_called_once_with(123,0)
            with patch.object(residue.os,'kill',side_effect=ProcessLookupError):
                with self.assertRaisesRegex(RuntimeError,'Restart'):residue.require_staging_runtime(root)

class CompletionTests(unittest.TestCase):
    def test_finalize_failure_keeps_fence_and_restart_retry_removes_every_owned_row(self):
        with tempfile.TemporaryDirectory() as temp:
            adapter=Adapter();studio=Studio(temp,adapter,start_worker=False)
            account,_=studio.session();owner=account['id']
            studio.onboard(owner,{'name':'Retire','persona':'maker','skills':['memory']})
            studio.heartbeat.statuses[owner]={'state':'watching'}
            studio.protection_activity.events.append({'owner':owner})
            adapter.finalize_removal=lambda *args:(_ for _ in ()).throw(RuntimeError('injected finalization failure'))
            with self.assertRaises(Problem):studio.delete_agent(owner,{'name':'Retire'})
            self.assertIsNotNone(studio.profile(owner))
            adapter.finalize_removal=lambda *args:None
            studio.delete_agent(owner,{'name':'Retire'})
            with studio.db() as db:
                for table,key in [('agents','id'),('jobs','owner'),('agent_deletions','owner'),('agent_policies','owner'),('heartbeat_controls','owner'),('heartbeat_receipts','owner')]:
                    self.assertEqual(db.execute('SELECT count(*) FROM '+table+' WHERE '+key+'=?',(owner,)).fetchone()[0],0)
                self.assertEqual(db.execute('PRAGMA secure_delete').fetchone()[0],1)
            self.assertNotIn(owner,studio.heartbeat.statuses)
            self.assertFalse(studio.protection_activity.events)

if __name__=='__main__':unittest.main()
