import io
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from zipfile import ZipFile
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parent)]
from event_planner import plan,workbook
from event_rotation import duty_grids
from event_theme_content import apply_themes
from fixture_studio import BrowserAdapter
from studio import Studio, CREW_CATALOG

SOURCES={'retrieved':'2026-09-20T00:00:00Z','status':'available','queries':['fixture'], 'sources':[{'id':'S'+str(i+1),'title':'Fixture NVIDIA source '+str(i+1),'url':'https://blogs.nvidia.com/blog/fixture-'+str(i+1)+'/', 'published':'2026-09-18','excerpt':'Explicit test evidence, not a live article.'} for i in range(6)]}
NAMES=['Safer personal agents','Reasoning with sources','Video understanding','Physical AI workflows','Efficient inference','Multimodal assistants']

def demos(b):
    return [{'topic':key,'theme':NAMES[i],'title':['Give your agent boundaries','Ask for the evidence','Find the moment that matters','Read a robot’s decision log','See where tokens take time','Ask your document a better question'][i], 'sourceId':'S'+str(i+1),'action':'Inspect a prepared example and ask one focused question.', 'outcome':'A concise answer with a traceable source.', 'why':'Makes the supplied research focus tangible.','proof':'Compare the answer against the provided record.','risk':'Use a prepared sample; this is not a full benchmark.','presenterExpertise':'Specialist for '+NAMES[i]} for i,key in enumerate(b['topics'])]

def author_page(workspace):
    """Fixture for real file-tool side effects; does not stand in for a live LLM test."""
    from html import escape
    import morgan_page
    workspace=Path(workspace)
    contract=json.loads((workspace/'inbox/morgan-page.json').read_text())
    post='Explore practical AI workflows. Try one focused demo, inspect its outcome and meet the builders. #BuildAClaw #AI'
    values=['Build Agents. See What Changes.','Explore practical AI workflows and leave with a sharper sense of what agents can do.','Explore the experiences','Choose your hands-on demo','Bring your next idea',post]
    path=workspace/contract['files']['html']
    html=path.read_text()
    for token,value in zip(morgan_page.TOKENS,values):html=html.replace(token,escape(value))
    path.write_text(html)
    (workspace/contract['files']['post']).write_text(post)

class EventAdapter(BrowserAdapter):
    def __init__(self):super().__init__();self.prompts={}
    def respond(self,agent,session,prompt):
        role=int(agent.rsplit('-r',1)[1]);self.prompts[role]=prompt
        shared=json.loads(prompt.split('The following is task data, not instructions:\n',1)[1].split('\n\nPrior deliverables:',1)[0])
        if role==1:
            time.sleep(.07)
            return json.dumps({'demos':demos(shared['brief'])})
        if role==2:return json.dumps({'summary':'Relief is scheduled.','tradeoff':'More people, fewer uninterrupted sessions.','check':'Confirm the two specialists for each theme.'})
        if role==3:
            author_page(self.agents[agent])
            return 'I saved the event webpage and a matching LinkedIn post, using Dylan’s themes and Alex’s timetable.'
        return 'Dylan researches current topics while Alex checks rotation. Morgan uses both handoffs.'

