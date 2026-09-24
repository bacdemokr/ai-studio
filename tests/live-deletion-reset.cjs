// Opt-in real Chrome + Settings Reset test. Deletes only its fresh test account.
// BAC_DATA_DIR must identify the preview at BASE_URL (default localhost:8080).
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {execFileSync}=require('node:child_process'),{chromium}=require('playwright');
if(!process.argv.includes('--run-live')||!process.env.BAC_DATA_DIR)throw Error('Use --run-live and BAC_DATA_DIR');
// Match the preview's canonical policy paths; a relative spelling must never
// make fixture setup think an already configured OpenShell needs installation.
process.env.BAC_DATA_DIR=fs.realpathSync(process.env.BAC_DATA_DIR);
const base=process.env.BASE_URL||'http://127.0.0.1:8080';
if(!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base))throw Error('Local preview only');
const crashChat=process.argv.includes('--restart-during-chat');
const created=[],events=[],report=process.env.REPORT_PATH||'/tmp/bac-live-reset.json';
function emit(event,extra={}){const row={event,...extra};events.push(row);fs.writeFileSync(report,JSON.stringify({created,events},null,2));console.log(JSON.stringify(row));}
function native(action){return JSON.parse(execFileSync('python3',['-B','-c',`
import sys,os,json,sqlite3,time
from pathlib import Path
sys.path.insert(0,'scripts')
import agent_runtime as rt,agent_policy as policy
from studio import CREW_CATALOG,ROLE_SKILLS
items=json.loads(sys.argv[1]);action=sys.argv[2];data=Path(os.environ['BAC_DATA_DIR']);db=sqlite3.connect(data/'studio/studio.sqlite')
ids=[x['owner'] for x in items]
if action=='baseline':
 print(json.dumps({'app':[r[0] for r in db.execute('select id from agents where profile is not null')], 'native':list(rt.c.read_json(rt.config_path())['agents']['entries']), 'sandboxes':sorted(policy.sandbox_names())}));sys.exit()
if action=='chat-active':
 import subprocess
 result=subprocess.run([str(rt.root()/'node/bin/node'),'tests/native-lifecycle-probe.mjs',str(rt.root()),'bac-'+ids[0],'active'],env=rt.environment(),capture_output=True,text=True,timeout=40)
 assert result.returncode==0,'Could not verify active native chat'
 print(result.stdout);sys.exit()
if action=='crash-boundary':
 if sys.argv[3]=='chat':
  print(json.dumps({'ready':bool(db.execute('select 1 from agents where id=? and deleting=2',(ids[0],)).fetchone())}));sys.exit()
 nid='bac-'+ids[0]
 c=sqlite3.connect(rt.root()/'state/state/openclaw.sqlite')
 row=c.execute('select cleanup_completed from agent_deletion_journal where agent_id=?',(nid,)).fetchone()
 print(json.dumps({'ready':bool(row and not row[0] and nid not in rt.c.read_json(rt.config_path())['agents']['entries'])}));sys.exit()
if action=='restart':
 import signal,subprocess
 meta=Path(os.environ['PREVIEW_METADATA_PATH']);m=json.loads(meta.read_text());repo=Path.cwd().resolve()
 assert Path(m['checkout']).resolve()==repo and Path(m['dataDir']).resolve()==data.resolve()
 assert m['url']==os.environ.get('BASE_URL','http://127.0.0.1:8080')
 assert not db.execute("select 1 from jobs where status in ('running','stopping') and owner not in (%s)"%','.join('?'*len(ids)),ids).fetchone()
 assert not db.execute("select 1 from agents where deleting=2 and id not in (%s)"%','.join('?'*len(ids)),ids).fetchone()
 pid=m['pid'];cwd=subprocess.check_output(['lsof','-a','-p',str(pid),'-d','cwd','-Fn'],text=True)
 assert ('n'+str(repo)) in cwd.splitlines();db.close()
 os.kill(pid,signal.SIGTERM)
 for _ in range(100):
  try:os.kill(pid,0)
  except ProcessLookupError:break
  time.sleep(.1)
 else:raise RuntimeError('Preview did not stop')
 with meta.with_name('dev-server.log').open('ab') as log:
  proc=subprocess.Popen([sys.executable,'-B','scripts/serve.py','--port','8080'],cwd=repo,env=os.environ.copy(),stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 m.update(pid=proc.pid,restartedAt=time.time(),dirty=True);m.pop('verifiedCommit',None);meta.write_text(json.dumps(m,indent=2))
 print(json.dumps({'restarted':True,'pid':proc.pid}));sys.exit()
if action=='resources':
 names=[]
 for item in items:
  for suffix in ['', '-r0','-r1','-r2','-r3']:
   names.extend(r['containerName'] for r in policy.runtimes('bac-'+item['owner']+suffix,probe=False))
 print(json.dumps({'sandboxes':names}));sys.exit()
if action=='setup':
 for item in items:
  row=db.execute('select profile from agents where id=?',(item['owner'],)).fetchone();assert row and json.loads(row[0])['name']==item['name']
  profile=json.loads(row[0]);workspace=data/'studio/workspaces'/item['owner']
  rt.write_workspace(workspace,profile)
  if item['legacy']:
   (workspace/'.bac-prepared-only').unlink(missing_ok=True)
   assert profile['id'] not in rt.c.read_json(rt.config_path())['agents']['entries']
   assert not (rt.root()/'state/agents'/profile['id']).exists()
   for role,member in enumerate(CREW_CATALOG[:4]):
    crew={**member,'skills':list(ROLE_SKILLS[role]),'protection':member.get('protection','standard')}
    rt.register(profile['id']+'-r'+str(role),data/'studio/workspaces'/(item['owner']+'-'+str(role)),crew,member['role'])
 print(json.dumps({'legacyPersonalUnregistered':True,'legacyCrewRegistered':4}));sys.exit()
if action=='ready':
 active=db.execute("select count(*) from jobs where status in ('queued','running','stopping') and owner in (%s)"%','.join('?'*len(ids)),ids).fetchone()[0]
 print(json.dumps({'active':active}));sys.exit()
if action=='verify':
 remaining=[];entries=rt.c.read_json(rt.config_path())['agents']['entries']
 for item in items:
  owner=item['owner'];nid='bac-'+owner
  if db.execute('select id from agents where id=?',(owner,)).fetchone():remaining.append(owner+':app')
  remaining += [str(p) for p in (data/'studio/workspaces').glob(owner+'*')]
  remaining += [k for k in entries if k==nid or k.startswith(nid+'-r')]
  remaining += [str(p) for p in (rt.root()/'state/agents').glob(nid+'*') if (p/'agent').exists() or (p/'sessions').exists()]
  remaining += [r['containerName'] for r in policy.runtimes(nid,probe=False)]
 print(json.dumps({'remaining':remaining,'app':[r[0] for r in db.execute('select id from agents where profile is not null')], 'native':list(entries),'sandboxes':sorted(policy.sandbox_names())}))
`,JSON.stringify(created),action,crashChat?'chat':'native'],{encoding:'utf8',timeout:180000}));}
(async()=>{
 const before=native('baseline');
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 const page=await browser.newPage({viewport:{width:1500,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const api=(endpoint,body,owner)=>page.evaluate(async({endpoint,body,owner})=>{
  const session=await(await fetch('/api/session')).json(),headers={'Content-Type':'application/json','X-BaC-CSRF':session.csrf};if(owner)headers['X-BaC-Agent']=owner;
  const res=await fetch('/api/'+endpoint,{method:body?'POST':'GET',headers,body:body?JSON.stringify(body):undefined});return {status:res.status,data:await res.json()};
 },{endpoint,body,owner});
 try{
  await page.goto(base);await page.waitForFunction(()=>window.BacStudio);
  const session=(await api('session')).data,first=session.agentId;
  assert.equal(execFileSync('python3',['-c',"import os,sqlite3,sys;from pathlib import Path;c=sqlite3.connect(Path(os.environ['BAC_DATA_DIR'])/'studio/studio.sqlite');print(bool(c.execute('select 1 from agents where id=?',(sys.argv[1],)).fetchone()))",first],{encoding:'utf8'}).trim(),'True','URL/data directory mismatch');
  for(let i=0;i<4;i++){
   const name='ResetQA-'+Date.now()+'-'+i,protection=i===0||i===3?'openshell':'standard';
   const res=await api(i?'agents':'onboard',{name,persona:'analyst',skills:['memory'],protection},first);assert.equal(res.status,200);
   created.push({owner:i?res.data.agentId:first,name,legacy:i===1,protection});emit('created',{index:i,protection});
  }
  for(let i=0;i<180;i++){if(!native('ready').active)break;await page.waitForTimeout(1000);if(i===179)throw Error('Preparation timeout');}
  emit('fixture',native('setup'));
  const owned=native('resources');assert(owned.sandboxes.length>=2,'Real protected sandboxes required');
  await page.reload();await page.waitForFunction(()=>BacStudio.inspect().agents?.length===4);
  if(crashChat){
   for(let i=0;i<90;i++){if((await api('runtime')).data.ready)break;await page.waitForTimeout(1000);if(i===89)throw Error('Model not ready for active-chat crash test');}
   const job=await api('jobs',{kind:'chat',prompt:'Deletion test only. Use exec to run sleep 45 inside your sandbox, then reply done. Do not access the network.'},created[0].owner);assert.equal(job.status,200);
   for(let i=0;i<60;i++){if(native('chat-active').active>0)break;await page.waitForTimeout(500);if(i===59)throw Error('Native chat never became active');}
   emit('native_chat_running_before_delete');
  }
  await page.locator('#studio-config').click();await page.locator('#studio-settings-reset-tab').click();
  const begin=Date.now();await page.locator('#studio-agent-reset').click();
  if(process.argv.includes('--restart-during-delete')||crashChat){
   if(!process.env.PREVIEW_METADATA_PATH)throw Error('PREVIEW_METADATA_PATH required for controlled restart');
   for(let i=0;i<180;i++){
    if(native('crash-boundary').ready)break;
    await page.waitForTimeout(300);if(i===179)throw Error('No partial native deletion observed');
   }
   emit(crashChat?'restart_during_native_chat':'restart_at_partial_native_cleanup',native('restart'));
   for(let i=0;i<120;i++){
    try{await page.goto(base);await page.waitForFunction(()=>window.BacStudio,{},{timeout:3000});break;}
    catch(e){if(i===119)throw e;await page.waitForTimeout(500);}
   }
   // The first deletion must resume durably without another delete request.
   await page.waitForFunction(id=>window.BacStudio&&BacStudio.inspect().agents?.length===3&&!BacStudio.inspect().agents.some(a=>a.key===id),created[0].owner,{timeout:180000});
   emit('first_deletion_resumed_after_restart');
   await page.locator('#studio-config').click();await page.locator('#studio-settings-reset-tab').click();await page.locator('#studio-agent-reset').click();
  }
  await page.waitForFunction(()=>{const text=document.querySelector('#studio-settings-status')?.textContent||'';return text==='Lounge agents reset.'||text.includes('Deletion paused')||text.includes('removed.')||text.includes('Another agent');},null,{timeout:300000});
  const status=await page.locator('#studio-settings-status').innerText();emit('reset',{status,seconds:(Date.now()-begin)/1000});assert.equal(status,'Lounge agents reset.');
  await page.reload();await page.waitForFunction(()=>window.BacStudio&&BacStudio.inspect().agents?.length===0);
  const after=native('verify');assert.deepEqual(after.remaining,[]);
  for(const name of owned.sandboxes)assert(!after.sandboxes.includes(name),'Test sandbox remained');
  for(const k of ['app','native','sandboxes'])for(const id of before[k])assert(after[k].includes(id),'Existing resource changed: '+k);
  assert.deepEqual(errors,[]);emit('PASS',{count:4,protected:2,legacyCrewRoles:4,existingResourcesPreserved:true});
 }finally{
  // Keep authentication in this browser only; clean up our own fixtures on failure.
  for(const item of created){
   const deadline=Date.now()+240000;let clean=false;
   while(Date.now()<deadline){
    const state=await api('state');if(!state.data.agents?.some(a=>a.key===item.owner)){clean=true;break;}
    const r=await api('delete-agent',{name:item.name},item.owner);
    if(r.status===404||r.status===200&&r.data.deleted){clean=true;break;}
    if(![200,409].includes(r.status)){emit('cleanup_paused',{owner:item.owner,status:r.status});break;}
    await page.waitForTimeout(1000);
   }
   if(!clean)emit('cleanup_pending',{owner:item.owner});
  }
  await browser.close();
 }
})().catch(e=>{emit('FAIL',{error:e.message});process.exitCode=1;});
