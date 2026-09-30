import unittest
import test_collaboration_plan as fixture

class ResetArtifactsTests(unittest.TestCase):
    setUp=fixture.CollaborationTests.setUp
    def file(self,owner,role=None,category='artifacts',name='keep.txt'):
        path=self.app.workspace(owner,role)/category/name
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text('saved')
        return path
    def test_reset_clears_team_outputs_preserves_uploads_personal_and_other_accounts(self):
        team=self.app.crew_owner(self.owner)
        other=self.app.crew_owner(self.app.session()[0]['id'])
        removed=[self.file(team),self.file(team,5),self.file(team,8,name='nested/brief.md')]
        kept=[self.file(team,0,'inbox'),self.file(team,5,'inbox'),self.file(self.owner),self.file(other,5)]
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
        self.app.enqueue(team,{'kind':'crew-chat','crewRole':5,'prompt':'Work'})
        row=self.app.next_job()
        self.assertTrue(self.app.reset_crew_chats(self.owner,reset_event=True)['resetting'])
        self.assertTrue(saved.exists())
        with self.app.db() as db:db.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(row['id'],))
        self.app.finish_pending_bac_resets()
        self.assertFalse(saved.exists())
