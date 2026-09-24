"""Opt-in live lifecycle test (16 fresh agents, including 8 OpenShell profiles).

From the checkout, with the preview and its model already connected:
  python3 -B tests/live-deletion-cycles.py --run-live \
    --data-dir /absolute/path/to/preview-data --report /tmp/deletion-report.json

Uses a fresh app session and real installed runtimes; it never reads model keys.
Only identities created by this invocation are deleted. Other agents, native
entries and sandboxes must survive. Run against an idle development preview.
Failures retain a non-secret report of test identities and cleanup outcomes.
Use --scenario lifecycle (12 agents) or interruptions (4) to narrow a rerun.
"""
import os,sys,json,time,sqlite3,urllib.request,urllib.error,http.cookiejar,concurrent.futures
from pathlib import Path
# Explicit opt-in: creates and deletes only fresh test identities using a running app.
# Run with the same BAC_DATA_DIR as the server. No credentials are read or persisted.
import argparse,subprocess,socket
parser=argparse.ArgumentParser(description='Live creation/deletion regression against the real OpenClaw and OpenShell runtimes.')
parser.add_argument('--run-live',action='store_true',required=True)
parser.add_argument('--data-dir',type=Path,required=True)
parser.add_argument('--url',default='http://127.0.0.1:8080')
parser.add_argument('--report',type=Path,required=True)
parser.add_argument('--scenario',choices=('lifecycle','interruptions','all'),default='all')
args=parser.parse_args()
from urllib.parse import urlsplit
url=urlsplit(args.url)
if url.scheme!='http' or url.hostname not in ('127.0.0.1','localhost') or url.username or url.password or url.path not in ('','/'):
 parser.error('Use a local preview URL without credentials or a path.')
