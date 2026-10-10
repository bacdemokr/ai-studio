"""Opt-in end-to-end context regression on the running Studio and local model.

Run inside the Studio container against its authoritative registry:
  BAC_LIVE_CONTEXT_TEST=1 python3 tests/live_context_matrix.py event-2 code review documents research event-3
Creates only synthetic participants, uses the normal queue/worker, and deletes
only those participants after their jobs stop. No publishing or external writes.
"""
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

if os.environ.get('BAC_LIVE_CONTEXT_TEST') != '1':
    raise SystemExit('Set BAC_LIVE_CONTEXT_TEST=1 to run real-model context tests.')
source = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(source if source.is_dir() else Path('/opt/bac/app/scripts')))
from studio import Studio
import agent_runtime
import model_connections

CASES = {
    'code': '/plan Create a compact desktop HTML tip calculator. Inputs are bill and tip percentage; show tip and total. Reject empty, negative and non-finite values. Save a working single HTML file. No web research needed.',
    'review': '/plan Create a small desktop HTML attendee group calculator with attendee count and group size. Both must be positive whole numbers. Show groups rounded up. Then have Vera independently review the saved source for empty, zero, negative and fractional inputs. Label static inspection honestly.',
    'documents': '/plan Read supplied context-fixture.txt and save a concise summary of the workshop requirements at its beginning. The appendix is repetitive filler and not a requirement. State any coverage limitations. No web research needed.',
    'source_page': '/plan Read this official NVIDIA article and build a compact single-file desktop HTML summary with three supported facts and the exact source link: https://nvidianews.nvidia.com/news/nvidia-kicks-off-the-next-generation-of-ai-with-rubin-six-new-chips-and-a-new-platform-for-agentic-ai . Use only retrieved evidence; omit unsupported details. No additional research needed.',
    'research': '/plan Research two NVIDIA AI developments from official NVIDIA sources and create a compact desktop HTML overview with cited links. Use only retrieved evidence; mark unknown dates honestly. Keep the page small.',
}
# Studio initialization performs startup recovery. Refuse to touch a busy host.
import ops_common
registry=ops_common.home()/'studio/studio.sqlite'
if registry.exists():
    with sqlite3.connect(registry) as db:
        if db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running','stopping')").fetchone()[0]:
            raise SystemExit('Live context tests require an idle host; existing work is preserved.')
app=Studio(start_worker=False)

reports=[]

def metrics(owner, job):
    result={'modelResponses':0,'maxInputTokens':0,'toolCalls':0,'contextErrors':0,'planningReplies':[]}
    with app.db() as db:
        ids=[r['native_id'] for r in db.execute('SELECT native_id FROM crew_resources WHERE owner=?',(owner,))]
    for agent in ids:
        path=agent_runtime.root()/'state/agents'/agent/'agent/openclaw-agent.sqlite'
        if not path.is_file(): continue
        with sqlite3.connect(path) as db:
            rows=db.execute('SELECT t.event_json,s.session_key FROM transcript_events t JOIN session_windows s USING(session_id) WHERE s.session_key LIKE ?',('%'+job+'%',)).fetchall()
        for raw, session in rows:
            message=json.loads(raw).get('message',{})
            if message.get('role')!='assistant':continue
            result['modelResponses']+=1
            if session.endswith('-planning'):
                result['planningReplies'].extend(b['text'][:8000] for b in message.get('content',[]) if b.get('type')=='text')
            result['maxInputTokens']=max(result['maxInputTokens'],message.get('usage',{}).get('input',0))
            result['toolCalls']+=sum(b.get('type')=='toolCall' for b in message.get('content',[]) if isinstance(b,dict))
            error=str(message.get('errorMessage','')).lower()
            result['contextErrors']+=int('context' in error and any(x in error for x in ('limit','exceed','overflow')))
    return result

def cleanup(participant):
    with app.db() as db:
        targets=db.execute('SELECT r.native_id,r.workspace_name FROM crew_resources r JOIN crew_contexts c ON c.owner=r.owner WHERE c.participant=?',(participant,)).fetchall()
        db.executemany('INSERT OR IGNORE INTO session_cleanup_targets(participant,native_id,workspace_name) VALUES (?,?,?)',[(participant,r['native_id'],r['workspace_name']) for r in targets])
        db.execute('UPDATE participants SET retiring=1 WHERE id=?',(participant,))
        db.execute('UPDATE agents SET deleting=3 WHERE participant=?',(participant,))
    app.cleanup_session(participant)

