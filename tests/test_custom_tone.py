import sys, tempfile, unittest, os
from pathlib import Path
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parent)]
from studio import Studio, Problem
from test_studio import Adapter
import agent_runtime as runtime
class CustomToneTests(unittest.TestCase):
    def test_custom_tone_persists_and_reaches_native_soul(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'BAC_DATA_DIR':tmp}):
            studio=Studio(Path(tmp)/'studio',Adapter(),start_worker=False)
            account,_=studio.session(); owner=account['id']
            profile=studio.onboard(owner,{'name':'Echo','persona':'guide','skills':['writer'],'purpose':'Write short invitations.','tone':'kind','tonePrompt':'Dry humor, curious, no flattery.'})
            runtime.save_config(runtime.initial_config())
            workspace=Path(tmp)/'native'
            runtime.register(profile['id'],workspace,profile)
            soul=(workspace/'SOUL.md').read_text()
            self.assertIn('# Tone\nDry humor, curious, no flattery.',soul)
            self.assertIn('Write short invitations.',soul)
            studio.configure(owner,{'name':'Echo','persona':'guide','skills':['writer']})
            self.assertEqual(studio.profile(owner)['tonePrompt'],profile['tonePrompt'])
            with self.assertRaises(Problem):
                studio.configure(owner,{'name':'Echo','persona':'guide','skills':['writer'],'tonePrompt':'x'*801})

    def test_literal_tone_and_role_are_not_expanded(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'BAC_DATA_DIR':tmp}):
            runtime.save_config(runtime.initial_config())
            for tone in ['Cynical', 'Cynical (Dry humor & skepticism)', 'Quiet.\nAsk one question at a time.', '']:
                profile={'name':'Echo','persona':'guide','skills':['writer'],'purpose':'Write invitations.\nKeep dates explicit.','tone':'cynical','tonePrompt':tone}
                workspace=Path(tmp)/'native'
                runtime.register('literal-agent',workspace,profile)
                soul=(workspace/'SOUL.md').read_text()
                self.assertEqual(soul.split('\n\n# Shared boundaries')[0], '# Tone\n'+tone+'\n\n# Role\n'+profile['purpose'])
                self.assertNotIn('spreadsheet',soul)
                self.assertIn('# Requests outside your role',soul)
                self.assertIn('then help with the actual request',soul)
                self.assertIn('not on every reply',soul)
                self.assertIn('within your actual skills and permissions',soul)
                self.assertNotIn('# Answer length',soul)

    def test_skill_gap_tracks_actual_equipped_tools(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'BAC_DATA_DIR':tmp}):
            runtime.save_config(runtime.initial_config())
            profile={'name':'Echo','persona':'guide','skills':['writer'],'purpose':'Polish short notes.','tone':'cynical'}
            workspace=Path(tmp)/'native'
            runtime.register('skill-gap',workspace,profile)
            import json
            def tools():
                return json.loads(runtime.config_path().read_text())['agents']['entries']['skill-gap']['tools']['allow']
            self.assertNotIn('web_fetch',tools())
            soul=(workspace/'SOUL.md').read_text()
            self.assertIn('Name the missing capability',soul)
            self.assertIn('Do not invent live weather',soul)
            self.assertIn('state the actual cause',soul)
            runtime.register('skill-gap',workspace,{**profile,'skills':['writer','weather']})
            self.assertIn('web_fetch',tools())
            self.assertIn(runtime.SKILLS['weather'][0],(workspace/'SOUL.md').read_text())
