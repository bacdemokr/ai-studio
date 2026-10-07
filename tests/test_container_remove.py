"""Ownership, retry and shared-resource boundaries of Docker uninstall."""
import contextlib
import hashlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import container_remove as remove


class Engine:
    def __init__(self, containers=(), volumes=(), networks=(), images=()):
        self.containers=copy.deepcopy(list(containers)); self.volumes=list(volumes)
        self.networks=list(networks); self.images=list(images); self.calls=[]; self.fail=None

    def call(self, method, path):
        self.calls.append((method,path))
        if self.fail == (method,path): raise remove.DockerError(500,'fixture interruption')
        if method=='GET':
            if path.startswith('/containers/'): return self.containers
            if path=='/volumes': return {'Volumes':self.volumes}
            if path=='/networks': return self.networks
            if path.startswith('/networks/'): return next(n for n in self.networks if n['Id']==path.split('/')[-1])
            if path.startswith('/images/'): return self.images
        if method=='DELETE' and path.startswith('/containers/'):
            ident=path.split('/')[2].split('?')[0]
            self.containers=[c for c in self.containers if c['Id']!=ident]
        elif method=='DELETE' and path.startswith('/volumes/'):
            self.volumes=[v for v in self.volumes if v['Name']!=path.split('/')[-1]]
        elif method=='DELETE' and path.startswith('/networks/'):
            self.networks=[n for n in self.networks if n['Id']!=path.split('/')[-1]]
        elif method=='POST':
            for c in self.containers:
                if c['Id']==path.split('/')[2]: c['State']='running' if path.endswith('/start') else 'exited'


class RemovalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.gateway=self.root/'gateway'; self.gateway.mkdir()
        self.marker=self.gateway/'.bac-gateway.json'
        self.marker.write_text(json.dumps({'owner':'bac-demo','schema':1}))
        (self.gateway/'state').mkdir(); (self.gateway/'state/data').write_text('secret')
        self.studio={'Id':'studio','State':'running','Labels':{remove.PROJECT_LABEL:'bac-demo','com.docker.compose.service':'studio'},'Mounts':[]}
        self.sandbox={'Id':'sandbox','State':'running','Labels':{remove.MANAGER:'openshell',remove.NAMESPACE:'bac-demo'},'Mounts':[{'Type':'bind','Source':str(self.gateway/'cache')}]}
        self.foreign={'Id':'model','State':'running','Labels':{},'Mounts':[]}
        self.volume={'Name':'bac-demo_studio-data','Labels':{remove.PROJECT_LABEL:'bac-demo','com.docker.compose.volume':'studio-data'}}
        self.network={'Id':'net','Name':'bac-sandboxes','Labels':{remove.MANAGER:'openshell'},'Containers':{'sandbox':{}}}

    def run_remove(self, engine, **kwargs):
        output=io.StringIO()
        with contextlib.redirect_stdout(output): remove.remove(engine,self.gateway,**kwargs)
        return output.getvalue()

    def assert_untouched(self, engine):
        self.assertFalse(any(method!='GET' for method,_ in engine.calls))
        self.assertTrue(self.marker.exists())

    def test_owned_resources_removed_foreign_kept_and_repeat_succeeds(self):
        engine=Engine([self.sandbox,self.foreign,self.studio],[self.volume],[self.network])
        self.run_remove(engine)
        self.assertEqual(engine.containers,[self.foreign]); self.assertEqual(engine.volumes,[])
        self.assertEqual(list(self.gateway.iterdir()),[])
        deletions=[p for m,p in engine.calls if m=='DELETE']
        self.assertLess(deletions.index('/containers/studio?v=true'),deletions.index('/containers/sandbox?v=true'))
        self.run_remove(engine)

    def test_unknown_marker_or_volume_owner_rejects_before_mutating(self):
        engine=Engine([self.studio],[{**self.volume,'Labels':{}}])
        with self.assertRaisesRegex(RuntimeError,'different ownership'): self.run_remove(engine)
        self.assert_untouched(engine)
        self.marker.write_text('{}'); engine=Engine([self.studio])
        with self.assertRaisesRegex(RuntimeError,'ownership marker'): self.run_remove(engine)
        self.assert_untouched(engine)

    def test_foreign_users_block_even_if_stopped_or_falsely_labelled_helper(self):
        for mount in ({'Name':'bac-demo_studio-data'}, {'Source':str(self.gateway/'state')}):
            foreign={**self.foreign,'State':'exited','Labels':{'com.nvidia.bac.cleanup':'true'},'Mounts':[mount]}
            engine=Engine([self.studio,foreign])
            with self.assertRaisesRegex(RuntimeError,'Another container uses BaC data'): self.run_remove(engine,hostname='other-helper')
            self.assert_untouched(engine)

    def test_only_current_helper_exempt_from_mount_check(self):
        helper={**self.foreign,'Id':'abcdef1234567890','Labels':{'com.nvidia.bac.cleanup':'true'},'Mounts':[{'Source':str(self.gateway)}]}
        engine=Engine([self.studio,helper])
        self.run_remove(engine,hostname='abcdef123456')
        self.assertEqual(engine.containers,[helper]); self.assertFalse(self.marker.exists())

    def test_foreign_network_endpoint_prevents_any_removal(self):
        engine=Engine([self.studio,self.sandbox],networks=[{**self.network,'Containers':{'model':{}}}])
        with self.assertRaisesRegex(RuntimeError,'BaC network'): self.run_remove(engine)
        self.assert_untouched(engine)

    def test_sandbox_namespace_collision_and_unrecognized_service_are_rejected(self):
        for container in ({**self.sandbox,'Mounts':[]}, {**self.studio,'Labels':{remove.PROJECT_LABEL:'bac-demo','com.docker.compose.service':'unexpected'}}):
            engine=Engine([container])
            with self.assertRaises(RuntimeError): self.run_remove(engine)
            self.assert_untouched(engine)

    def test_partial_failure_keeps_marker_and_can_resume(self):
        engine=Engine([self.studio,self.sandbox],[self.volume])
        engine.fail=('DELETE','/containers/sandbox?v=true')
        with self.assertRaises(remove.DockerError): self.run_remove(engine)
        self.assertTrue(self.marker.exists()); self.assertNotIn(self.studio,engine.containers)
        engine.fail=None; self.run_remove(engine)
        self.assertEqual(engine.containers,[]); self.assertEqual(engine.volumes,[])
        self.assertFalse(self.marker.exists())

    def test_symlink_contents_never_followed_and_shared_files_preserved(self):
        outside=self.root/'shared'; outside.mkdir(); (outside/'keep').write_text('keep')
        (self.gateway/'linked').symlink_to(outside,target_is_directory=True)
        self.run_remove(Engine())
        self.assertEqual((outside/'keep').read_text(),'keep')
        self.gateway.rmdir(); self.gateway.symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError,'symlink'): self.run_remove(Engine())

    def test_image_candidates_include_old_bac_versions_but_not_generic_images(self):
        app={'Id':'sha256:app','RepoTags':['bac-studio:old'],'Labels':{'org.opencontainers.image.title':'BaC Agent Studio','org.opencontainers.image.source':'https://github.com/bacdemokr/tmp'}}
        foreign={'Id':'sha256:model','RepoTags':['ollama:latest'],'Labels':{}}
        output=self.run_remove(Engine(images=[app,foreign]),lock={'images':{'gateway':'gateway@sha256:pin','debian':'debian:stable'}})
        self.assertIn('BAC_IMAGE bac-studio:old',output); self.assertIn('BAC_IMAGE gateway@sha256:pin',output)
        self.assertNotIn('ollama:',output); self.assertNotIn('debian:',output)

    def installation(self):
        install=self.root/'install'; install.mkdir()
        for name in ('shared', 'backups'):
            (install/name).mkdir(); (install/name/'data').write_text('project data')
        (install/'bac').write_text('launcher')
        (install/'.env').write_text('BAC_IMAGE=bac-studio:test')
        return install

    def test_project_shared_and_backups_removed_including_repeat(self):
        install=self.installation()
        self.run_remove(Engine(),installation=install)
        self.assertFalse((install/'shared').exists()); self.assertFalse((install/'backups').exists())
        self.assertEqual((install/'bac').read_text(),'launcher')
        self.assertFalse((install/'.env').exists())
        self.run_remove(Engine(),installation=install)

    def test_project_data_symlinks_do_not_delete_external_targets(self):
        install=self.installation()
        outside=self.root/'external'; outside.mkdir(); (outside/'keep').write_text('keep')
        (install/'shared/link').symlink_to(outside,target_is_directory=True)
        self.run_remove(Engine(),installation=install)
        self.assertEqual((outside/'keep').read_text(),'keep')
        (install/'shared').symlink_to(outside,target_is_directory=True)
        self.run_remove(Engine(),installation=install)
        self.assertFalse((install/'shared').is_symlink())
        self.assertEqual((outside/'keep').read_text(),'keep')

    def test_project_data_mounts_checked_before_any_deletion(self):
        install=self.installation(); engine=Engine([self.studio])
        with patch.object(Path,'is_mount',lambda path: path==install/'backups'):
            with self.assertRaisesRegex(RuntimeError,'mounted filesystem'):
                self.run_remove(engine,installation=install)
        self.assert_untouched(engine)
        self.assertTrue((install/'shared/data').exists())

    def test_failed_container_cleanup_preserves_project_files_for_retry(self):
        install=self.installation(); engine=Engine([self.studio])
        engine.fail=('DELETE','/containers/studio?v=true')
        with self.assertRaises(remove.DockerError): self.run_remove(engine,installation=install)
        self.assertTrue((install/'backups/data').exists())
        engine.fail=None; self.run_remove(engine,installation=install)
        self.assertFalse((install/'backups').exists())

    def test_host_mount_path_used_for_project_data_usage_check(self):
        install=self.installation()
        foreign={**self.foreign,'Mounts':[{'Source':'/original/install/shared'}]}
        engine=Engine([self.studio,foreign])
        with self.assertRaisesRegex(RuntimeError,'Another container uses BaC data'):
            self.run_remove(engine,installation=install,host_installation='/original/install')
        self.assert_untouched(engine)

    def release(self):
        install=self.installation()
        (install/'runtime-lock.json').write_text('{}')
        (install/'release.json').write_text(json.dumps({'version':'0.1.0','image':'bac-studio:test',
            'runtimeLockSHA256':hashlib.sha256(b'{}').hexdigest()}))
        (install/'image.tar.gz').write_bytes(b'image archive')
        return install

    def test_release_removes_installer_archives_and_data(self):
        install=self.release()
        outside=self.root/'keep'; outside.write_text('outside')
        (install/'external-link').symlink_to(outside)
        self.run_remove(Engine(),installation=install,release=True)
        self.assertEqual(list(install.iterdir()),[])
        self.assertEqual(outside.read_text(),'outside')

    def test_invalid_release_or_git_checkout_rejected_before_deleting(self):
        install=self.release(); (install/'runtime-lock.json').write_text('changed')
        engine=Engine([self.studio])
        with self.assertRaisesRegex(RuntimeError,'release folder'):
            self.run_remove(engine,installation=install,release=True)
        self.assert_untouched(engine)
        (install/'runtime-lock.json').write_text('{}'); (install/'.git').mkdir()
        with self.assertRaisesRegex(RuntimeError,'release folder'):
            self.run_remove(engine,installation=install,release=True)
        self.assert_untouched(engine)

    def test_release_keeps_retry_files_on_data_deletion_error(self):
        install=self.release()
        with patch.object(remove.shutil,'rmtree',side_effect=OSError('fixture disk error')):
            with self.assertRaises(OSError): self.run_remove(Engine(),installation=install,release=True)
        self.assertTrue((install/'bac').exists()); self.assertTrue((install/'release.json').exists())
        self.run_remove(Engine(),installation=install,release=True)
        self.assertEqual(list(install.iterdir()),[])

    def test_image_history_accumulates_patch_versions_without_duplicates(self):
        first={'images':{'gateway':'gateway@sha256:old','supervisor':'supervisor@sha256:old'}}
        second={'images':{'gateway':'gateway@sha256:new','supervisor':'supervisor@sha256:new'}}
        remove.record_images(first,'bac-studio:1',self.gateway)
        remove.record_images(second,'bac-studio:2',self.gateway)
        remove.record_images(second,'bac-studio:2',self.gateway)
        saved=remove.image_history(self.gateway)
        self.assertEqual(len(saved),6)
        self.assertIn('gateway@sha256:old',saved)
        output=self.run_remove(Engine(),lock=second)
        for ref in saved: self.assertIn('BAC_IMAGE '+ref,output)
        self.assertEqual(list(self.gateway.iterdir()),[])

    def test_first_image_record_initializes_only_an_empty_owned_directory(self):
        gateway=self.root/'new-gateway'
        remove.record_images({'images':{}},'bac-studio:1',gateway)
        self.assertIsNotNone(remove.gateway_marker(gateway))
        self.assertEqual(remove.image_history(gateway),{'bac-studio:1'})
        foreign=self.root/'foreign-gateway'; foreign.mkdir(); (foreign/'state').write_text('keep')
        with self.assertRaisesRegex(RuntimeError,'not marked'):
            remove.record_images({'images':{}},'bac-studio:1',foreign)
        self.assertEqual((foreign/'state').read_text(),'keep')

    def test_corrupt_or_symlinked_history_is_rejected_before_any_mutation(self):
        path=self.gateway/remove.IMAGE_HISTORY
        for contents in ('[]', '{"owner":"other","images":[]}', '{"owner":"bac-demo","schema":1,"images":["--all"]}'):
            path.write_text(contents); engine=Engine([self.studio])
            with self.assertRaisesRegex(RuntimeError,'image history'):
                self.run_remove(engine)
            self.assert_untouched(engine)
        path.unlink(); path.symlink_to(self.root/'missing')
        with self.assertRaisesRegex(RuntimeError,'symlink'):
            remove.record_images({},'bac-studio:1',self.gateway)

    def test_remove_collects_all_app_tags_and_untagged_ids_but_not_other_images(self):
        labels={'org.opencontainers.image.title':'BaC Agent Studio','org.opencontainers.image.source':'https://github.com/bacdemokr/tmp'}
        images=[{'Id':'sha256:old','RepoTags':['bac-studio:old','bac-studio:old-alias'],'Labels':labels},
                {'Id':'sha256:dangling','RepoTags':None,'RepoDigests':None,'Labels':labels},
                {'Id':'sha256:legacytest','RepoTags':['bac-studio-tests:old'],'Labels':{}},
                {'Id':'sha256:unrelated','RepoTags':['other-project:test'],'Labels':{}}]
        output=self.run_remove(Engine(images=images))
        for ref in ('bac-studio:old','bac-studio:old-alias','sha256:old','sha256:dangling','bac-studio-tests:old','sha256:legacytest'):
            self.assertIn('BAC_IMAGE '+ref,output)
        self.assertNotIn('unrelated',output); self.assertNotIn('other-project',output)

    def test_old_container_image_is_collected_even_before_history_tracking(self):
        sandbox={**self.sandbox,'Image':'gateway@sha256:older-than-history'}
        output=self.run_remove(Engine([sandbox]))
        self.assertIn('BAC_IMAGE gateway@sha256:older-than-history',output)


if __name__=='__main__': unittest.main()
