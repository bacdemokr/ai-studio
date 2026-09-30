import json
import unittest
import test_collaboration_plan as fixture
from artifact_references import published_references


class PublicReferencesTests(unittest.TestCase):
    setUp=fixture.CollaborationTests.setUp
    start=fixture.CollaborationTests.start
    job=fixture.CollaborationTests.job

    def test_final_answer_and_saved_response_use_real_downloads_and_upload_name(self):
        self.app.upload(self.owner,{'name':'sales (1).csv','content':'value\n3'})
        self.adapter.plan={'summary':'Summarize upload','tasks':[{
            'role':6,'task':'Read sales','inputs':['document-0'],'requiredFiles':['artifacts/summary.md']}]}
        original=self.adapter.respond
        def respond(agent,session,prompt,**kwargs):
            if session.endswith('-working'):
                (self.adapter.agents[agent]/'artifacts/summary.md').write_text('Total: 3')
                return 'Saved artifacts/summary.md'
            if session.endswith('-reviewing'):
                import re
                temporary=re.search(r'inbox/plan-input-[^" ]+\.csv',prompt)[0]
                return json.dumps({'done':True,'reason':'Finished','answer':'Read `'+temporary+'`. [Summary](artifacts/summary.md)'})
            return original(agent,session,prompt,**kwargs)
        self.adapter.respond=respond
        result=self.start('/plan Summarize sales (1).csv');self.app.execute(self.app.next_job())
        job=self.job(result);answer=job['result']['answer']
        self.assertNotIn('inbox/plan-input-',answer)
        self.assertIn('sales (1).csv',answer)
        path=job['payload']['collaboration']['outputs']['6']['files'][0]
        self.assertIn('[Summary]('+path+')',answer)
        self.assertEqual(self.app.available_file(self.owner,job['result']['files'][0]).read_text(),answer)

    def test_external_urls_code_and_unknown_paths_are_unchanged(self):
        text='`artifacts/a.md` and artifacts/a.md.bak https://example.com/artifacts/a.md\n```text\nartifacts/a.md\n```'
        result=published_references(text,{'artifacts/a.md':'artifacts/export.md'})
        self.assertTrue(result.startswith('`artifacts/export.md`'))
        self.assertIn('artifacts/a.md.bak',result)
        self.assertIn('https://example.com/artifacts/a.md',result)
        self.assertIn('```text\nartifacts/a.md\n```',result)
