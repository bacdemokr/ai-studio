import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch

from test_studio import Studio, Adapter
from agent_documents import read_documents, MAX_BYTES
from serve import create_server


class AgentDocumentsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.adapter=Adapter();self.studio=Studio(self.temp.name,self.adapter,start_worker=False)
        self.person=self.studio.session()[0];self.owner=self.person['id']
        self.studio.onboard(self.owner,{'name':'Scout','persona':'analyst','skills':['documents']})

    def save(self,relative,content,role=None):
        path=self.studio.workspace(self.owner,role)/relative;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(content,encoding='utf-8');return path

    def test_returns_exact_saved_files_and_only_equipped_custom_skills(self):
        source='# Tone\nKind, with a literal <script>example</script>.\n'
        self.save('SOUL.md',source);self.save('USER.md','# User preferences\nLocal demos.\n')
        self.save('skills/bac-documents/SKILL.md','Real saved skill instructions.\n')
        self.save('skills/bac-weather/SKILL.md','Not equipped; do not show.')
        self.save('openclaw.json','Secret configuration must not appear.')
        self.save('SOUL.md','# Casey\nCrew-specific instructions.\n',role=0)
        personal=read_documents(self.studio,self.owner)
        files={d['path']:d for d in personal['documents']}
        self.assertEqual(personal['name'],'Scout');self.assertEqual(files['SOUL.md']['content'],source)
        self.assertEqual(files['skills/bac-documents/SKILL.md']['status'],'ready')
        self.assertNotIn('skills/bac-weather/SKILL.md',files);self.assertNotIn('openclaw.json',files)
        crew=read_documents(self.studio,self.owner,0)
        self.assertEqual(crew['name'],'Casey');self.assertEqual(crew['documents'][0]['content'],'# Casey\nCrew-specific instructions.\n')
        self.assertEqual(self.studio.workspace(self.owner).joinpath('SOUL.md').read_text(),source)

    def test_missing_documents_do_not_provision_an_agent_or_create_files(self):
        workspace=self.studio.workspace(self.owner,4)
        self.assertFalse(workspace.exists())
        with patch.object(self.studio,'ensure_agent',side_effect=AssertionError('Inspection must stay read-only')):
            result=read_documents(self.studio,self.owner,4)
        self.assertTrue(all(d['status']=='missing' for d in result['documents']))
        self.assertFalse(workspace.exists())

    def test_unreadable_or_linked_file_does_not_expose_content_or_break_other_tabs(self):
        outside=Path(self.temp.name)/'outside.md';outside.write_text('Do not expose this.')
        (self.studio.workspace(self.owner)/'SOUL.md').symlink_to(outside)
        self.save('IDENTITY.md','Scout identity')
        self.save('USER.md','x'*(MAX_BYTES+1))
        self.save('AGENTS.md','valid').write_bytes(b'\xff\xfe')
        result=read_documents(self.studio,self.owner);files={d['path']:d for d in result['documents']}
        for name in ('SOUL.md','USER.md','AGENTS.md'):self.assertEqual(files[name]['status'],'unavailable')
        self.assertEqual(files['IDENTITY.md']['content'],'Scout identity')
        self.assertNotIn('Do not expose',json.dumps(result))

    def test_binary_file_api_accepts_uppercase_extensions_and_parentheses(self):
        import base64
        from urllib.parse import quote
        server=create_server('127.0.0.1',0,self.studio)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        for name,mime in [('Budget (1).XLSX','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),('Invite (1).EML','message/rfc822')]:
            with self.subTest(name=name):
                raw=b'\x80\xff binary fixture'
                self.save('inbox/'+name,'').write_bytes(raw)
                url='http://127.0.0.1:'+str(server.server_port)+'/api/file?path='+quote('inbox/'+name)
                request=urllib.request.Request(url,headers={'Cookie':'bac_session='+self.person['token'],'X-BaC-Agent':self.owner})
                with urllib.request.urlopen(request) as response:result=json.load(response)
                self.assertEqual(result['mime'],mime)
                self.assertEqual(base64.b64decode(result['content']),raw)

    def test_http_reads_are_account_scoped_and_accept_no_arbitrary_file_paths(self):
        self.save('SOUL.md','Personal source')
        team=self.studio.crew_owner(self.owner)
        (self.studio.workspace(team,0)/'SOUL.md').write_text('Casey source')
        other=self.studio.session()[0]['id'];self.studio.onboard(other,{'name':'Private','skills':['documents']})
        (self.studio.workspace(other)/'SOUL.md').write_text('Private source')
        server=create_server('127.0.0.1',0,self.studio)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        base='http://127.0.0.1:'+str(server.server_port)+'/api/agent-documents'
        def fetch(query='',owner=None):
            headers={'Cookie':'bac_session='+self.person['token'],'X-BaC-Agent':owner or self.owner}
            return json.load(urllib.request.urlopen(urllib.request.Request(base+query,headers=headers),timeout=3))
        self.assertEqual(fetch()['documents'][0]['content'],'Personal source')
        self.assertEqual(fetch('?role=0')['documents'][0]['content'],'Casey source')
        for query in ('?role=-1','?role=99','?role=','?role=0&role=1','?path=../../openclaw.json'):
            with self.subTest(query=query),self.assertRaises(urllib.error.HTTPError) as error:fetch(query)
            self.assertEqual(error.exception.code,400)
        with self.assertRaises(urllib.error.HTTPError) as error:fetch(owner=other)
        self.assertEqual(error.exception.code,404)


if __name__=='__main__':unittest.main()
