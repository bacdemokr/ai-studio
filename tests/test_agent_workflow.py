"""Real skill tools and workflow wiring with explicitly simulated model/tool transcripts."""
import copy
from html import escape
import json
from pathlib import Path
import sqlite3
import tempfile
import os
import subprocess
import unittest
from unittest.mock import patch
from test_researched_event import EventAdapter,SOURCES,demos,author_page
from telemetry import Reply
from studio import Studio
from event_agent_tools import run,compile_schedule
import agent_workflow
import agent_activity


def schedule_spec(contract):
    from event_staffing import presenter_limit,work_slots,single_presenter_slots
    b=contract['brief'];c=contract['capacity'];minutes=c.get('session',b['session']);daily=b['duration']//minutes;booths=[];index=1
    for i,t in enumerate(c['topics']):
        count=presenter_limit(b,minutes,t['groups']);work=work_slots(minutes)
        allowed=single_presenter_slots(daily,minutes) if count==1 else list(range(daily))
        available=[(d,slot) for d in range(1,b['days']+1) for slot in allowed]
        selected=[available[j*len(available)//t['groups']] for j in range(t['groups'])]
        days=[]
        for d in range(1,b['days']+1):
            slots=[slot for day,slot in selected if day==d]
            if slots:days.append({'day':d,'slots':slots,'rotation':[0] if count==1 else [0]*work+[1]*work})
        names=['Presenter %02d (unassigned)'%(index+p) for p in range(count)];index+=count
        booths.append({'topicId':t['id'],'presenters':names,'days':days})
    return {'sessionMinutes':minutes,'maxConsecutiveSessions':work_slots(minutes),'criteria':['Stagger booth breaks','Work blocks with at least 15 minutes of rest'],
            'tradeoff':'Staff to the visit load; pause booths for breaks when one specialist is sufficient.','check':'Confirm specialist availability.','booths':booths}


class AgentToolsAdapter(EventAdapter):
    def __init__(self):super().__init__();self.tool_calls=[]
    def respond(self,agent,session,prompt):
        if prompt.startswith('LINKEDIN-FIRST:'):
            return Reply('Explore hands-on AI demos at our event. Discover practical ideas from the program and join us to learn together. #AI #BuildAClaw',{})
        stage=int(agent.rsplit('-r',1)[1]);work=Path(self.agents[agent]);actions=[]
        if stage in (1,2):
            contract=json.loads((work/'inbox/agent-task.json').read_text());files=contract['files']
            if stage==1:
                run(work,'search',['Agent-selected fixture query']);run(work,'read',['S'+str(i+1) for i in range(contract['brief']['themeCount'])])
                (work/files['demos']).write_text(json.dumps({'demos':demos(contract['brief'])}));actions=['search','read']
            else:
                run(work,'draft-schedule',[]);run(work,'schedule',[]);actions=['draft-schedule','schedule']
            text='I executed '+', '.join(actions)+' and saved the deliverable.'
        elif stage==3:
            post_path=work/json.loads((work/'inbox/morgan-page.json').read_text())['files']['post']
            saved_post=post_path.read_text()
            author_page(work)
            post_path.write_text(saved_post)
            contract=json.loads((work/'inbox/morgan-page.json').read_text());path=work/contract['files']['html']
            cards=''.join('<article><h3>'+escape(t['demo'])+'</h3><p>'+escape(t.get('action',''))+'</p><a href="'+escape(t.get('source',''),quote=True)+'">Source</a></article>' for t in contract['themes'])
            path.write_text(path.read_text().replace('<!-- Author the demo cards here from Dylan’s themes. -->',cards))
            text='I wrote the program cards, page and social post.'
        else:text='Dylan researches while Alex schedules. Morgan combines their saved handoffs.'
        answer=Reply(text,{})
        answer.activity={'available':True,'source':'Test fixture','calls':[{'id':session+'-'+a,'tool':'exec','action':a,'target':a,'status':'completed'} for a in actions]}
        self.tool_calls.extend(actions)
        return answer


class AgentWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.adapter=AgentToolsAdapter();self.studio=Studio(self.temp.name,self.adapter,start_worker=False);self.owner=self.studio.session()[0]['id']

    def event(self,count=3,**brief):
        job=self.studio.enqueue(self.owner,{'kind':'crew','preset':True,'workflow':'showcase','executionMode':agent_workflow.MODE,'brief':{'schema':2,'themeCount':count,**brief}})
        with patch('nvidia_research.discover',side_effect=AssertionError('The app must not search')),patch('nvidia_research.search_one',return_value=copy.deepcopy(SOURCES['sources'])),patch('event_agent_tools.read_article',return_value='Fixture article read by the agent tool.'):
            self.studio.execute(self.studio.next_job())
        return self.studio.state(self.owner)['jobs'][0]


    def test_three_themes_and_agent_cli_export_from_shipped_skill(self):
        import agent_runtime as runtime
        from event_planner import plan
        with patch.dict(os.environ,{'BAC_DATA_DIR':self.temp.name}), patch.object(runtime,'gateway_config_patch') as publish:
            runtime.save_config(runtime.initial_config())
            workspace=Path(self.temp.name)/'shipped'
            runtime.register('test-scheduling',workspace,{'name':'Alex','persona':'analyst','skills':['event-tools','event-scheduling']},'Operations planner')
            entry=publish.call_args.args[0]['agents']['entries']['test-scheduling']
            self.assertIn('exec',entry['tools']['allow']);self.assertEqual(entry['sandbox']['mode'],'off')
            b,c=plan({'themeCount':3,'days':2,'attendees':180})
            payload={'brief':b,'capacity':c};agent_workflow.prepare(workspace,'cli-test',payload,2)
            contract=json.loads((workspace/'inbox/agent-task.json').read_text())
            script='skills/bac-event-tools/scripts/event_agent_tools.py'
            drafted=subprocess.run([__import__('sys').executable,script,'draft-schedule'],cwd=workspace,capture_output=True,text=True)
            self.assertEqual(drafted.returncode,0,drafted.stderr)
            self.assertEqual(json.loads(drafted.stdout)['status'],'drafted')
            result=subprocess.run([__import__('sys').executable,script,'schedule'],cwd=workspace,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'],'validated')
            activity={'calls':[{'tool':'exec','action':'schedule','status':'completed'}]}
            result=agent_workflow.validate(workspace,'cli-test',payload,2,activity)
            self.assertEqual(sum(r['attendees'] for r in result['capacity']['schedule']),180)
            self.assertEqual({r['day'] for r in result['capacity']['schedule']},{1,2})
            self.assertIn('class="break"',result['scheduleHtml'])

    def test_followup_search_keeps_source_ids_and_successful_reads(self):
        from event_planner import plan
        workspace=Path(self.temp.name);b,c=plan({'themeCount':3})
        (workspace/'inbox').mkdir(exist_ok=True)
        agent_workflow.prepare(workspace,'search-test',{'brief':b,'capacity':c},1)
        with patch('nvidia_research.search_one',return_value=copy.deepcopy(SOURCES['sources'])):
            before=run(workspace,'search',['agents'])
        with patch('event_agent_tools.read_article',return_value='Verified article text'):
            read=run(workspace,'read',['S1'])['sources'][0]
        with patch('nvidia_research.search_one',return_value=[]):
            after=run(workspace,'search',['narrower query'])
        self.assertEqual({s['id']:s['url'] for s in before['sources']},{s['id']:s['url'] for s in after['sources']})
        self.assertNotIn('article',after['sources'][0])
        self.assertEqual(after['sources'][0]['readAt'],read['readAt'])
        saved=json.loads((workspace/agent_workflow.paths('search-test')['research']).read_text())
        self.assertEqual(saved['sources'][0]['article'],'Verified article text')
        with patch('event_agent_tools.read_article',side_effect=AssertionError('Do not fetch a successful read again')):
            cached=run(workspace,'read',['S1'])['sources'][0]
        self.assertEqual(cached,read)
        self.assertEqual(after['queries'],['agents','narrower query'])

    def test_article_batch_overlaps_keeps_complete_evidence_and_bounds_reply(self):
        import threading
        from event_planner import plan
        workspace = Path(self.temp.name); b, c = plan({'themeCount': 3})
        (workspace/'inbox').mkdir(exist_ok=True)
        agent_workflow.prepare(workspace, 'batch-test', {'brief': b, 'capacity': c}, 1)
        with patch('nvidia_research.search_one', return_value=copy.deepcopy(SOURCES['sources'])):
            research = run(workspace, 'search', ['agents'])
        ids = [s['id'] for s in research['sources'][:3]]
        barrier = threading.Barrier(3)
        def fetch(url):
            barrier.wait(timeout=3)
            return 'Evidence ' * 1700
        with patch('event_agent_tools.read_article', side_effect=fetch):
            result = run(workspace, 'read', ids)
        saved = json.loads((workspace/agent_workflow.paths('batch-test')['research']).read_text())
        self.assertTrue(all(s['articleTruncated'] for s in result['sources']))
        self.assertLessEqual(sum(len(s['article']) for s in result['sources']), 3600)
        self.assertTrue(all(len(s['article'])<=1200 for s in result['sources']))
        self.assertTrue(all(len(s['article']) == 15300 for s in saved['sources'] if s['id'] in ids))
        self.assertEqual([s['id'] for s in result['sources']], ids)
        with patch('event_agent_tools.read_article',return_value='Evidence ' * 1700):
            all_sources=run(workspace,'read',[s['id'] for s in research['sources'][:6]])
        self.assertLessEqual(sum(len(s['article']) for s in all_sources['sources']),3600)
        self.assertEqual(len(all_sources['sources']),6)
        with patch('event_agent_tools.read_article',side_effect=AssertionError('Evidence must not fetch')):
            evidence=run(workspace,'evidence',ids)
        self.assertEqual([s['id'] for s in evidence['sources']],ids)
        self.assertLessEqual(sum(len(s['article']) for s in evidence['sources']),3600)
        self.assertTrue(all('fullArticleFile' not in s for s in evidence['sources']))
        contract=json.loads((workspace/'inbox/agent-task.json').read_text())
        self.assertEqual(set(contract['capacity']),{'topics'})
        self.assertEqual(set(contract['demosSchema']['demos'][0]), {'topic','theme','title','sourceId','action','outcome','why','proof','risk','presenterExpertise'})
        self.assertIn('/sandbox',contract['workspaceGuidance'])
        self.assertTrue(contract['validationCommand'].endswith(' validate-themes'))
        self.assertLess(len(json.dumps(contract)),5000)


    def test_schedule_rejects_double_topic_assignment_and_incomplete_coverage(self):
        from event_planner import plan
        b,c=plan({'themeCount':3});contract={'brief':b,'capacity':c};spec=schedule_spec(contract)
        compile_schedule(b,c,spec)
        bad=copy.deepcopy(spec);bad['booths'][1]['presenters'][0]=bad['booths'][0]['presenters'][0]
        with self.assertRaisesRegex(ValueError,'one topic'):compile_schedule(b,c,bad)
        bad=copy.deepcopy(spec);bad['booths'][0]['days'][0]['slots'].pop()
        with self.assertRaisesRegex(ValueError,'Cover all'):compile_schedule(b,c,bad)
        bad=copy.deepcopy(spec);bad['maxConsecutiveSessions']=1;bad['booths'][0]['days'][0]['rotation']=[0]
        with self.assertRaisesRegex(ValueError,'consecutive'):compile_schedule(b,c,bad)

    def test_270_minutes_rejects_opening_cluster_and_accepts_spread(self):
        from event_planner import plan
        b,c=plan({'themeCount':3,'attendees':75,'duration':270,'session':15,'groupSize':5,'startTime':'10:00'})
        spec=schedule_spec({'brief':b,'capacity':c})
        for booth in spec['booths']:
            booth['days']=[{'day':1,'slots':[0,4,8,12,17],'rotation':[0]}]
        result=compile_schedule(b,c,spec)
        self.assertEqual(len(result['schedule']),15)
        self.assertEqual(sum(r['attendees'] for r in result['schedule']),75)
        self.assertEqual(max(r['end'] for r in result['schedule']),'14:30')
        for cluster in ([0,1,2,3,4],[13,14,15,16,17],[0,1,2,16,17]):
            bad=copy.deepcopy(spec);bad['booths'][0]['days'][0]['slots']=cluster
            with self.assertRaisesRegex(ValueError,'Spread.*full event'):compile_schedule(b,c,bad)

    def test_actual_210_minute_staggered_plan_no_longer_needs_repairs(self):
        from event_planner import plan
        b,c=plan({'themeCount':3,'attendees':140,'duration':210,'session':15,'groupSize':5})
        spec=schedule_spec({'brief':b,'capacity':c})
        actual=[[0,1,3,4,5,7,8,9,11,12],
                [0,2,3,5,6,8,9,10,12,13],
                [0,1,2,4,5,6,8,9,10,13]]
        for booth,slots in zip(spec['booths'],actual):
            booth['days']=[{'day':1,'slots':slots,'rotation':[0]}]
        result=compile_schedule(b,c,spec)
        self.assertEqual(len(result['schedule']),30)
        self.assertEqual(sum(r['attendees'] for r in result['schedule']),140)
        for booth,slots in zip(spec['booths'],actual):
            self.assertEqual(booth['days'][0]['slots'],slots)

    def test_all_distribution_and_rotation_errors_return_together(self):
        from event_planner import plan
        b,c=plan({'themeCount':3,'attendees':75,'duration':270,'session':15,'groupSize':5})
        spec=schedule_spec({'brief':b,'capacity':c})
        for booth in spec['booths']:
            booth['days']=[{'day':1,'slots':[0,1,2,3,4],'rotation':[0]}]
        with self.assertRaises(ValueError) as error:compile_schedule(b,c,spec)
        message=str(error.exception)
        for topic in b['topics']:self.assertIn('Spread '+topic,message)
        for booth in spec['booths']:self.assertIn(booth['presenters'][0]+' exceeds',message)
        self.assertIn('fix all listed issues',message)

    def test_distribution_across_days_and_single_visit(self):
        from event_planner import plan
        for args in ({'themeCount':3,'attendees':180,'days':2},
                     {'themeCount':3,'attendees':3,'days':2}):
            b,c=plan(args);spec=schedule_spec({'brief':b,'capacity':c})
            result=compile_schedule(b,c,spec)
            self.assertEqual(sum(r['attendees'] for r in result['schedule']),b['attendees'])
            if b['attendees']==180:
                self.assertEqual({r['day'] for r in result['schedule']},{1,2})
                bad=copy.deepcopy(spec)
                bad['booths'][0]['days']=[{'day':1,'slots':list(range(c['topics'][0]['groups'])),'rotation':[0]}]
                with self.assertRaisesRegex(ValueError,'Spread.*full event'):compile_schedule(b,c,bad)

    def test_native_trace_is_scoped_and_does_not_include_file_contents(self):
        root=Path(self.temp.name);dbpath=root/'agents/test/agent/openclaw-agent.sqlite';dbpath.parent.mkdir(parents=True)
        with sqlite3.connect(dbpath) as db:
            db.execute('create table session_windows(session_id text,session_key text)');db.execute('create table transcript_events(session_id text,seq integer,event_json text,created_at integer)')
            db.execute('insert into session_windows values(?,?)',('one','agent:test:openai-user:ours'))
            db.execute('insert into session_windows values(?,?)',('two','agent:test:openai-user:other'))
            events=[{'message':{'role':'assistant','content':[{'type':'toolCall','id':'a','name':'write','arguments':{'path':'artifacts/a.html','content':'DO NOT DISCLOSE'}}]}},
                    {'message':{'role':'toolResult','toolCallId':'a','isError':False}}]
            for i,event in enumerate(events):db.execute('insert into transcript_events values(?,?,?,?)',('one',i,json.dumps(event),2000))
            db.execute('insert into transcript_events values(?,?,?,?)',('two',0,json.dumps(events[0]).replace('artifacts/a.html','other.html'),2000))
        activity=agent_activity.collect(root,'test','ours',1)
        self.assertEqual(len(activity['calls']),1);self.assertEqual(activity['calls'][0]['status'],'completed')
        self.assertNotIn('DO NOT DISCLOSE',json.dumps(activity));self.assertNotIn('other.html',json.dumps(activity))

    def test_tool_receipt_does_not_accept_a_masked_shell_failure(self):
        root=Path(self.temp.name);dbpath=root/'agents/test/agent/openclaw-agent.sqlite';dbpath.parent.mkdir(parents=True)
        with sqlite3.connect(dbpath) as db:
            db.execute('create table session_windows(session_id text,session_key text)');db.execute('create table transcript_events(session_id text,seq integer,event_json text,created_at integer)')
            db.execute('insert into session_windows values(?,?)',('one','agent:test:openai-user:ours'))
            command='python3 skills/bac-event-tools/scripts/event_agent_tools.py read S1; true'
            call={'message':{'role':'assistant','content':[{'type':'toolCall','id':'a','name':'exec','arguments':{'command':command}}]}}
            result={'message':{'role':'toolResult','toolCallId':'a','details':{'exitCode':0}}}
            for i,event in enumerate((call,result)):db.execute('insert into transcript_events values(?,?,?,?)',('one',i,json.dumps(event),2000))
        with self.assertRaises(ValueError):agent_activity.require_action(agent_activity.collect(root,'test','ours'),'read')
        with sqlite3.connect(dbpath) as db:
            call['message']['content'][0]['arguments']['command']='python3 skills/bac-event-tools/scripts/event_agent_tools.py search agents && python3 skills/bac-event-tools/scripts/event_agent_tools.py read S1'
            db.execute('update transcript_events set event_json=? where seq=0',(json.dumps(call),))
        activity=agent_activity.collect(root,'test','ours')
        agent_activity.require_action(activity,'search');agent_activity.require_action(activity,'read')


if __name__=='__main__':unittest.main()