try:
    for case in sys.argv[1:] or ['event-2','code','review','documents','research','event-3']:
        participant=app.session()[0]['id'];job=None;terminal=False
        start=time.monotonic()
        try:
            scenario='event-brief' if case.startswith('event-') else 'plan'
            owner=app.crew_owner(participant,scenario)
            with app.db() as db:
                db.execute('INSERT OR REPLACE INTO metadata(key,value) VALUES (?,?)',('scenario-model:'+owner,json.dumps({'provider':'local'})))
            for _ in range(100):
                if model_connections.status('local')['ready']:break
                time.sleep(.1)
            if scenario=='event-brief':
                data={'kind':'crew','preset':True,'executionMode':'agent-led-v1','brief':{'schema':2,'themeCount':int(case[-1]),'attendees':280,'duration':570,'city':'Zurich'}}
            else:
                if case=='documents':
                    folder=app.workspace(owner,0)/'inbox';folder.mkdir(parents=True,exist_ok=True)
                    (folder/'context-fixture.txt').write_text('WORKSHOP REQUIREMENTS: Zurich; 280 attendees; 6 stations; 570 minutes; desktop demonstrations; no registration or purchase.\nAPPENDIX (not requirements):\n'+('Repeated historical sample; no new requirements.\n'*30000))
                data={'kind':'crew-chat','crewRole':0,'prompt':CASES[case]}
            job=app.enqueue(owner,data)['id']
            print(json.dumps({'case':case,'job':job,'status':'started'}),flush=True)
            last=None
            while time.monotonic()-start<900:
                with app.db() as db:row=db.execute('SELECT * FROM jobs WHERE id=?',(job,)).fetchone()
                status=row['status'];payload=json.loads(row['payload'])
                events=json.loads(row['events']);title=events[-1]['title'] if events else status
                if title!=last:
                    print(json.dumps({'case':case,'status':status,'activity':title}),flush=True);last=title
                if status=='waiting':app.decision(owner,job,'approve-equipment')
                if status in ('done','error','cancelled'):
                    terminal=True;break
                time.sleep(2)
            if not terminal:
                app.decision(owner,job,'cancel')
                raise RuntimeError('Test exceeded 900 seconds; cancellation requested.')
            result=json.loads(row['result'])
            plan=payload.get('collaboration',{})
            report={'case':case,'job':job,'status':status,'seconds':round(time.monotonic()-start,1),
                    'outcome':plan.get('outcome'),'error':result.get('error'),'answer':str(result.get('answer',''))[:3000],
                    'remaining':plan.get('remaining'),'metrics':metrics(owner,job),
                    'roles':plan.get('calledRoles',list(payload.get('outputs',{}))),
                    'files':result.get('files',payload.get('packageFiles',[])),
                    'recovery':payload.get('outputLimitRecovery',plan.get('outputLimitRetry'))}
            saved=Path('/tmp/bac-context-results')/job;saved.mkdir(parents=True,exist_ok=True)
            for relative in report['files']:
                source=app.available_file(owner,relative)
                if source.is_file() and source.stat().st_size<2000000:
                    (saved/source.name).write_bytes(source.read_bytes())
            (saved/'report.json').write_text(json.dumps(report,indent=2))
            reports.append(report);print('RESULT '+json.dumps(report),flush=True)
        except Exception as error:
            reports.append({'case':case,'status':'test-error','error':str(error)[:500]})
            print('RESULT '+json.dumps(reports[-1]),flush=True)
        finally:
            if job and not terminal:
                # Do not remove a workspace from under an in-flight model call.
                for _ in range(200):
                    with app.db() as db:row=db.execute('SELECT status FROM jobs WHERE id=?',(job,)).fetchone()
                    if not row or row['status'] in ('done','error','cancelled'):terminal=True;break
                    time.sleep(2)
            if not job or terminal:cleanup(participant)
            else:print('Cleanup deferred for active synthetic participant '+participant,flush=True)
finally:
    app.stop.set()
print('MATRIX '+json.dumps(reports),flush=True)
if any(r['status']!='done' or r.get('metrics',{}).get('contextErrors') or
       (not r['case'].startswith('event-') and r.get('outcome')!='complete') or
       (r['case']=='review' and 4 not in r.get('roles',[])) for r in reports):sys.exit(1)
