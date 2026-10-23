"""Scoped Markdown edits persist, invalidate runtime caches and reject stale writes."""
import json
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

import test_agent_documents as fixtures
from test_studio import Studio, Adapter
from native_config_fixture import offline_config
from agent_documents import read_documents, save_documents, MAX_BYTES
from document_edits import MARKER
from serve import create_server
from studio import Problem


class AgentDocumentEditsTests(unittest.TestCase):
    setUp = fixtures.AgentDocumentsTests.setUp
    save = fixtures.AgentDocumentsTests.save

    def change(self, path, content, owner=None, role=None):
        doc = next(d for d in read_documents(self.studio, owner or self.owner, role)['documents'] if d['path'] == path)
        return {'path': path, 'content': content, 'revision': doc['revision']}

    @offline_config
    def test_all_visible_files_survive_profile_edits_and_restart(self):
        self.save('TOOLS.md', '# Tools\n')
        self.save('HEARTBEAT.md', '# A custom periodic note\n')
        documents = read_documents(self.studio, self.owner)['documents']
        changes = [self.change(d['path'], '# User edit\n'+d['path']+'\n한글 <script>literal</script>\n') for d in documents]
        profile = self.studio.profile(self.owner)
        self.studio.provisioned.add(profile['id'])
        result = save_documents(self.studio, self.owner, {'documents': changes})
        self.assertNotIn(profile['id'], self.studio.provisioned)
        expected = {change['path']: change['content'] for change in changes}
        self.assertEqual({d['path']: d['content'] for d in result['documents']}, expected)
        self.studio.configure(self.owner, {**profile, 'tone': 'direct', 'model': profile['model']})
        restarted = Studio(self.temp.name, Adapter(), start_worker=False)
        self.assertEqual({d['path']: d['content'] for d in read_documents(restarted, self.owner)['documents']}, expected)
        from personal_voice import contract
        self.assertIn('Read them before responding', contract(restarted.profile(self.owner)))
        self.assertIn('skills/bac-documents/SKILL.md', contract(restarted.profile(self.owner)))

    def test_missing_memory_can_be_created_and_empty_file_is_preserved(self):
        target = self.studio.workspace(self.owner) / 'MEMORY.md'; target.unlink()
        change = self.change('MEMORY.md', '')
        self.assertEqual(change['revision'], 'missing')
        save_documents(self.studio, self.owner, {'documents': [change]})
        self.assertEqual(target.read_text(), '')
        self.assertEqual(read_documents(self.studio, self.owner)['documents'][4]['status'], 'ready')

    @offline_config
    def test_each_edited_file_updates_native_registration_without_new_permissions(self):
        import agent_runtime as runtime
        from personal_voice import signature, contract
        workspace = self.studio.workspace(self.owner)
        self.save('TOOLS.md', '# Tool notes\n')
        self.save('HEARTBEAT.md', '# Custom note\n')
        with patch.object(runtime, 'root', return_value=Path(self.temp.name)/'native'):
            runtime.save_config(runtime.initial_config())
            profile = self.studio.profile(self.owner)
            def registration():
                runtime.register(profile['id'], workspace, self.studio.profile(self.owner))
                return json.loads(runtime.config_path().read_text())['agents']['entries'][profile['id']]
            before = registration()
            for doc in read_documents(self.studio, self.owner)['documents']:
                content = doc['content']+'\nA user instruction for '+doc['path']+'\n'
                save_documents(self.studio, self.owner, {'documents':[self.change(doc['path'],content)]})
                after = registration()
                self.assertNotEqual(before['identity']['theme'], after['identity']['theme'], doc['path'])
                self.assertEqual(before['tools'], after['tools'])
                self.assertEqual(before['skills'], after['skills'])
                self.assertEqual((workspace/doc['path']).read_text(), content)
                before = after
            edited = self.studio.profile(self.owner)
            self.assertEqual(signature(edited), '')
            self.assertNotIn('Chosen tone:', contract(edited))

    def test_stale_batch_does_not_overwrite_any_file(self):
        a = self.change('SOUL.md', 'new soul'); b = self.change('MEMORY.md', 'new memory')
        before = (self.studio.workspace(self.owner) / 'SOUL.md').read_text()
        self.save('MEMORY.md', 'A newer agent memory')
        with self.assertRaises(Problem) as error:
            save_documents(self.studio, self.owner, {'documents': [a, b]})
        self.assertEqual(error.exception.status, 409)
        self.assertEqual((self.studio.workspace(self.owner) / 'SOUL.md').read_text(), before)
        self.assertEqual((self.studio.workspace(self.owner) / 'MEMORY.md').read_text(), 'A newer agent memory')

    def test_paths_payload_and_linked_files_are_rejected(self):
        for path in ('../SOUL.md', '/tmp/SOUL.md', 'openclaw.json', MARKER, 'skills/bac-weather/SKILL.md', 'artifacts/custom.md'):
            with self.subTest(path=path), self.assertRaises(Problem):
                save_documents(self.studio, self.owner, {'documents': [{'path':path, 'revision':'missing', 'content':'bad'}]})
        for content in ('x'*(MAX_BYTES+1), '\x00', None):
            with self.subTest(content_type=type(content).__name__), self.assertRaises(Problem):
                save_documents(self.studio, self.owner, {'documents': [self.change('SOUL.md', content)]})
        outside = Path(self.temp.name) / 'outside.md'; outside.write_text('outside')
        target = self.studio.workspace(self.owner) / 'SOUL.md'; target.unlink(); target.symlink_to(outside)
        with self.assertRaises(Problem):
            save_documents(self.studio, self.owner, {'documents': [{'path':'SOUL.md','revision':'missing','content':'no'}]})
        self.assertEqual(outside.read_text(), 'outside')

    def test_busy_agent_and_active_team_cannot_be_edited(self):
        change = self.change('SOUL.md', 'not now')
        self.studio.executing_owners.add(self.owner)
        with self.assertRaises(Problem) as error:save_documents(self.studio, self.owner, {'documents':[change]})
        self.assertEqual(error.exception.status, 409)
        self.studio.executing_owners.clear()
        team = self.studio.crew_owner(self.owner)
        self.studio.executing_owners.add(team)
        with self.assertRaises(Problem) as error:
            save_documents(self.studio, team, {'documents':[self.change('SOUL.md','busy',team,0)]}, 0)
        self.assertEqual(error.exception.status, 409)

    def test_failed_write_restores_original_files_and_metadata(self):
        changes = [self.change('SOUL.md','new soul'), self.change('MEMORY.md','new memory')]
        before = {d['path']: d.get('content') for d in read_documents(self.studio,self.owner)['documents']}
        from document_edits import atomic_write
        failed = False
        def fail_once(path, content):
            nonlocal failed
            if Path(path).name == 'MEMORY.md' and not failed:
                failed = True; raise OSError('Fixture write failure')
            atomic_write(path, content)
        with patch('document_edits.atomic_write', side_effect=fail_once), self.assertRaises(OSError):
            save_documents(self.studio,self.owner,{'documents':changes})
        self.assertEqual({d['path']:d.get('content') for d in read_documents(self.studio,self.owner)['documents']},before)
        self.assertFalse((self.studio.workspace(self.owner)/MARKER).exists())

    def test_http_writes_require_csrf_and_preserve_account_and_crew_scope(self):
        other = self.studio.session()[0]['id'];self.studio.onboard(other,{'name':'Private','skills':[]})
        team = self.studio.crew_owner(self.owner)
        server = create_server('127.0.0.1',0,self.studio)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        url = 'http://127.0.0.1:'+str(server.server_port)+'/api/agent-documents'
        def post(body, owner=None, csrf=None):
            headers={'Cookie':'bac_session='+self.person['token'],'X-BaC-Agent':owner or self.owner,'X-BaC-CSRF':self.person['csrf'] if csrf is None else csrf,'Content-Type':'application/json'}
            return json.load(urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(body).encode(),headers=headers),timeout=5))
        change = self.change('SOUL.md', 'Private draft')
        for kwargs, code in [({'csrf':''},403),({'owner':other},404)]:
            with self.assertRaises(urllib.error.HTTPError) as error:post({'documents':[change]},**kwargs)
            self.assertEqual(error.exception.code,code)
        for role in (True,-1,'0',99):
            with self.assertRaises(urllib.error.HTTPError) as error:post({'role':role,'documents':[change]})
            self.assertEqual(error.exception.code,400)
        personal = post({'documents':[change]})
        self.assertEqual(personal['documents'][0]['content'],'Private draft')
        crew_change = self.change('SOUL.md','# Casey custom instructions\n',team,0)
        result = post({'role':0,'documents':[crew_change]})
        self.assertEqual(result['documents'][0]['content'],crew_change['content'])
        self.assertEqual((self.studio.workspace(self.owner)/'SOUL.md').read_text(),'Private draft')
        self.studio.initialize_crew_workspaces(team)
        self.assertEqual((self.studio.workspace(team,0)/'SOUL.md').read_text(),crew_change['content'])


if __name__ == '__main__':unittest.main()
