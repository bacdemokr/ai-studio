"""A lost native registry must not hide agent-owned OpenShell resources."""
import json
import sys
import tempfile
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import agent_policy as policy
import agent_runtime as runtime
from owned_openshell import creation_args


class SandboxOwnershipTests(unittest.TestCase):
    agent = 'bac-'+'a'*24

    def test_label_inventory_is_owner_scoped_and_failure_is_not_absence(self):
        with patch.object(policy, 'plugin_config', return_value={'config': {'gateway': 'test'}}), patch.object(policy, 'shell', return_value='oc-owned\n') as shell:
            self.assertEqual(policy.owned_sandbox_names(self.agent), {'oc-owned'})
            self.assertIn('bac-agent-id='+self.agent, shell.call_args.args)
            shell.side_effect = RuntimeError('unavailable')
            with self.assertRaises(RuntimeError):policy.owned_sandbox_names(self.agent)
            shell.reset_mock()
            with self.assertRaises(RuntimeError):policy.owned_sandbox_names('bac-host')
            shell.assert_not_called()

    def test_lost_registry_still_deletes_labeled_sandbox_only(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runtime, 'root', return_value=Path(directory)/'native'):
            workspace=Path(directory)/'workspace';workspace.mkdir()
            config=runtime.initial_config();config['agents']['entries'][self.agent]={'workspace':str(workspace)}
            runtime.save_config(config)
            with patch.object(runtime,'quiesce_native'), patch.object(runtime,'delete_native',return_value=json.dumps({'agentId':self.agent,'failed':[]})), patch.object(policy,'runtimes',return_value=[]), patch.object(policy,'owned_sandbox_names',return_value={'oc-owned'}), patch.object(policy,'sandbox_names',side_effect=[{'oc-owned','oc-other'},{'oc-other'}]), patch.object(policy,'shell') as shell, patch.object(policy,'sandbox_registry'):
                runtime.remove(self.agent,workspace)
                shell.assert_called_once_with('sandbox','delete','oc-owned')

    def test_late_sandbox_prevents_success_and_preserves_cleanup_receipt(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runtime,'root',return_value=Path(directory)):
            runtime.save_config(runtime.initial_config())
            with patch.object(policy,'owned_sandbox_names',return_value={'oc-late'}), patch('deletion_residue.purge') as purge, patch.object(runtime.subprocess,'run') as command:
                with self.assertRaises(runtime.NativeCleanupPending):runtime.finalize_removal(self.agent,Path(directory)/'absent')
                purge.assert_not_called();command.assert_not_called()

    def test_labeled_orphan_cannot_take_the_unused_workspace_shortcut(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory, patch.object(runtime,'root',return_value=Path(directory)):
            runtime.save_config(runtime.initial_config())
            result=subprocess.CompletedProcess([],0,json.dumps({'unregistered':[self.agent]}),'')
            with patch.object(runtime.subprocess,'run',return_value=result), patch.object(policy,'owned_sandbox_names',return_value={'oc-orphan'}):
                self.assertEqual(runtime.unregistered_deletion_targets([(self.agent,Path(directory)/'absent')]),set())

    def test_creation_labels_survive_registry_loss_and_cannot_follow_deletion(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);workspace=root/'workspaces'/'agent';workspace.mkdir(parents=True)
            database=root/'studio.sqlite'
            with sqlite3.connect(database) as db:
                db.execute('CREATE TABLE agents(id TEXT PRIMARY KEY,deleting INTEGER,kind TEXT,profile TEXT)')
                db.execute('CREATE TABLE crew_resources(owner TEXT,native_id TEXT UNIQUE)')
                db.execute('INSERT INTO agents VALUES (?,0,?,?)',(self.agent[4:],'personal',json.dumps({'id':self.agent})))
            config={'agents':{'entries':{self.agent:{'workspace':str(workspace)}}}}
            args=['--gateway','demo','sandbox','create','--name','oc-owned','--','sleep','infinity']
            result=creation_args(args,self.agent,config,database)
            self.assertEqual(result[result.index('--label')+1],'bac-agent-id='+self.agent)
            self.assertLess(result.index('--label'),result.index('--'))
            self.assertEqual(result[-3:],['--','sleep','infinity'])
            with sqlite3.connect(database) as db:db.execute('UPDATE agents SET deleting=2')
            with self.assertRaisesRegex(RuntimeError,'deletion'):creation_args(args,self.agent,config,database)
            with self.assertRaisesRegex(RuntimeError,'owner'):creation_args(args,self.agent,{'agents':{'entries':{}}},database)
            self.assertEqual(creation_args(['sandbox','delete','oc-owned'],self.agent,config,database),['sandbox','delete','oc-owned'])


    def test_preserved_crew_uses_recorded_owner_and_never_native_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            database=Path(directory)/'studio.sqlite'
            native=self.agent+'-r1'
            owner='b'*24
            config={'agents':{'entries':{native:{}}}}
            args=['sandbox','create','--name','oc-crew']
            with sqlite3.connect(database) as db:
                db.execute('CREATE TABLE agents(id TEXT PRIMARY KEY,deleting INTEGER,kind TEXT,profile TEXT)')
                db.execute('CREATE TABLE crew_resources(owner TEXT,native_id TEXT UNIQUE)')
                db.execute('INSERT INTO agents VALUES (?,0,?,NULL)',(owner,'crew'))
                db.execute('INSERT INTO crew_resources VALUES (?,?)',(owner,native))
            self.assertIn('bac-agent-id='+native,creation_args(args,native,config,database))
            # A live personal agent matching the old prefix cannot rescue a
            # deleting crew, nor acquire a role with a missing ownership record.
            with sqlite3.connect(database) as db:
                db.execute('INSERT INTO agents VALUES (?,0,?,?)',(self.agent[4:],'personal',json.dumps({'id':self.agent})))
                db.execute('UPDATE agents SET deleting=1 WHERE id=?',(owner,))
            with self.assertRaisesRegex(RuntimeError,'deletion'):creation_args(args,native,config,database)
            with sqlite3.connect(database) as db:db.execute('DELETE FROM agents WHERE id=?',(owner,))
            with self.assertRaisesRegex(RuntimeError,'owner'):creation_args(args,native,config,database)
            with sqlite3.connect(database) as db:
                db.execute('INSERT INTO agents VALUES (?,0,?,NULL)',(owner,'personal'))
            with self.assertRaisesRegex(RuntimeError,'owner'):creation_args(args,native,config,database)
            with sqlite3.connect(database) as db:db.execute('DELETE FROM crew_resources')
            with self.assertRaisesRegex(RuntimeError,'owner'):creation_args(args,native,config,database)

    def test_personal_owner_requires_saved_profile_and_active_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            database=Path(directory)/'studio.sqlite'
            config={'agents':{'entries':{self.agent:{}}}}
            args=['sandbox','create']
            with sqlite3.connect(database) as db:
                db.execute('CREATE TABLE agents(id TEXT PRIMARY KEY,deleting INTEGER,kind TEXT,profile TEXT)')
                db.execute('CREATE TABLE crew_resources(owner TEXT,native_id TEXT UNIQUE)')
                db.execute('INSERT INTO agents VALUES (?,0,?,NULL)',(self.agent[4:],'personal'))
            for kind,profile in [('personal',None),('personal',json.dumps({'id':'bac-'+'b'*24})),('crew',json.dumps({'id':self.agent}))]:
                with self.subTest(kind=kind,profile=profile):
                    with sqlite3.connect(database) as db:db.execute('UPDATE agents SET kind=?,profile=?',(kind,profile))
                    with self.assertRaisesRegex(RuntimeError,'owner'):creation_args(args,self.agent,config,database)
            with sqlite3.connect(database) as db:db.execute('DELETE FROM agents')
            with self.assertRaisesRegex(RuntimeError,'owner'):creation_args(args,self.agent,config,database)


if __name__ == '__main__':unittest.main()
