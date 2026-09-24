"""Deletion state combinations and crash boundaries, not only happy-path profiles.

Native calls are fault-injected here. Real installed-runtime coverage lives in
live-deletion-cycles.py and live-deletion-reset.cjs; do not confuse the two.
"""
import itertools,json,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import test_agent_deletion as base
from test_studio import Studio
from studio import Problem
import agent_runtime as rt

class CleanupStateTests(unittest.TestCase):
    def test_unused_batch_keeps_registered_and_shared_workspaces_on_full_cleanup_path(self):
        import subprocess
        with tempfile.TemporaryDirectory() as temp,patch.object(rt,'root',return_value=Path(temp)/'native'):
            nid='bac-'+'a'*24;work=Path(temp)/'work';work.mkdir()
            config=rt.initial_config();config['agents']['entries']={nid:{'workspace':str(work/'personal')},'other':{'workspace':str(work/'shared')}};rt.save_config(config)
            targets=[(nid,work/'personal'),(nid+'-r0',work/'shared/child'),(nid+'-r1',work/'unused')]
            with patch.object(rt.subprocess,'run',return_value=subprocess.CompletedProcess([],0,json.dumps({'unregistered':[nid+'-r1']}),'')) as command:
                self.assertEqual(rt.unregistered_deletion_targets(targets),{nid+'-r1'})
                self.assertEqual(json.loads(command.call_args.args[0][-1]),[nid+'-r1'])
            for report in ({'unregistered':[nid]}, {'unregistered':[nid+'-r1']*2}, {}, []):
                with self.subTest(report=report),patch.object(rt.subprocess,'run',return_value=subprocess.CompletedProcess([],0,json.dumps(report),'')):
                    with self.assertRaises(RuntimeError):rt.unregistered_deletion_targets(targets)

    def test_64_registration_files_registry_combinations(self):
        nid='bac-'+'a'*24
        for entry,folder,documents,marker,registry,enabled in itertools.product((False,True),repeat=6):
            with self.subTest(entry=entry,folder=folder,documents=documents,marker=marker,registry=registry,enabled=enabled), tempfile.TemporaryDirectory() as temp:
                root=Path(temp)/'native';work=Path(temp)/'workspace';work.mkdir();(work/'memory.txt').write_text('retain until verified')
                other=Path(temp)/'other';other.mkdir();(other/'keep').write_text('other owner')
                if documents:(work/'IDENTITY.md').write_text('definitions only')
                if marker:(work/'.bac-prepared-only').touch()
                with patch.object(rt,'root',return_value=root):
                    config=rt.initial_config();config['plugins']['entries']['openshell']={'enabled':enabled}
                    if entry:config['agents']['entries'][nid]={'workspace':str(work)}
                    rt.save_config(config)
                    if folder:(root/'state/agents'/nid/'sessions').mkdir(parents=True)
                    calls=[]
                    with patch.object(rt,'quiesce_native',side_effect=lambda _:calls.append('stop')) as stop, \
                         patch('agent_policy.runtimes',return_value=[{'containerName':'oc-owned'}] if registry else []) as lookup, \
                         patch('agent_policy.sandbox_names',side_effect=[{'oc-owned','oc-other'},{'oc-other'}]), \
                         patch('agent_policy.shell',side_effect=lambda *a:calls.append('sandbox')) as shell, \
                         patch('agent_policy.sandbox_registry',side_effect=lambda *a:calls.append('registry')) as retire, \
                         patch.object(rt,'delete_native',side_effect=lambda _:calls.append('native') or json.dumps({'agentId':nid,'failed':[]})) as native:
                        rt.remove(nid,work)
                    self.assertEqual(stop.call_count,int(entry or folder))
                    lookup.assert_called_once_with(nid,probe=False);native.assert_called_once_with(nid)
                    self.assertEqual(calls,(['stop'] if entry or folder else [])+(['sandbox','registry'] if registry else [])+['native'])
                    self.assertEqual((other/'keep').read_text(),'other owner')
                    self.assertTrue((work/'memory.txt').exists(),'Adapter must not bypass app/native ownership cleanup')

    def test_corrupt_or_missing_configuration_never_means_empty_runtime(self):
        for content in ('{','null','[]','{}','{"agents":{"entries":[]}}','{"agents":{"entries":{"x":null}}}',None):
            with self.subTest(content=content),tempfile.TemporaryDirectory() as temp,patch.object(rt,'root',return_value=Path(temp)):
                rt.config_path().parent.mkdir();work=Path(temp)/'workspace';work.mkdir()
                (work/'.bac-prepared-only').touch();(work/'keep').write_text('data')
                if content is not None:rt.config_path().write_text(content)
                with patch.object(rt,'delete_native') as delete,patch('agent_policy.runtimes') as lookup:
                    with self.assertRaises(RuntimeError):rt.remove('bac-'+'a'*24,work)
                    delete.assert_not_called();lookup.assert_not_called()
                self.assertEqual((work/'keep').read_text(),'data')

    def test_missing_workspace_and_marker_still_reconciles_native_journal(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(rt,'root',return_value=Path(temp)):
            rt.save_config(rt.initial_config());nid='bac-'+'a'*24
            with patch('agent_policy.runtimes',return_value=[]),patch.object(rt,'delete_native',return_value=json.dumps({'agentId':nid,'failed':[],'purgeFailed':True})) as delete:
                with self.assertRaises(rt.NativeCleanupPending):rt.remove(nid,Path(temp)/'absent')
                delete.assert_called_once_with(nid)

    def test_rejected_or_malformed_confirmation_never_completes(self):
        nid='bac-'+'a'*24
        for report in ([],None,{}, {'agentId':nid}, {'agentId':nid,'failed':None}, {'agentId':nid,'failed':[],'ok':False}, {'agentId':'bac-'+'b'*24,'failed':[]}):
            with self.subTest(report=report),tempfile.TemporaryDirectory() as temp,patch.object(rt,'root',return_value=Path(temp)):
                rt.save_config(rt.initial_config());work=Path(temp)/'workspace';work.mkdir();(work/'keep').write_text('keep')
                with patch('agent_policy.runtimes',return_value=[]),patch.object(rt,'delete_native',return_value=json.dumps(report)):
                    with self.assertRaises(RuntimeError):rt.remove(nid,work)
                self.assertTrue((work/'keep').exists())

    def test_registered_identity_without_explicit_workspace_is_not_unregistered(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(rt,'root',return_value=Path(temp)):
            nid='bac-'+'a'*24;config=rt.initial_config();config['agents']['entries'][nid]={};rt.save_config(config)
            with patch.object(rt,'delete_native') as delete:
                with self.assertRaisesRegex(RuntimeError,'workspace changed'):rt.remove(nid,Path(temp)/'workspace')
                delete.assert_not_called()

    def test_delayed_sandbox_removal_keeps_registry_and_resumes_after_absence(self):
        import subprocess
        for timeout in (False,True):
            with self.subTest(timeout=timeout),tempfile.TemporaryDirectory() as temp,patch.object(rt,'root',return_value=Path(temp)):
                nid='bac-'+'a'*24;rt.save_config(rt.initial_config())
                with patch('agent_policy.runtimes',return_value=[{'containerName':'oc-owned'}]), \
                     patch('agent_policy.sandbox_names',return_value={'oc-owned'}) as inventory, \
                     patch('agent_policy.shell',side_effect=subprocess.TimeoutExpired('delete',35) if timeout else None) as shell, \
                     patch('agent_policy.sandbox_registry') as retire,patch.object(rt,'time') as clock, \
                     patch.object(rt,'delete_native',return_value=json.dumps({'agentId':nid,'failed':[]})) as delete:
                    with self.assertRaises(rt.NativeCleanupPending):rt.remove(nid,Path(temp)/'workspace')
                    retire.assert_not_called();delete.assert_not_called()
                    inventory.return_value=set();shell.reset_mock()
                    rt.remove(nid,Path(temp)/'workspace')
                    shell.assert_not_called();retire.assert_called_once_with(nid,['oc-owned']);delete.assert_called_once_with(nid)

class CleanupCrashTests(unittest.TestCase):
    setUp=base.DeletionTests.setUp
    tearDown=base.DeletionTests.tearDown

    def test_only_proven_unused_targets_skip_individual_native_cleanup(self):
        from unittest.mock import Mock
        nid=self.studio.profile(self.scout)['id']
        self.adapter.unregistered_deletion_targets=Mock(return_value={nid+'-r0',nid+'-r2'})
        with patch.object(self.adapter,'remove',wraps=self.adapter.remove) as remove:
            self.studio.delete_agent(self.scout,{'name':'Scout'})
        self.assertEqual([call.args[0] for call in remove.call_args_list],[nid,nid+'-r1',nid+'-r3'])
        self.assertEqual(len(self.adapter.unregistered_deletion_targets.call_args.args[0]),5)
        self.assertFalse(any(self.studio.workspace(self.scout).parent.glob(self.scout+'*')))
        self.assertIsNotNone(self.studio.profile(self.owner))

    def test_failed_batch_inspection_preserves_files_and_fences_agent(self):
        from unittest.mock import Mock
        self.adapter.unregistered_deletion_targets=Mock(side_effect=RuntimeError('Registry unavailable'))
        with patch.object(self.adapter,'remove') as remove:
            with self.assertRaises(Problem):self.studio.delete_agent(self.scout,{'name':'Scout'})
            remove.assert_not_called()
        self.assertTrue(self.studio.state(self.scout)['deleting'])
        self.assertTrue(self.studio.workspace(self.scout).exists())

    def test_duplicate_request_joins_pending_cleanup_without_replaying_it(self):
        self.studio.executing_owners={self.scout}
        self.studio.delete_agent(self.scout,{'name':'Scout'})
        self.studio.delete_lock.acquire()
        try:
            with patch.object(self.adapter,'remove') as remove:
                self.assertEqual(self.studio.delete_agent(self.scout,{'name':'Scout'})['deleting'],self.scout)
                with self.assertRaises(Problem):self.studio.delete_agent(self.scout,{'name':'Changed'})
                self.assertEqual(self.studio.delete_agent(self.owner,{'name':'Jinny'})['deleting'],self.owner)
                remove.assert_not_called()
            self.studio.signal.clear()
            self.studio.finish_pending_deletions()
            self.studio.delete_agent(self.scout,{'name':'Scout'})
            self.assertFalse(self.studio.signal.is_set(),'A busy cleanup slot must not spin the worker')
        finally:self.studio.delete_lock.release()
        self.studio.executing_owners=set()
        self.studio.finish_pending_deletions()
        self.assertIsNone(self.studio.profile(self.scout));self.assertIsNone(self.studio.profile(self.owner))

    def test_restart_after_every_native_target_finishes_remaining_plan(self):
        # SystemExit represents process death: bypass ordinary Exception handling.
        for boundary in range(5):
            with self.subTest(boundary=boundary):
                target=self.studio.add_agent(self.owner,{**self.profile,'name':'Crash'+str(boundary)})['agentId']
                original=self.adapter.remove;seen=[]
                def crash(nid,workspace):
                    original(nid,workspace)
                    if workspace.exists():shutil.rmtree(workspace)
                    seen.append(nid)
                    if len(seen)==boundary+1:raise SystemExit('simulated process termination')
                with patch.object(self.adapter,'remove',side_effect=crash):
                    with self.assertRaises(SystemExit):self.studio.delete_agent(target,{'name':'Crash'+str(boundary)})
                restarted=Studio(self.temp.name,self.adapter,start_worker=False,recover=True)
                with patch.object(self.adapter,'remove',wraps=original) as resumed:
                    restarted.finish_pending_deletions()
                    self.assertEqual(len(resumed.call_args_list),5,'Persist targets even after native config/workspace disappeared')
                self.assertIsNone(restarted.profile(target));self.assertIsNotNone(restarted.profile(self.owner))
                self.assertFalse(any(restarted.workspace(target).parent.glob(target+'*')))
                self.studio=restarted

    def test_failed_app_file_cleanup_retries_without_resurrecting_agents(self):
        actual=shutil.rmtree;workspace=self.studio.workspace(self.scout)
        def fail(path,*args,**kwargs):
            if Path(path)==workspace:raise PermissionError('simulated read-only storage')
            return actual(path,*args,**kwargs)
        with patch('studio.shutil.rmtree',side_effect=fail):
            with self.assertRaises(Problem):self.studio.delete_agent(self.scout,{'name':'Scout'})
        restarted=Studio(self.temp.name,self.adapter,start_worker=False,recover=True)
        self.assertTrue(restarted.state(self.scout)['deleting'])
        restarted.delete_agent(self.scout,{'name':'Scout'})
        self.assertIsNone(restarted.profile(self.scout));self.assertIsNotNone(restarted.profile(self.owner))

    def test_heartbeat_disable_error_is_fenced_and_exits_waiting_state(self):
        with self.studio.db() as db:
            p=self.studio.profile(self.scout);p['skills']=['radar'];db.execute('UPDATE agents SET profile=? WHERE id=?',(json.dumps(p),self.scout))
        with patch.object(self.studio.heartbeat,'disable',side_effect=RuntimeError('temporary failure')):
            with self.assertRaises(Problem):self.studio.delete_agent(self.scout,{'name':'Scout'})
        state=self.studio.state(self.scout)
        self.assertTrue(state['deleting'])
        self.assertFalse(next(a for a in state['agents'] if a['key']==self.scout)['deletionWaiting'])
        self.studio.delete_agent(self.scout,{'name':'Scout'});self.assertIsNone(self.studio.profile(self.scout))

if __name__=='__main__':unittest.main()
