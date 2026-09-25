from native_config_fixture import offline_config
import json, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import agent_runtime as runtime
import agent_policy as policy

class DemoSkillsTests(unittest.TestCase):
    @offline_config
    def test_equipped_skills_are_native_files_with_matching_tool_access(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'BAC_DATA_DIR':tmp}):
            runtime.save_config(runtime.initial_config())
            for skill in ('web','weather','documents','builder','writer','memory'):
                workspace=Path(tmp)/skill
                runtime.register('test-'+skill,workspace,{'name':'Test','persona':'guide','skills':[skill]})
                entry=json.loads(runtime.config_path().read_text())['agents']['entries']['test-'+skill]
                self.assertEqual(entry['skills'],['bac-'+skill])
                self.assertTrue((workspace/'skills'/('bac-'+skill)/'SKILL.md').exists())
                self.assertEqual('web_fetch' in entry['tools']['allow'],skill in ('web','weather','documents'))
                self.assertIn('write',entry['tools']['allow'])
                self.assertIn('edit',entry['tools']['allow'])
            self.assertIn('sortBy=submittedDate', (Path(tmp)/'web/skills/bac-web/SKILL.md').read_text())

    @offline_config
    def test_papers_stay_inside_protected_transport_and_require_separate_approval(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'BAC_DATA_DIR':tmp}), patch.object(policy,'configured',return_value=True):
            runtime.save_config(runtime.initial_config())
            runtime.register('test-protected',Path(tmp)/'agent',{'name':'Test','persona':'guide','skills':['web'],'protection':'openshell'})
            content=(Path(tmp)/'agent/skills/bac-web/SKILL.md').read_text()
            self.assertIn('export.arxiv.org',content);self.assertIn('host=sandbox',content)
            self.assertIn('paper discovery',content)
            entry=json.loads(runtime.config_path().read_text())['agents']['entries']['test-protected']
            self.assertNotIn('write',entry['tools']['allow'])
            runtime.register('test-page',Path(tmp)/'page',{'name':'Page','persona':'guide','skills':['nvidia-webpage'],'protection':'openshell'})
            page_entry=json.loads(runtime.config_path().read_text())['agents']['entries']['test-page']
            self.assertIn('write',page_entry['tools']['allow']);self.assertIn('edit',page_entry['tools']['allow'])
            self.assertEqual(policy.policy_document()['network_policies'],{})
            rules=policy.policy_document(['papers'])['network_policies']
            self.assertEqual(set(rules),{'bac_papers'})
            self.assertEqual({e['host'] for e in rules['bac_papers']['endpoints']},{'arxiv.org','export.arxiv.org'})