ROOT=Path(__file__).resolve().parents[1];DATA=args.data_dir.resolve();os.environ['BAC_DATA_DIR']=str(DATA);sys.path.insert(0,str(ROOT/'scripts'))
import agent_runtime as rt,agent_policy as policy
DB=DATA/'studio/studio.sqlite'; report=args.report.resolve();report.parent.mkdir(parents=True,exist_ok=True)
records=[];created=[];csrf='';started=time.time()
import threading
report_lock=threading.RLock()
jar=http.cookiejar.CookieJar();http=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
def call(path,body=None,owner=None,timeout=180):
 headers={'Content-Type':'application/json','X-BaC-CSRF':csrf}
 if owner:headers['X-BaC-Agent']=owner
 req=urllib.request.Request(args.url.rstrip('/')+'/api/'+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
 try:
  with http.open(req,timeout=timeout) as resp:return resp.status,json.load(resp)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
def rows(sql,args=()):
 with sqlite3.connect(DB) as db:db.row_factory=sqlite3.Row;return [dict(r) for r in db.execute(sql,args)]
def emit(event,**extra):
 with report_lock:
  records.append({'event':event,'elapsed':round(time.time()-started,1),**extra});report.write_text(json.dumps({'created':created,'records':records},indent=2));print(json.dumps(records[-1]),flush=True)
def ready(owner):
 deadline=time.monotonic()+240
 while time.monotonic()<deadline:
  jobs=rows("select status from jobs where owner=? and kind='prepare-agent' order by created desc limit 1",(owner,))
  if not jobs or jobs[0]['status']=='done':return
  if jobs[0]['status'] in ('failed','error','cancelled'):raise RuntimeError('Preparation '+jobs[0]['status'])
  time.sleep(1)
 raise TimeoutError('Preparation timeout')
def enqueue_chat(owner,prompt):
 # Match the UI: start a model turn only after runtime readiness returns.
 # A 503 here occurs before a job is inserted, so no model run is replayed.
 deadline=time.monotonic()+90;waiting=False
 while time.monotonic()<deadline:
  _,state=call('runtime')
  if state.get('ready'):
   status,result=call('jobs',{'kind':'chat','prompt':prompt},owner)
   if status==200:
    if waiting:emit('runtime_ready_again')
    return result
   if status!=503 or result.get('error')!='Your agent is saved. Start the shared LLM and OpenClaw on the host to run this mission.':
    raise AssertionError('Chat request rejected: '+str(status))
  if not waiting:emit('waiting_for_runtime');waiting=True
  time.sleep(1)
 raise TimeoutError('Runtime not ready for the model-dependent test')
def remove(item,duplicate=False):
 owner=item['owner'];begin=time.monotonic()
 code,result=call('delete-agent',{'name':item['name']},owner)
 if code not in (200,404):emit('delete_rejected',name=item['name'],status=code,error=result.get('error'));return False
 if duplicate:
  code2,_=call('delete-agent',{'name':item['name']},owner);emit('duplicate_request',name=item['name'],status=code2)
  if code2 not in (200,404):raise AssertionError('Duplicate deletion was not joined')
 deadline=time.monotonic()+240
 while time.monotonic()<deadline:
  state=rows('select deleting from agents where id=?',(owner,))
  if not state:emit('deleted',name=item['name'],seconds=round(time.monotonic()-begin,1));return True
  if state[0]['deleting']==1:emit('paused',name=item['name']);return False
  time.sleep(1)
 emit('delete_timeout',name=item['name']);return False
def verify(item,known_sandboxes):
 owner=item['owner'];native='bac-'+owner
 entries=json.loads(rt.config_path().read_text())['agents']['entries']
 remains={'app':bool(rows('select id from agents where id=?',(owner,))), 'workspaces':[p.name for p in (DATA/'studio/workspaces').glob(owner+'*')], 'nativeEntries':[k for k in entries if k==native or k.startswith(native+'-r')], 'nativeData':[p.name for p in (rt.root()/'state/agents').glob(native+'*') if (p/'agent').exists() or (p/'sessions').exists()], 'sandboxRegistry':len(policy.runtimes(native,probe=False)), 'sandboxes':sorted(known_sandboxes & policy.sandbox_names()) if known_sandboxes else []}
 # Completed means permanent app-owned retirement, not just a missing roster.
 remains['cleanupReceipt']=(rt.root()/'deletion-receipts'/(native+'.json')).exists()
 remains['nativeHistory']=[]
 state_db=rt.root()/'state/state/openclaw.sqlite'
 if state_db.exists():
  with sqlite3.connect(state_db) as db:
   for table in ('agent_deletion_journal','agent_databases','agent_provenance'):
    if db.execute("SELECT 1 FROM sqlite_master WHERE name=?",(table,)).fetchone():
     if db.execute('SELECT 1 FROM '+table+' WHERE agent_id=?',(native,)).fetchone():remains['nativeHistory'].append(table)
 remains['configBackups']=[p.name for p in (rt.root()/'state').glob('openclaw.json.*') if p.is_file() and native in json.loads(p.read_text()).get('agents',{}).get('entries',{})]
 emit('verified',name=item['name'],clean=not any(remains.values()),remains=remains)
 if any(remains.values()):raise AssertionError('Cleanup left resources')
baseline={r['id'] for r in rows('select id from agents where profile is not null')}
baseline_native=set(json.loads(rt.config_path().read_text())['agents']['entries'])
baseline_sandboxes=policy.sandbox_names()
_,session=call('session');csrf=session['csrf'];current=session['agentId']
if not rows('SELECT id FROM agents WHERE id=?',(current,)):
 raise RuntimeError('The URL and data directory do not belong to the same preview')
try:
 for cycle in (range(3) if args.scenario=='lifecycle' else range(3,4) if args.scenario=='interruptions' else range(4)):
  batch=[];known={}
  for index in range(4):
   protected=index%2==1;radar=index>=2
   name=f'DeleteQA-{cycle+1}-{index+1}'
   payload={'name':name,'persona':'analyst','skills':['radar'] if radar else ['memory'],'protection':'openshell' if protected else 'standard'}
   status,data=call('onboard' if not batch else 'agents',payload,current)
   if status!=200:raise RuntimeError('Create failed '+str(status))
   owner=current if not batch else data['agentId'];item={'owner':owner,'name':name,'protection':payload['protection'],'radar':radar};created.append(item);batch.append(item);(DATA/'studio/workspaces'/owner/'cleanup-marker.txt').write_text(owner);emit('created',**item)
  if cycle!=1:
   for item in batch:
    ready(item['owner']);known[item['owner']]={r['containerName'] for r in policy.runtimes('bac-'+item['owner'],probe=False)}
    if item['protection']=='openshell' and not known[item['owner']]:raise AssertionError('No real OpenShell sandbox')
    emit('ready',name=item['name'],sandboxCount=len(known[item['owner']]))
   if cycle==0:
    # A real model turn provisions the ordinary agent too.
    job=enqueue_chat(batch[0]['owner'],'Reply with exactly: deletion check ready')
    deadline=time.monotonic()+120
    while time.monotonic()<deadline:
     state=rows('select status from jobs where id=?',(job['id'],))[0]['status']
     if state in ('done','error','failed','cancelled'):break
     time.sleep(1)
    emit('model_turn',status=state)
    if state!='done':raise AssertionError('Model turn did not complete')
   elif cycle==2:
    job=enqueue_chat(batch[3]['owner'],'This is a deletion test. Use exec to run sleep 12, then say done. Do not use any network tools.')
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
     state=rows('select status from jobs where id=?',(job['id'],))[0]['status']
     if state!='queued':break
     time.sleep(.5)
    emit('delete_during_chat',status=state)
    if state!='running':raise AssertionError('No active chat to delete')
  if cycle==3:
   # Leave a stale native registry entry by removing this test agent's sandbox first.
   item=batch[1]
   for name in known[item['owner']]:policy.shell('sandbox','delete',name)
   deadline=time.monotonic()+30
   while known[item['owner']] & policy.sandbox_names():
    if time.monotonic()>deadline:raise TimeoutError('Test sandbox did not retire')
    time.sleep(.5)
   emit('sandbox_already_absent',name=item['name'])
   # Force an actual native heartbeat, then observe it in sessions.list before deletion.
   item=batch[3];native='bac-'+item['owner']
   prompt='Local deletion regression. Use exec to run sleep 30, then return HEARTBEAT_OK. Do not read feeds, access websites, or send messages.'
   (DATA/'studio/workspaces'/item['owner']/'HEARTBEAT.md').write_text(prompt+'\n')
   with rt.config_lock():
    config=json.loads(rt.config_path().read_text());config['agents']['entries'][native]['heartbeat']['prompt']=prompt;rt.save_config(config)
   def probe(action):
    result=subprocess.run([str(rt.root()/'node/bin/node'),str(ROOT/'tests/native-lifecycle-probe.mjs'),str(rt.root()),native,action],env=rt.environment(),capture_output=True,text=True,timeout=40)
    if result.returncode:
     # Preserve typed diagnostics without exposing native config or session text.
     details={}
     for line in result.stderr.splitlines():
      try:details=json.loads(line)
      except ValueError:continue
     emit('probe_failed',action=action,**{k:details[k] for k in ('errorName','kind','code','message') if k in details})
     if action=='active' and details.get('message')!='Invalid scoped sessions':return None
     raise RuntimeError('Native lifecycle '+action+' probe failed')
    return json.loads(result.stdout)
   time.sleep(2);probe('wake');deadline=time.monotonic()+120
   while True:
    active=probe('active')
    # Read-only observation may race gateway hot reload. Record each failed
    # read, never repeat the wake or accept an unobserved heartbeat as active.
    if active and active['heartbeat']:break
    if time.monotonic()>deadline:raise TimeoutError('Native heartbeat never became active')
    time.sleep(1)
   emit('native_heartbeat_active',name=item['name'],count=active['active'])
   # Lose only our HTTP reply, leaving the server/native deletion running.
   try:
    code,_=call('delete-agent',{'name':item['name']},item['owner'],timeout=.01)
    emit('early_delete_reply',name=item['name'],status=code)
   except (TimeoutError,socket.timeout,urllib.error.URLError):emit('client_disconnected',name=item['name'])
  if cycle==1:
   with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    results=list(pool.map(remove,batch))
   if not all(results):raise AssertionError('Concurrent deletion failed')
  else:
   for item in reversed(batch):
    if not remove(item,duplicate=cycle>=2):raise AssertionError('Deletion failed')
    for other in batch:
     state=rows('select deleting from agents where id=?',(other['owner'],))
     if state and not state[0]['deleting']:assert (DATA/'studio/workspaces'/other['owner']/'cleanup-marker.txt').read_text()==other['owner'],'Another workspace was changed'
  for item in batch:verify(item,known.get(item['owner'],set()))
  assert baseline <= {r['id'] for r in rows('select id from agents where profile is not null')},'Existing agent removed'
  emit('cycle_passed',cycle=cycle+1)
  _,state=call('state');current=state['agentId']
 assert baseline_native <= set(json.loads(rt.config_path().read_text())['agents']['entries']),'Existing native agent removed'
 assert baseline_sandboxes <= policy.sandbox_names(),'Existing sandbox removed'
 emit('PASS',count=len(created),existingAgentsPreserved=len(baseline),existingNativeAgentsPreserved=len(baseline_native),existingSandboxesPreserved=len(baseline_sandboxes))
except Exception as e:
 emit('FAIL',errorType=type(e).__name__,reason=str(e)[:180]);raise
finally:
 for item in created:
  if rows('select id from agents where id=?',(item['owner'],)):
   try:remove(item)
   except Exception as e:emit('test_cleanup_failed',name=item['name'],errorType=type(e).__name__)
