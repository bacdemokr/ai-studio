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
    b=contract['brief'];c=contract['capacity'];daily=b['duration']//b['session'];booths=[]
    for i,t in enumerate(c['topics']):
        days=[]
        for d in range(1,b['days']+1):
            count=(t['groups']+b['days']-d)//b['days']
            if count:days.append({'day':d,'slots':list(range(min(i,daily-count),min(i,daily-count)+count)),'rotation':[0,0,1,1]})
        booths.append({'topicId':t['id'],'presenters':['Presenter %02d (unassigned)'%(2*i+1),'Presenter %02d (unassigned)'%(2*i+2)],'days':days})
    return {'sessionMinutes':b['session'],'maxConsecutiveSessions':2,'criteria':['Stagger booth starts','Two consecutive visits before a break'],
            'tradeoff':'Two dedicated specialists per topic provide relief.','check':'Confirm each specialist’s availability.','booths':booths}


class AgentToolsAdapter(EventAdapter):
    def __init__(self):super().__init__();self.tool_calls=[]
    def respond(self,agent,session,prompt):
        stage=int(agent.rsplit('-r',1)[1]);work=Path(self.agents[agent]);actions=[]
        if stage in (1,2):
            contract=json.loads((work/'inbox/agent-task.json').read_text());files=contract['files']
            if stage==1:
                run(work,'search',['Agent-selected fixture query']);run(work,'read',['S'+str(i+1) for i in range(contract['brief']['themeCount'])])
                (work/files['demos']).write_text(json.dumps({'demos':demos(contract['brief'])}));actions=['search','read']
            else:
                (work/files['plan']).write_text(json.dumps(schedule_spec(contract)));run(work,'schedule',[]);actions=['schedule']
            text='I executed '+', '.join(actions)+' and saved the deliverable.'
        elif stage==3:
            author_page(work)
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

    def test_agents_execute_research_and_schedule_then_morgan_authors_page(self):
        job=self.event();p=job['payload'];self.assertEqual(job['status'],'done')
        self.assertCountEqual(self.adapter.tool_calls,['search','read','schedule'])
        self.assertTrue(p['website']['authored']);self.assertEqual(p['capacity']['staffingPolicy'],'agent-authored')
        self.assertEqual(p['research']['queries'],['Agent-selected fixture query'])
        self.assertTrue(all(t['researchStatus']=='sourced' for t in p['capacity']['topics']))
        self.assertEqual(p['handoffs']['1']['receivedFrom'],['0']);self.assertEqual(p['handoffs']['2']['receivedFrom'],['0'])
        self.assertEqual(set(p['handoffs']['3']['receivedFrom']),{'0','1','2'})
        source=json.loads((self.studio.workspace(self.owner,2)/agent_workflow.paths(job['id'])['schedule']).read_text())
        fields=lambda rows:[tuple(r[k] for k in ('booth','day','start','end','presenter','attendees')) for r in rows]
        self.assertEqual(fields(source['capacity']['schedule']),fields(p['capacity']['schedule']))
        self.assertTrue(all(r['demo']!='Research pending' for r in p['capacity']['schedule']))
        self.assertIn('Dylan',p['outputs']['0']);self.assertTrue(p['activity']['1']['available'])
        from morgan_page import SCHEDULE_MOUNT,POST_MOUNT,paths as page_paths
        raw=(self.studio.workspace(self.owner,3)/page_paths(job['id'])['html']).read_text()
        published=(self.studio.workspace(self.owner)/p['website']['path']).read_text()
        post=(self.studio.workspace(self.owner,3)/page_paths(job['id'])['post']).read_text().strip()
        self.assertEqual(raw.replace(SCHEDULE_MOUNT,p['scheduleFragment']).replace(POST_MOUNT,escape(post)),published)
        self.assertNotIn('Cross-training is required',published)

    def test_missing_native_tool_receipt_is_not_accepted_as_agent_work(self):
        original=self.adapter.respond
        def no_receipts(*args):
            reply=original(*args);reply.activity={'available':True,'calls':[]};return reply
        self.adapter.respond=no_receipts
        with self.assertRaisesRegex(RuntimeError,'No app-generated replacement'):
            self.event()
        job=self.studio.state(self.owner)['jobs'][0]
        self.assertNotIn('1',job['payload']['outputs']);self.assertNotIn('website',job['payload'])

    def test_six_themes_and_agent_cli_export_from_shipped_skill(self):
        import agent_runtime as runtime
        from event_planner import plan
        with patch.dict(os.environ,{'BAC_DATA_DIR':self.temp.name}):
            runtime.save_config(runtime.initial_config())
            workspace=Path(self.temp.name)/'shipped'
            runtime.register('test-scheduling',workspace,{'name':'Alex','persona':'analyst','skills':['event-tools','event-scheduling']},'Operations planner')
            entry=json.loads(runtime.config_path().read_text())['agents']['entries']['test-scheduling']
            self.assertIn('exec',entry['tools']['allow']);self.assertEqual(entry['sandbox']['mode'],'off')
            b,c=plan({'themeCount':6,'days':2,'attendees':180})
            payload={'brief':b,'capacity':c};agent_workflow.prepare(workspace,'cli-test',payload,2)
            contract=json.loads((workspace/'inbox/agent-task.json').read_text())
            (workspace/contract['files']['plan']).write_text(json.dumps(schedule_spec(contract)))
            script='skills/bac-event-tools/scripts/event_agent_tools.py'
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
        self.assertEqual(after['sources'][0],read)
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
        self.assertLessEqual(sum(len(s['article']) for s in result['sources']), 18000)
        self.assertTrue(all(len(s['article']) == 15300 for s in saved['sources'] if s['id'] in ids))
        self.assertEqual([s['id'] for s in result['sources']], ids)

    def test_page_source_stays_small_and_repeated_citations_are_allowed(self):
        import morgan_page
        job=self.event(6);payload=job['payload'];workspace=self.studio.workspace(self.owner,3)
        self.assertLess(len(morgan_page.starter(payload)),16000)
        source=workspace/morgan_page.paths(job['id'])['html']
        citation='<p class="source"><a href="https://blogs.nvidia.com/blog/example/">'+('A long source title ' * 8)+'</a></p>'
        raw=source.read_text();source.write_text(raw.replace('</main>',citation+citation+'</main>'))
        morgan_page.validate(workspace,job['id'],payload)
        paragraph='<p>'+('A duplicate promotional paragraph with no new information. '*3)+'</p>'
        source.write_text(raw.replace('</main>',paragraph+paragraph+'</main>'))
        with self.assertRaisesRegex(morgan_page.PageError,'duplicated promotional'):
            morgan_page.validate(workspace,job['id'],payload)

    def test_large_event_never_passes_full_timetable_to_morgan_inputs(self):
        import morgan_page
        job=self.event(6,days=2,attendees=720);payload=job['payload'];work=self.studio.workspace(self.owner,3)
        self.assertEqual({r['day'] for r in payload['capacity']['schedule']},{1,2})
        self.assertGreater(len(payload['scheduleFragment'].encode()),32000)
        for path in ('inbox/agent-task.json','inbox/shared-brief.json','inbox/morgan-page.json','inbox/morgan-page-starter.html'):
            with self.subTest(path=path):
                data=(work/path).read_text()
                self.assertLess(len(data.encode()),16000)
                self.assertNotIn('"presenterDuty":',data)
                self.assertNotIn('"schedule": [',data)
                self.assertNotIn('<table',data)
        contract=json.loads((work/'inbox/agent-task.json').read_text())
        self.assertEqual(contract['contract'],'inbox/morgan-page.json')
        page=morgan_page.validate(work,job['id'],payload)
        self.assertIn(payload['scheduleFragment'],page['html'])
        self.assertNotIn('<table',page['sourceHtml'])

    def test_completion_claim_without_writes_is_repaired_in_a_fresh_context(self):
        original=self.adapter.respond;calls=[]
        def missing_first_write(agent,session,prompt):
            if agent.endswith('-r3'):
                calls.append((session,prompt))
                if len(calls)==1:return Reply('The webpage and LinkedIn post are complete.',{})
            return original(agent,session,prompt)
        self.adapter.respond=missing_first_write
        job=self.event(6,days=2)
        self.assertEqual(job['status'],'done');self.assertEqual(job['payload']['pageDraft']['attempts'],2)
        self.assertEqual(len(calls),2);self.assertNotEqual(calls[0][0],calls[1][0])
        self.assertIn('do not read or rewrite the large timetable',calls[1][1])
        self.assertIn('Replace every MORGAN_*',calls[1][1])
        self.assertTrue(job['payload']['website']['authored'])

    def test_repeated_completion_claims_without_writes_never_publish_a_page(self):
        original=self.adapter.respond;calls=[]
        def no_writes(agent,session,prompt):
            if agent.endswith('-r3'):
                calls.append(session)
                return Reply('I finished and saved both files.',{})
            return original(agent,session,prompt)
        self.adapter.respond=no_writes
        with self.assertRaisesRegex(RuntimeError,'one repair'):self.event(6,days=2)
        job=self.studio.state(self.owner)['jobs'][0];p=job['payload']
        self.assertEqual(len(calls),2);self.assertNotEqual(job['status'],'done')
        self.assertEqual(p['pageDraft']['status'],'failed');self.assertEqual(p['pageDraft']['attempts'],2)
        self.assertNotIn('3',p['outputs']);self.assertIn('1',p['outputs']);self.assertIn('2',p['outputs'])
        self.assertFalse(p.get('website',{}).get('authored'))
        self.assertFalse(any(f.endswith('-event-page.html') for f in p.get('packageFiles',[])))

    def test_completed_source_must_contain_program_and_promotion_in_the_page(self):
        import morgan_page
        job=self.event(6,days=2);p=job['payload'];work=self.studio.workspace(self.owner,3)
        path=work/morgan_page.paths(job['id'])['html'];raw=path.read_text()
        # Token replacement alone cannot pass if the cards are hidden in a template.
        first=raw.index('<article>');last=raw.rindex('</article>')+len('</article>')
        path.write_text(raw[:first]+'<template>'+raw[first:last]+'</template>'+raw[last:])
        with self.assertRaisesRegex(morgan_page.PageError,'demo title in the program'):
            morgan_page.validate(work,job['id'],p)
        # A single marker in the head is not a visible LinkedIn post mount.
        path.write_text(raw.replace(morgan_page.POST_MOUNT,'').replace('</head>',morgan_page.POST_MOUNT+'</head>'))
        with self.assertRaisesRegex(morgan_page.PageError,'marker in the promotion'):
            morgan_page.validate(work,job['id'],p)
        path.write_text(raw)
        morgan_page.validate(work,job['id'],p)
        p['scheduleFragment']=''
        with self.assertRaisesRegex(morgan_page.PageError,'selected timetable is missing'):
            morgan_page.validate(work,job['id'],p)

    def test_schedule_rejects_double_topic_assignment_and_incomplete_coverage(self):
        from event_planner import plan
        b,c=plan({'themeCount':3});contract={'brief':b,'capacity':c};spec=schedule_spec(contract)
        compile_schedule(b,c,spec)
        bad=copy.deepcopy(spec);bad['booths'][1]['presenters'][0]=bad['booths'][0]['presenters'][0]
        with self.assertRaisesRegex(ValueError,'one topic'):compile_schedule(b,c,bad)
        bad=copy.deepcopy(spec);bad['booths'][0]['days'][0]['slots'].pop()
        with self.assertRaisesRegex(ValueError,'Cover all'):compile_schedule(b,c,bad)
        bad=copy.deepcopy(spec);bad['booths'][0]['days'][0]['rotation']=[0]
        with self.assertRaisesRegex(ValueError,'consecutive'):compile_schedule(b,c,bad)

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