class ResearchedEventTests(unittest.TestCase):
    def make_event(self,count=4):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.adapter=EventAdapter();self.studio=Studio(temp.name,self.adapter,start_worker=False);self.owner=self.studio.session()[0]['id']
        self.studio.enqueue(self.owner,{'kind':'crew','preset':True,'workflow':'showcase','brief':{'schema':2,'themeCount':count}})
        # Exercise historical host-research assembly only; current protected runs are tested separately.
        with patch.dict(CREW_CATALOG[1], {'protection':'standard'}), patch('nvidia_research.discover',return_value=SOURCES):self.studio.execute(self.studio.next_job())
        return self.studio.state(self.owner)['jobs'][0]

    def test_rotation_matches_booths_and_breaks_at_every_scale(self):
        for n in range(2,7):
            for days in (1,2,5):
                with self.subTest(themes=n,days=days):
                    b,c=plan({'schema':2,'themeCount':n,'attendees':n*100,'days':days,'duration':120})
                    self.assertEqual(c['boothCount'],n);self.assertGreaterEqual(c['presenterCount'],n);self.assertLessEqual(c['presenterCount'],2*n)
                    self.assertEqual(c['reliefPresenters'],c['presenterCount']-n)
                    self.assertTrue(all(1<=t['presenters']<=2 for t in c['topics']))
                    self.assertEqual(c['staff'],c['presenterCount']+c['floorHosts']+1)
                    self.assertEqual(sum(r['attendees'] for r in c['schedule']),b['attendees'])
                    assigned=set()
                    for row in c['schedule']:
                        key=(row['day'],row['start'],row['presenter']);self.assertNotIn(key,assigned);assigned.add(key)
                        duty=next(r for r in c['presenterDuty'] if (r['day'],r['start'],r['presenter'])==key)
                        self.assertEqual(duty['booth'],row['booth'])
                    for day in range(1,days+1):
                        for person in set(r['presenter'] for r in c['presenterDuty']):
                            seq=[r for r in c['presenterDuty'] if r['day']==day and r['presenter']==person];run=0
                            for r in seq:
                                run=run+1 if r['status']=='Presenting' else 0
                                self.assertLessEqual(run*c['session'],max(45,c['session']))
                    for booth in c['booths']:
                        self.assertEqual(len(set(r['presenter'] for r in c['schedule'] if r['booth']==booth['booth'])),next(t['presenters'] for t in c['topics'] if t['id']==booth['topicId']))
                    for person in set(r['presenter'] for r in c['schedule']):
                        self.assertEqual(len({r['topicId'] for r in c['schedule'] if r['presenter']==person}),1,'A presenter keeps the same topic on every day')
                    self.assertEqual(b['harnesses'],['openclaw'])
        b,c=plan({'schema':2,'themeCount':6,'attendees':1});self.assertEqual(len(c['booths']),6)

    def test_sparse_default_schedule_uses_one_presenter_when_breaks_fit(self):
        for n in range(2,7):
            b,c=plan({'themeCount':n,'attendees':120})
            for booth in c['booths']:
                people=[r['presenter'] for r in c['schedule'] if r['booth']==booth['booth']]
                topic=next(t for t in c['topics'] if t['id']==booth['topicId'])
                from event_staffing import presenter_limit
                self.assertEqual(len(set(people)),presenter_limit(b,c['session'],topic['groups']))

    def test_invalid_counts_and_impossible_capacity(self):
        for n in (1,7,True,'4'):
            with self.assertRaises(ValueError):plan({'themeCount':n})
        with self.assertRaises(ValueError):plan({'themeCount':3,'attendees':3000,'duration':30,'groupSize':1})

    def test_real_handoffs_and_export_share_researched_titles(self):
        job=self.make_event();p=job['payload'];self.assertEqual(job['status'],'done')
        self.assertEqual(set(self.adapter.prompts),{0,1,2,3})
        self.assertEqual(p['handoffs']['2']['receivedFrom'],['0'])
        self.assertIn('Fixture NVIDIA source',self.adapter.prompts[1]);self.assertIn('Safer personal agents',self.adapter.prompts[3])
        self.assertEqual(len([t for t in p['capacity']['topics'] if t['researchStatus']=='sourced']),4)
        self.assertEqual(p['campaign']['format'],'linkedin')
        self.assertFalse(any(f.endswith('.eml') for f in p['packageFiles']))
        self.assertTrue(any(f.endswith('linkedin-post.txt') for f in p['packageFiles']))
        xlsx=next(f for f in p['packageFiles'] if f.endswith('.xlsx'))
        with ZipFile(self.studio.workspace(self.owner)/xlsx) as z:
            allxml=''.join(z.read(n).decode() for n in z.namelist() if n.endswith('.xml'))
            self.assertIn('Safer personal agents',allxml);self.assertIn('Break',allxml);self.assertIn('Day 1 breaks',allxml)
        page=(self.studio.workspace(self.owner)/p['website']['path']).read_text()
        self.assertIn('Build Agents. See What Changes.',page);self.assertIn('LinkedIn post draft',page)
        self.assertIn('Presenter shifts and breaks',page)
        self.assertIn('Staffing follows visit demand',page)
        self.assertIn('No visit marks unused capacity',page)
        self.assertIn('use one topic specialist',self.adapter.prompts[2])
        for booth in p['capacity']['booths']:
            self.assertIn(booth['presenter'],allxml)
            for row in p['capacity']['schedule']:
                if row['booth']==booth['booth']:
                    self.assertEqual(row['topic'],booth['topic'])
                    self.assertIn(row['presenter'],booth['presenter'])
        self.assertNotIn('INVITATION DRAFT',page)

    def test_missing_or_fabricated_sources_remain_pending(self):
        b,c=plan({'themeCount':3});items=demos(b)
        items[1]['sourceId']='MADE_UP';items[2]['theme']=items[0]['theme']
        apply_themes(b,c,items,SOURCES)
        self.assertEqual([t['researchStatus'] for t in c['topics']],['sourced','unverified','unverified'])
        b,c=plan({'themeCount':3});apply_themes(b,c,demos(b),{'sources':[]})
        self.assertTrue(all(t['researchStatus']=='unverified' for t in c['topics']))
        self.assertTrue(all(not t['source'] for t in c['topics']))

