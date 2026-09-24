// Opt-in real Chrome + Settings Reset test. Deletes only its fresh test account.
// BAC_DATA_DIR must identify the preview at BASE_URL (default localhost:8080).
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {execFileSync}=require('node:child_process'),{chromium}=require('playwright');
if(!process.argv.includes('--run-live')||!process.env.BAC_DATA_DIR)throw Error('Use --run-live and BAC_DATA_DIR');
const base=process.env.BASE_URL||'http://127.0.0.1:8080';
if(!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base))throw Error('Local preview only');
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
`,JSON.stringify(created),action],{encoding:'utf8',timeout:180000}));}
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
  await page.locator('#studio-config').click();await page.locator('#studio-settings-reset-tab').click();
  const begin=Date.now();await page.locator('#studio-agent-reset').click();
  await page.waitForFunction(()=>{const text=document.querySelector('#studio-settings-status')?.textContent||'';return text==='Lounge agents reset.'||text.includes('Deletion paused')||text.includes('removed.');},null,{timeout:300000});
  const status=await page.locator('#studio-settings-status').innerText();emit('reset',{status,seconds:(Date.now()-begin)/1000});assert.equal(status,'Lounge agents reset.');
  await page.reload();await page.waitForFunction(()=>window.BacStudio&&BacStudio.inspect().agents?.length===0);
  const after=native('verify');assert.deepEqual(after.remaining,[]);
  for(const name of owned.sandboxes)assert(!after.sandboxes.includes(name),'Test sandbox remained');
  for(const k of ['app','native','sandboxes'])for(const id of before[k])assert(after[k].includes(id),'Existing resource changed: '+k);
  assert.deepEqual(errors,[]);emit('PASS',{count:4,protected:2,legacyCrewRoles:4,existingResourcesPreserved:true});
 }finally{
  // Keep authentication in this browser only; clean up our own fixtures on failure.
  for(const item of created){const r=await api('delete-agent',{name:item.name},item.owner);if(![200,404].includes(r.status))emit('cleanup_pending',{owner:item.owner,status:r.status});}
  await browser.close();
 }
})().catch(e=>{emit('FAIL',{error:e.message});process.exitCode=1;});
