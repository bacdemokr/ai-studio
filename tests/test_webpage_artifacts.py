import json
import test_collaboration_plan as collaboration
from test_studio import Studio, Problem
from webpage_artifacts import html_files, collect_pages

PAGE = '''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{font-family:Arial;background:#f4f8f0;padding:32px}h1{font-size:42px}button{background:#76b900;padding:12px;border:0}</style></head><body><h1>Workshop preview</h1><p>Explore a practical AI workshop.</p><button id="demo" onclick="this.textContent='It works'">Try demo</button><script>try{parent.document.body.dataset.previewEscaped='yes'}catch(e){};fetch('/api/session').catch(()=>{});</script></body></html>'''

class WebpageAdapter(collaboration.PlanAdapter):
    def __init__(self):
        super().__init__()
        self.plan['tasks'][-1] = {'role':5, 'task':'Build the webpage from the research and requirements.'}

    def respond(self, agent, session, prompt, **kwargs):
        answer=super().respond(agent,session,prompt,**kwargs)
        role=int(agent.rsplit('-r',1)[1]) if '-r' in agent else None
        if 'WEBPAGE_FIXTURE' in prompt and session.endswith('-planning'):
            plan = json.loads(answer)
            for task in plan['tasks']:
                if task.get('task') == 'Check a practical sequence and constraints.':
                    task.update(role=3, task='Write the webpage copy for Wade.')
            return json.dumps(plan)
        if 'WEBPAGE_FIXTURE' in prompt and (role in (None,5) or role == 3 and not session.startswith('bac-plan-')):
            path=self.agents[agent]/'artifacts'/'workshop.html'
            path.parent.mkdir(exist_ok=True)
            path.write_text(PAGE)
            return 'The workshop webpage is saved in artifacts/workshop.html.'
        return answer

# Reuse the small setup/helpers, not the full inherited regression cases.
import unittest
class WebpageTests(unittest.TestCase):
    setUp=collaboration.CollaborationTests.setUp
    start=collaboration.CollaborationTests.start
    job=collaboration.CollaborationTests.job

    def use_pages(self):
        self.adapter=WebpageAdapter()
        self.app.adapter=self.adapter

    def test_personal_page_without_builder_skill(self):
        self.use_pages()
        self.app.enqueue(self.owner,{'kind':'chat','prompt':'WEBPAGE_FIXTURE Build a page'})
        self.app.execute(self.app.next_job())
        job=self.app.state(self.owner)['jobs'][0]
        pages=[p for p in job['result']['files'] if p.endswith('.html')]
        self.assertEqual(len(pages),1)
        self.assertEqual(self.app.available_file(self.owner,pages[0]).read_text(),PAGE)
        self.assertIn('self-contained HTML',self.adapter.calls[0][2])

    def test_direct_crew_page_is_exported_for_authenticated_download(self):
        self.use_pages();team=self.app.crew_owner(self.owner)
        result=self.app.enqueue(team,{'kind':'crew-chat','crewRole':3,'prompt':'WEBPAGE_FIXTURE Build a page'})
        self.app.execute(self.app.next_job());job=self.job(result)
        page=job['result']['files'][0]
        self.assertEqual(self.app.available_file(self.owner,page).read_text(),PAGE)
        self.assertEqual(self.app.job_owner(self.owner,result['id']),team)
        outsider=self.app.session()[0]['id']
        with self.assertRaises(Problem):self.app.available_file(outsider,page)
        with self.assertRaises(Problem):self.app.job_owner(outsider,result['id'])

    def test_plan_collects_specialist_page_and_retains_original_snapshot(self):
        self.use_pages();result=self.start('/plan WEBPAGE_FIXTURE Build a workshop page')
        self.app.execute(self.app.next_job());job=self.job(result)
        pages=job['payload']['collaboration']['outputs']['5']['files']
        self.assertEqual(len(pages),1)
        self.assertIn(pages[0],job['result']['files'])
        team=self.app.crew_owner(self.owner)
        (self.app.workspace(team,5)/'artifacts/workshop.html').write_text('Changed in a later turn')
        restarted=Studio(self.temp.name,self.adapter,start_worker=False)
        self.assertEqual(restarted.available_file(self.owner,pages[0]).read_text(),PAGE)

    def test_fenced_complete_documents_and_not_fragments_or_claimed_paths(self):
        before=html_files(self.app.workspace(self.owner))
        paths=collect_pages(self.app,self.owner,'fenced',None,before,'```html\n'+PAGE+'\n```')
        self.assertEqual(len(paths),1)
        before=html_files(self.app.workspace(self.owner))
        self.assertEqual(collect_pages(self.app,self.owner,'fragment',None,before,'```html\n<h1>Example</h1>\n```\nSaved /etc/private.html'),[])

    def test_unchanged_nested_and_symlink_pages(self):
        w=self.app.workspace(self.owner);folder=w/'artifacts';folder.mkdir(exist_ok=True)
        (folder/'old.html').write_text(PAGE)
        before=html_files(w)
        nested=folder/'nested';nested.mkdir();(nested/'new.html').write_text(PAGE+'<!-- new -->')
        outside=w.parent/'not-this-agent.html';outside.write_text('PRIVATE_OTHER_AGENT')
        (folder/'escape.html').symlink_to(outside)
        (folder/'escape-dir').symlink_to(w.parent,target_is_directory=True)
        paths=collect_pages(self.app,self.owner,'nested',None,before,'')
        self.assertEqual(len(paths),1)
        self.assertEqual(self.app.available_file(self.owner,paths[0]).read_text(),PAGE+'<!-- new -->')

    def test_completed_page_remains_when_later_specialist_fails(self):
        self.use_pages();self.adapter.plan['tasks']=[{'role':5,'task':'Build page'},{'role':2,'task':'Review'}]
        self.adapter.fail_role=2;result=self.start('/plan WEBPAGE_FIXTURE Build a workshop page')
        with self.assertRaises(RuntimeError):self.app.execute(self.app.next_job())
        pages=self.job(result)['payload']['collaboration']['outputs']['5']['files']
        self.assertEqual(self.app.available_file(self.owner,pages[0]).read_text(),PAGE)

    def test_file_and_fenced_copy_create_only_one_preview(self):
        workspace=self.app.workspace(self.owner)
        before=html_files(workspace)
        (workspace/'artifacts'/'index.html').write_text(PAGE+'\n')
        paths=collect_pages(self.app,self.owner,'duplicate',None,before,'```html\n'+PAGE+'\n```')
        self.assertEqual(len(paths),1)
