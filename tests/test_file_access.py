import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts'), str(Path(__file__).parent)]
import file_access as files
import agent_runtime as runtime
import agent_policy as policy
from studio import Studio, Problem
from test_studio import Adapter

class FileAccessTests(unittest.TestCase):
    def test_invalid_read_finishes_with_path_error_before_runtime_or_model(self):
        adapter=Adapter();studio=Studio(self.root/'preflight',adapter,start_worker=False)
        owner=studio.session()[0]['id']
        studio.onboard(owner,{'name':'Files','persona':'guide','skills':['web'],'protection':'openshell'})
        missing=str(self.root/'missing.txt')
        job=studio.enqueue(owner,{'prompt':'Read '+missing})
        with patch.object(studio,'ensure_agent',side_effect=AssertionError('must not prepare runtime')):
            studio.execute(studio.next_job())
        with studio.db() as db:
            row=db.execute('select status,result from jobs where id=?',(job['id'],)).fetchone()
        self.assertEqual(row['status'],'done')
        self.assertIn('does not exist',json.loads(row['result'])['answer'])
        self.assertEqual(adapter.calls,[])
        report=studio.policy_report(owner)
        self.assertEqual(report['pendingFiles'],[])
        self.assertEqual(report['fileIssues'][0]['path'],missing)

    def test_create_requires_existing_parent_and_valid_reads_remain_approvable(self):
        studio=Studio(self.root/'preflight-create',Adapter(),start_worker=False)
        owner=studio.session()[0]['id']
        studio.onboard(owner,{'name':'Files','persona':'guide','skills':['web'],'protection':'openshell'})
        for prompt,expected_count,error in [
            ('Create '+str(self.root/'absent'/'new.txt'),0,'parent directory'),
            ('Create '+str(self.root/'new.txt'),1,None),
            ('Read '+str(self.host),2,None),
        ]:
            with self.subTest(prompt=prompt):
                job=studio.enqueue(owner,{'prompt':prompt});studio.decision(owner,job['id'],'cancel')
                report=studio.policy_report(owner)
                self.assertEqual(len(report['pendingFiles']),expected_count)
                if error:self.assertIn(error,report['fileIssues'][0]['reason'])
                else:self.assertEqual(report['fileIssues'],[])

    def test_quoted_paths_exclude_delimiters_and_preserve_literal_punctuation(self):
        for text in ("read '/home/jinhol/a.txt'", 'read "/home/jinhol/a.txt"',
                     'read `/home/jinhol/a.txt`', 'read /home/jinhol/a.txt?'):
            with self.subTest(text=text):
                self.assertEqual(files.requested_files(text), ['/home/jinhol/a.txt'])
        self.assertEqual(files.requested_files("read '/home/jinhol/my notes.txt'"), ['/home/jinhol/my notes.txt'])
        self.assertEqual(files.requested_files('read `/home/jinhol/a.txt\'`'), ["/home/jinhol/a.txt'"])
        self.assertEqual(files.requested_files('read `/home/jinhol/report!`'), ['/home/jinhol/report!'])

    def test_single_quoted_file_produces_usable_exact_permissions(self):
        studio=Studio(self.root/'quoted-data',Adapter(),start_worker=False)
        owner=studio.session()[0]['id']
        studio.onboard(owner,{'name':'Files','persona':'guide','skills':['weather'],'protection':'openshell'})
        job=studio.enqueue(owner,{'prompt':"Read '"+str(self.host)+"'"})
        studio.decision(owner,job['id'],'cancel')
        report=studio.policy_report(owner)
        self.assertIn(self.read,report['pendingFiles'])
        self.assertNotIn('unavailableReason',report['catalog'][self.read])
        self.assertEqual(studio.policy_change(owner,{'permission':self.read,'allow':True}),{'applied':True})

    def test_symlink_parent_error_identifies_the_blocked_component(self):
        alias=self.root/'alias';alias.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError) as error:
            files.checked_path(str(alias/'host.txt'))
        self.assertIn(str(alias),str(error.exception))
        self.assertIn('real file path',str(error.exception))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.workspace = self.root / 'workspace'; self.workspace.mkdir()
        self.host = self.root / 'host.txt'; self.host.write_text('original')
        self.read = 'file:read:' + str(self.host)
        self.write = 'file:write:' + str(self.host)

    def test_no_approval_no_host_copy(self):
        self.assertEqual(files.prepare(self.workspace, []), [])
        self.assertEqual(list((self.workspace/'inbox').iterdir()), [])

    def test_read_copy_does_not_modify_original(self):
        records = files.prepare(self.workspace, [self.read])
        copy = self.workspace/records[0]['relative']
        self.assertEqual(copy.read_text(), 'original')
        copy.write_text('edited');files.finish(self.workspace, records)
        self.assertEqual(self.host.read_text(), 'original')

    def test_write_and_revoke(self):
        records = files.prepare(self.workspace, [self.read,self.write])
        copy = self.workspace/records[0]['relative'];copy.write_text('new')
        files.finish(self.workspace, records)
        self.assertEqual(self.host.read_text(), 'new')
        files.prepare(self.workspace, [])
        self.assertFalse(copy.exists())

    def test_folder_created_in_copy_is_reported_and_next_turn_recovers(self):
        records=files.prepare(self.workspace,[self.write])
        copy=self.workspace/records[0]['relative']
        copy.unlink();copy.mkdir();(copy/'notes').write_text('keep')
        with self.assertRaisesRegex(RuntimeError,'Host folders are not supported'):
            files.finish(self.workspace,records)
        files.prepare(self.workspace,[self.write])
        self.assertEqual(copy.read_text(),'original')
        retained=list(copy.parent.glob(copy.name+'.invalid-directory-*'))
        self.assertEqual((retained[0]/'notes').read_text(),'keep')
        self.assertEqual(self.host.read_text(),'original')

    def test_missing_read_rejected_before_policy_inspection(self):
        studio=Studio(self.root/'data',Adapter(),start_worker=False)
        owner=studio.session()[0]['id']
        studio.onboard(owner,{'name':'Files','persona':'guide','skills':['weather'],'protection':'openshell'})
        with patch.object(studio,'policy_report',side_effect=AssertionError('must not inspect')):
            with self.assertRaisesRegex(Problem,'does not exist'):
                studio.policy_change(owner,{'permission':'file:read:'+str(self.root/'missing'),'allow':True})

    def test_host_folder_request_has_no_file_approval_buttons(self):
        studio=Studio(self.root/'data',Adapter(),start_worker=False)
        owner=studio.session()[0]['id']
        studio.onboard(owner,{'name':'Files','persona':'guide','skills':['weather'],'protection':'openshell'})
        path=str(self.root/'new-folder')
        job=studio.enqueue(owner,{'prompt':'Can you creaet folder like this? '+path})
        studio.decision(owner,job['id'],'cancel')
        report=studio.policy_report(owner)
        self.assertEqual(report['unsupportedFolders'],[path])
        self.assertEqual(report['pendingFiles'],[])
        with self.assertRaises(Problem):studio.policy_change(owner,{'permission':'file:write:'+path,'allow':True})
        self.assertEqual(files.requested_directories('read '+str(self.host)),[])
        self.assertEqual(files.requested_directories(path+' 폴더 만들어줘'),[path])

    def test_new_file(self):
        new = self.root/'new.txt'
        records = files.prepare(self.workspace, ['file:write:'+str(new)])
        (self.workspace/records[0]['relative']).write_text('created')
        files.finish(self.workspace, records)
        self.assertEqual(new.read_text(), 'created')

    def test_external_edit_is_not_overwritten(self):
        records = files.prepare(self.workspace, [self.write])
        (self.workspace/records[0]['relative']).write_text('agent')
        self.host.write_text('user')
        with self.assertRaises(RuntimeError):files.finish(self.workspace, records)
        self.assertEqual(self.host.read_text(), 'user')

    def test_links_directories_and_traversal_rejected(self):
        link = self.root/'link';link.symlink_to(self.host)
        for path in [link,self.root]:
            with self.assertRaises(ValueError):files.checked_path(str(path))
        with self.assertRaises(ValueError):files.file_rule('file:read:/tmp/../etc/passwd')
        (self.workspace/'inbox').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):files.prepare(self.workspace,[self.read])

    def test_replaced_copy_symlink_rejected(self):
        records=files.prepare(self.workspace,[self.write]);copy=self.workspace/records[0]['relative']
        copy.unlink();copy.symlink_to(self.host)
        with self.assertRaises(ValueError):files.finish(self.workspace,records)

    def test_file_requests_not_urls(self):
        self.assertEqual(files.requested_files('read `/Users/test/a b.txt` and https://host.com/home/abc'),['/Users/test/a b.txt'])

    def test_file_grants_do_not_broaden_network(self):
        self.assertEqual(policy.policy_document([self.read]),policy.policy_document())
        self.assertEqual(policy.permission_rule(self.read)['access'],'read')

    def test_missing_file_only_offers_write_until_created(self):
        studio=Studio(self.root/'data',Adapter(),start_worker=False)
        owner=studio.session()[0]['id']
        studio.onboard(owner,{'name':'Files','persona':'guide','skills':['weather'],'protection':'openshell'})
        path=self.root/'new.txt'
        job=studio.enqueue(owner,{'prompt':'Create '+str(path)})
        studio.decision(owner,job['id'],'cancel')
        read='file:read:'+str(path);write='file:write:'+str(path)
        self.assertEqual(studio.policy_report(owner)['pendingFiles'],[write])
        path.write_text('created')
        self.assertEqual(studio.policy_report(owner)['pendingFiles'],[read,write])
        studio.policy_change(owner,{'permission':read,'allow':True})
        path.unlink()
        report=studio.policy_report(owner)
        self.assertEqual(report['pendingFiles'],[write])
        self.assertIn(read,report['requested'])  # Saved grants must remain revocable.

    def test_model_suggested_path_requires_matching_user_filename(self):
        path=str(self.host)
        answer='I need permission for `'+path+'` in OpenShell Policy.'
        self.assertEqual(files.proposed_files('read host.txt?',answer),[path])
        self.assertEqual(files.proposed_files('hello',answer),[])
        self.assertEqual(files.proposed_files('read other.txt',answer),[])
        studio=Studio(self.root/'suggestions',Adapter(),start_worker=False)
        owner=studio.session()[0]['id']
        studio.onboard(owner,{'name':'Files','persona':'guide','skills':['weather'],'protection':'openshell'})
        job=studio.enqueue(owner,{'prompt':'read host.txt?'})
        studio.decision(owner,job['id'],'cancel')
        with studio.db() as db:
            db.execute('UPDATE jobs SET result=? WHERE id=?',(json.dumps({'answer':answer}),job['id']))
        report=studio.policy_report(owner)
        self.assertIn(self.read,report['pendingFiles'])
        self.assertTrue(report['catalog'][self.read]['suggested'])
        self.assertNotIn(self.read,report['requested'])
        studio.policy_change(owner,{'permission':self.read,'allow':True})
        self.assertIn(self.read,studio.policy_report(owner)['requested'])

    def test_catalog_candidates_and_approval(self):
        studio=Studio(self.root/'data',Adapter(),start_worker=False)
        account,_=studio.session();owner=account['id']
        studio.onboard(owner,{'name':'Files','persona':'guide','skills':['weather'],'protection':'openshell'})
        job=studio.enqueue(owner,{'prompt':'read '+str(self.host)})
        studio.decision(owner,job['id'],'cancel')
        report=studio.policy_report(owner)
        self.assertIn(self.read,report['pendingFiles']);self.assertIn(self.write,report['pendingFiles'])
        studio.policy_change(owner,{'permission':self.read,'allow':True})
        self.assertNotIn(self.read,studio.policy_report(owner)['pendingFiles'])
        other=studio.add_agent(owner,{'name':'Other','persona':'guide','skills':['weather'],'protection':'openshell'})['agentId']
        self.assertEqual(studio.policy_report(other)['pendingFiles'],[])
        with self.assertRaises(Problem):studio.policy_change(other,{'permission':self.read,'allow':True})

    def test_job_pipeline_exports_only_approved_changes(self):
        adapter=Adapter();studio=Studio(self.root/'pipeline',adapter,start_worker=False)
        account,_=studio.session();owner=account['id']
        studio.onboard(owner,{'name':'Files','persona':'guide','skills':['weather'],'protection':'openshell'})
        seed=studio.enqueue(owner,{'prompt':'Edit '+str(self.host)});studio.decision(owner,seed['id'],'cancel')
        studio.policy_change(owner,{'permission':self.write,'allow':True})
        def respond(agent_id,session,prompt):
            self.assertIn('read/write',prompt)
            copy=studio.workspace(owner)/files.relative_path(str(self.host))
            self.assertEqual(copy.read_text(),'original')
            copy.write_text('pipeline edit')
            return 'Edited the file.'
        with patch.object(adapter,'respond',side_effect=respond):
            job=studio.enqueue(owner,{'prompt':'Now edit it'})
            studio.execute(studio.next_job())
        self.assertEqual(self.host.read_text(),'pipeline edit')
        self.assertEqual(studio.evidence(owner,job['id'])['mission']['status'],'done')

    def test_standard_tools_and_prompt_allow_external_files(self):
        with patch.object(runtime,'root',return_value=self.root/'runtime'),patch.object(runtime,'ensure_openshell'),patch.object(runtime,'cli',return_value='{}'):
            runtime.root().mkdir();runtime.save_config(runtime.initial_config())
            runtime.register('bac-'+'1'*24,self.workspace,{'name':'Files','persona':'guide','skills':['weather'],'protection':'standard'})
            entry=json.loads(runtime.config_path().read_text())['agents']['entries']['bac-'+'1'*24]
            self.assertFalse(entry['tools']['fs']['workspaceOnly'])
            self.assertTrue({'read','write','edit'} <= set(entry['tools']['allow']))
            self.assertIn('external files explicitly requested', (self.workspace/'AGENTS.md').read_text())
            self.assertEqual(entry['sandbox']['mode'],'off')

if __name__=='__main__':unittest.main()
