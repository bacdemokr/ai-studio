"""Retirement of host-file grants leaves websites, uploads and artifacts intact."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).parent)]
from studio import Studio, Problem
from test_studio import Adapter
from agent_policy import permission_rule

class WebsiteOnlyPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.adapter=Adapter()
        self.studio=Studio(self.root/'studio',self.adapter,start_worker=False)
        self.owner=self.studio.session()[0]['id']
        self.studio.onboard(self.owner,dict(name='Files',skills=['writer'],protection='openshell'))

    def test_removed_api_rejects_file_grants_without_native_calls(self):
        for key in ['file:read:/tmp/a','file:write:/tmp/a']:
            with self.assertRaises(ValueError):permission_rule(key)
            for allow in [True,False]:
                with patch.object(self.adapter,'policy_status') as native:
                    with self.assertRaises(Problem):self.studio.policy_change(self.owner,dict(permission=key,allow=allow))
                    native.assert_not_called()

    def test_existing_installs_retire_only_managed_copies_and_preserve_websites(self):
        host=self.root/'original.txt';host.write_text('original')
        workspace=self.studio.workspace(self.owner);inbox=workspace/'inbox'
        names=['approved-'+hashlib.sha256(str(host).encode()).hexdigest()+'.txt',
               'approved-'+'b'*64+'.txt','approved-'+'c'*64+'.txt.invalid-directory-123']
        (inbox/names[0]).write_text('copy');(inbox/names[1]).symlink_to(host)
        (inbox/names[2]).mkdir();(inbox/names[2]/'nested').symlink_to(host)
        upload=inbox/'notes.txt';upload.write_text('uploaded')
        similar=inbox/'approved-not-a-transfer.txt';similar.write_text('keep')
        artifact=workspace/'artifacts'/'result.txt';artifact.write_text('result')
        keys=['weather','file:read:'+str(host),'file:write:'+str(host)]
        with self.studio.db() as db:
            db.execute("DELETE FROM metadata WHERE key='host-file-grants-retired'")
            db.execute('INSERT INTO agent_policies(owner,approved) VALUES(?,?)',(self.owner,json.dumps(keys)))
            db.execute('INSERT INTO agent_policies(owner,role,approved) VALUES(?,1,?)',(self.owner,json.dumps(['host:blogs.nvidia.com','file:read:'+str(host)])))
        migrated=Studio(self.root/'studio',self.adapter,start_worker=False)
        self.assertEqual(migrated.saved_policy(self.owner)[1],['weather'])
        self.assertEqual(migrated.saved_policy(self.owner,1)[1],['host:blogs.nvidia.com'])
        self.assertTrue(all(not (inbox/name).exists() and not (inbox/name).is_symlink() for name in names))
        self.assertEqual([p.read_text() for p in (host,upload,similar,artifact)],['original','uploaded','keep','result'])
        migrated.retire_host_file_grants()
        self.assertEqual(upload.read_text(),'uploaded')
        self.assertNotIn('pendingFiles',migrated.policy_report(self.owner))
        self.assertNotIn('per-file grants',(workspace/'AGENTS.md').read_text())

    def test_path_request_reaches_model_without_host_inspection_or_writeback(self):
        host=self.root/'private.txt';host.write_text('private contents')
        upload=self.studio.workspace(self.owner)/'inbox'/'notes.txt';upload.write_text('uploaded')
        job=self.studio.enqueue(self.owner,dict(prompt='Read '+str(host)))
        def respond(agent,session,prompt):
            self.assertIn('User request:\nRead '+str(host),prompt)
            self.assertIn('ask the user to upload',prompt)
            self.assertNotIn('private contents',prompt)
            self.assertNotIn('Host-path metadata hints',prompt)
            (self.studio.workspace(self.owner)/'artifacts'/'draft.txt').write_text('result')
            return 'Please upload the file so I can read it.'
        with patch.object(self.adapter,'respond',side_effect=respond):self.studio.execute(self.studio.next_job())
        mission=self.studio.evidence(self.owner,job['id'])['mission']
        self.assertEqual(mission['status'],'done')
        self.assertIn('artifacts/draft.txt',mission['result']['files'])
        self.assertEqual(host.read_text(),'private contents')
        self.assertEqual(upload.read_text(),'uploaded')
        self.assertEqual(self.studio.protection_activity.snapshot({self.owner},self.owner),[])