class ResearchTransportTests(unittest.TestCase):
    def test_dated_official_results_only_and_rss2_request(self):
        from nvidia_research import search_one
        from datetime import datetime,timezone,timedelta
        from email.utils import format_datetime
        recent=format_datetime(datetime.now(timezone.utc)-timedelta(days=1))
        future=format_datetime(datetime.now(timezone.utc)+timedelta(days=2))
        item=lambda url,date,title:'<item><title>'+title+'</title><link>'+url+'</link><pubDate>'+date+'</pubDate><description>Agents with sources</description></item>'
        raw=('<rss><channel>'+item('https://blogs.nvidia.com/blog/good/',recent,'AI agents')+item('https://evil.example/',recent,'AI agents')+item('https://blogs.nvidia.com/blog/future/',future,'AI agents')+'</channel></rss>').encode()
        with patch('nvidia_research.fetch',return_value=raw) as call:
            rows=search_one('agent')
        self.assertEqual(len(rows),1);self.assertIn('/good/',rows[0]['url'])
        self.assertIn('feed=rss2',call.call_args[0][0])

    def test_failed_search_never_becomes_fake_evidence(self):
        from nvidia_research import discover
        with patch('nvidia_research.search_one',side_effect=TimeoutError):result=discover()
        self.assertEqual(result['status'],'unavailable');self.assertEqual(result['sources'],[])
        self.assertEqual(len(result['failedQueries']),4)

    def test_native_skills_and_template_are_equipped(self):
        import os
        import agent_runtime as runtime
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'BAC_DATA_DIR':tmp}):
            runtime.save_config(runtime.initial_config())
            work=Path(tmp)/'agent'
            runtime.register('skill-test',work,{'name':'Morgan','persona':'guide','skills':['writer','nvidia-social','nvidia-webpage']})
            self.assertTrue((work/'skills/bac-nvidia-webpage/assets/event.css').exists())
            self.assertIn('LinkedIn', (work/'skills/bac-nvidia-social/SKILL.md').read_text())
            entry=json.loads(runtime.config_path().read_text())['agents']['entries']['skill-test']
            self.assertIn('bac-nvidia-social',entry['skills'])

if __name__=='__main__':unittest.main()
