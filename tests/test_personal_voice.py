import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parent)]
import agent_runtime as runtime
from personal_voice import signature, contract, PRESET_UPDATES
from crew_roundtable import reaction_prompt
from test_studio import Studio, Adapter


class PersonalVoiceTests(unittest.TestCase):
    def test_signature_is_shared_by_workspace_chat_and_roundtable(self):
        with tempfile.TemporaryDirectory() as temp:
            profile={'name':'Echo','persona':'analyst','tone':'cynical','tonePrompt':'Dry and skeptical.', 'skills':['documents']}
            workspace=Path(temp)/'workspace'
            runtime.write_workspace(workspace,profile)
            self.assertIn(signature(profile),(workspace/'SOUL.md').read_text())
            self.assertIn('EVERY conversational answer',(workspace/'skills/bac-documents/SKILL.md').read_text())
            prompt=reaction_prompt(profile,'English','{}')
            self.assertIn(signature(profile),prompt)
            self.assertIn('Dry and skeptical.',prompt)
            self.assertNotIn('1–2 short sentences',prompt)
            self.assertNotIn('no JSON, headings',prompt)
            runtime.write_workspace(workspace,profile,'Research & demo planner')
            self.assertNotIn('# Signature replies',(workspace/'SOUL.md').read_text())

    def test_both_skills_have_one_unambiguous_outer_format(self):
        rules=signature({'skills':['writer','documents']})
        self.assertIn('COMBINED FORMAT: exactly 1., 2., 3.',rules)
        self.assertIn('No separate headline',rules)
        self.assertIn('never invent',contract({'skills':['writer'],'tone':'cynical'}))

    def test_existing_presets_update_custom_roles_and_memory_survive(self):
        with tempfile.TemporaryDirectory() as temp:
            studio=Studio(temp,Adapter(),start_worker=False)
            person=studio.session()[0];owner=person['id']
            old=list(PRESET_UPDATES)[1]
            studio.onboard(owner,{'name':'Announcer','purpose':old,'skills':['writer']})
            custom=studio.add_agent(owner,{'name':'Custom','purpose':'Poetry with a dry wink.','skills':['writer']})['agentId']
            (studio.workspace(owner)/'MEMORY.md').write_text('Keep my preference.')
            restarted=Studio(temp,Adapter(),start_worker=False)
            self.assertEqual(restarted.profile(owner)['purpose'],PRESET_UPDATES[old])
            self.assertEqual(restarted.profile(custom)['purpose'],'Poetry with a dry wink.')
            self.assertEqual((studio.workspace(owner)/'MEMORY.md').read_text(),'Keep my preference.')
            self.assertIn('emoji-led headline',(studio.workspace(owner)/'SOUL.md').read_text())
            self.assertIn('Poetry with a dry wink.',(studio.workspace(custom)/'SOUL.md').read_text())

    def test_off_topic_personal_request_carries_role_tone_and_format(self):
        class Capture(Adapter):
            def respond(self,agent,session,prompt):
                self.prompt=prompt
                return '📣 Sky update\nBlue light scatters more.'
        with tempfile.TemporaryDirectory() as temp:
            adapter=Capture();studio=Studio(temp,adapter,start_worker=False)
            owner=studio.session()[0]['id']
            profile=studio.onboard(owner,{'name':'Announcer','purpose':'Write announcements.','tone':'cynical','skills':['writer']})
            job=studio.enqueue(owner,{'prompt':'Why is the sky blue?'})
            with studio.db() as db:row=db.execute('SELECT * FROM jobs WHERE id=?',(job['id'],)).fetchone()
            studio.execute(row)
            self.assertIn('Why is the sky blue?',adapter.prompt)
            self.assertIn('Chosen tone: cynical',adapter.prompt)
            self.assertIn(signature(profile),adapter.prompt)
            self.assertIn('not a reason to refuse',adapter.prompt)


if __name__=='__main__':unittest.main()
