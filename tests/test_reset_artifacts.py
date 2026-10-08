import unittest
import test_collaboration_plan as fixture

class ResetArtifactsTests(unittest.TestCase):
    setUp=fixture.CollaborationTests.setUp
    def file(self,owner,role=None,category='artifacts',name='keep.txt'):
        path=self.app.workspace(owner,role)/category/name
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text('saved')
        return path
    def test_reset_clears_team_outputs_and_uploads_preserves_personal_and_other_accounts(self):
        team=self.app.crew_owner(self.owner)
        other=self.app.crew_owner(self.app.session()[0]['id'])
        removed=[self.file(team),self.file(team,5),self.file(team,8,name='nested/brief.md'),self.file(team,0,'inbox',name='notes.pdf'),self.file(team,0,'inbox',name='notes.pdf.txt'),self.file(team,5,'inbox')]
        kept=[self.file(self.owner,category='inbox'),self.file(self.owner),self.file(other,5),self.file(other,0,'inbox')]
        self.app.reset_crew_chats(self.owner,reset_event=True)
        for path in removed:self.assertFalse(path.exists())
        for path in kept:self.assertTrue(path.exists())
        self.assertTrue((self.app.workspace(team,5)/'artifacts').is_dir())
        self.app.reset_crew_chats(self.owner,reset_event=True)
    def test_artifact_symlink_does_not_delete_target(self):
        team=self.app.crew_owner(self.owner)
        keep=self.file(self.owner)
        directory=self.app.workspace(team,5);directory.mkdir(parents=True,exist_ok=True)
        (directory/'artifacts').rmdir()
        (directory/'artifacts').symlink_to(keep.parent,target_is_directory=True)
        self.app.reset_crew_chats(self.owner,reset_event=True)
        self.assertTrue(keep.exists())
        self.assertFalse((directory/'artifacts').is_symlink())
    def test_pending_work_delays_artifact_deletion(self):
        team=self.app.crew_owner(self.owner)
        saved=self.file(team,5)
        attached=self.file(team,0,'inbox')
        self.app.enqueue(team,{'kind':'crew-chat','crewRole':5,'prompt':'Work'})
        row=self.app.next_job()
        self.assertTrue(self.app.reset_crew_chats(self.owner,reset_event=True)['resetting'])
        self.assertTrue(saved.exists())
        self.assertTrue(attached.exists())
        with self.app.db() as db:db.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(row['id'],))
        self.app.finish_pending_bac_resets()
        self.assertFalse(saved.exists())
        self.assertFalse(attached.exists())

    def test_reset_clears_attachment_list_and_upload_symlink_without_following_it(self):
        team=self.app.crew_owner(self.owner)
        self.app.upload(self.owner,{'crewRole':0,'name':'notes.md','content':'Attached notes'})
        self.assertTrue(self.app.state(self.owner)['crewDocuments'])
        kept=self.file(self.owner,category='inbox')
        link=self.app.workspace(team,0)/'inbox'/'external'
        link.symlink_to(kept.parent,target_is_directory=True)
        self.app.reset_crew_chats(self.owner,reset_event=True)
        self.assertEqual(self.app.state(self.owner)['crewDocuments'],[])
        self.assertTrue(kept.exists())
        self.assertFalse(link.exists())

    def test_directory_removed_mid_listing_does_not_break_state(self):
        from unittest.mock import patch
        from pathlib import Path
        original=Path.rglob
        def disappear(folder, pattern):
            if folder.name=='artifacts':
                def scan():
                    raise FileNotFoundError('reset removed the directory during iteration')
                    yield
                return scan()
            return original(folder,pattern)
        self.file(self.owner,category='inbox',name='keep.txt')
        with patch.object(Path,'rglob',disappear):
            files=self.app.files(self.owner,recursive=True)
        self.assertEqual([f['path'] for f in files],['inbox/keep.txt'])
