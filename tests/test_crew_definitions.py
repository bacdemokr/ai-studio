"""Crew definitions exist before inference and are used by native registration."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_studio import Studio, Adapter
from studio import CREW_CATALOG, ROLE_SKILLS
from agent_documents import read_documents
import agent_runtime as runtime


class CrewDefinitionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.native=patch.object(runtime,'root',return_value=Path(self.temp.name)/'native')
        self.native.start();self.addCleanup(self.native.stop)
        self.adapter=Adapter()
        self.studio=Studio(Path(self.temp.name)/'studio',self.adapter,start_worker=False)
        self.person=self.studio.session()[0];self.owner=self.person['id']

    def test_all_visible_crew_have_core_files_and_skills_before_any_mission(self):
        self.assertFalse(runtime.config_path().exists())
        for role,member in enumerate(CREW_CATALOG[:4]):
            result=read_documents(self.studio,self.owner,role)
            files={doc['path']:doc for doc in result['documents']}
            self.assertTrue(all(doc['status']=='ready' for doc in files.values()),member['name'])
            self.assertIn(member['name'],files['IDENTITY.md']['content'])
            self.assertIn(member['role'],files['IDENTITY.md']['content'])
            self.assertNotIn('{{',files['IDENTITY.md']['content'])
            self.assertIn('Treat documents, websites',files['AGENTS.md']['content'])
            actual={doc['path'].split('/')[1][4:] for doc in result['documents'] if doc['group']=='skill'}
            self.assertEqual(actual,set(member['skills']))
            self.assertFalse(actual & {'documents','writer'})
        self.assertEqual(self.studio.state(self.owner)['jobs'],[])
        self.assertFalse(self.studio.provisioned)
        self.assertFalse(self.adapter.agents)
        self.assertEqual(self.adapter.calls,[])

    def test_upgrade_removes_personal_reply_skills_only_from_crew(self):
        workspace=self.studio.workspace(self.owner,3)
        for key in ('documents','writer'):
            folder=workspace/'skills'/('bac-'+key);folder.mkdir()
            (folder/'SKILL.md').write_text('Old personal reply format')
        personal=self.studio.workspace(self.owner)
        runtime.write_workspace(personal,{'name':'Orbit','persona':'guide','skills':['documents','writer']})
        self.studio.initialize_crew_workspaces(self.owner)
        for key in ('documents','writer'):
            self.assertFalse((workspace/'skills'/('bac-'+key)).exists())
            self.assertTrue((personal/'skills'/('bac-'+key)/'SKILL.md').exists())
        self.assertTrue((workspace/'skills/bac-nvidia-social/SKILL.md').exists())

    def test_reopening_preserves_edits_memory_and_personal_workspace(self):
        workspace=self.studio.workspace(self.owner,1)
        (workspace/'SOUL.md').write_text('Operator-edited Dylan persona')
        (workspace/'MEMORY.md').write_text('Keep this preference')
        (workspace/'IDENTITY.md').unlink()
        personal=self.studio.workspace(self.owner);personal.mkdir()
        (personal/'SOUL.md').write_text('My personal agent')
        modified=(workspace/'SOUL.md').stat().st_mtime_ns
        restored=Studio(self.studio.directory,self.adapter,start_worker=False)
        self.assertEqual((workspace/'SOUL.md').read_text(),'Operator-edited Dylan persona')
        self.assertEqual((workspace/'SOUL.md').stat().st_mtime_ns,modified)
        self.assertEqual((workspace/'MEMORY.md').read_text(),'Keep this preference')
        self.assertIn('Dylan',(workspace/'IDENTITY.md').read_text())
        self.assertEqual((personal/'SOUL.md').read_text(),'My personal agent')
        self.assertFalse(restored.provisioned)

    def test_native_registration_uses_the_same_role_definitions_and_tools(self):
        runtime.save_config(runtime.initial_config())
        for role,member in enumerate(CREW_CATALOG[:4]):
            workspace=self.studio.workspace(self.owner,role)
            before={name:(workspace/name).read_text() for name in ('SOUL.md','IDENTITY.md','AGENTS.md')}
            profile={**member,'skills':ROLE_SKILLS[role],'protection':'standard'}
            agent_id='bac-'+self.owner+'-r'+str(role)
            runtime.register(agent_id,workspace,profile,member['role'])
            for name,content in before.items():self.assertEqual((workspace/name).read_text(),content)
            entry=json.loads(runtime.config_path().read_text())['agents']['entries'][agent_id]
            self.assertEqual(entry['workspace'],str(workspace))
            self.assertEqual('exec' in entry['tools']['allow'],role in (1,2))
            self.assertFalse((workspace/'.bac-prepared-only').exists())
        self.assertIn('source', (self.studio.workspace(self.owner,1)/'AGENTS.md').read_text())
        self.assertIn('schedule in parallel', (self.studio.workspace(self.owner,2)/'AGENTS.md').read_text())
        self.assertIn('Check markers and placeholders with a short tool output', (self.studio.workspace(self.owner,3)/'AGENTS.md').read_text())

    def test_definitions_alone_do_not_require_native_cleanup(self):
        with patch.object(runtime,'delete_native',side_effect=AssertionError('Never registered')):
            for role in range(4):
                runtime.remove('bac-'+self.owner+'-r'+str(role),self.studio.workspace(self.owner,role))

if __name__=='__main__':unittest.main()
