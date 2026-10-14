// Real app rendering, isolated connections and controlled plans; no model calls.
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const server=spawn('python3',['-B','tests/fixture_personal_models.py'],{env:{...process.env,BAC_TEST_PORT:'18275'},stdio:['ignore','pipe','pipe']});let browser;
 server.stderr.on('data',()=>{});
 try{
  await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('Fixture timeout')),15000);server.stdout.on('data',b=>{if(b.toString().includes('READY')){clearTimeout(t);resolve();}});server.once('exit',()=>{clearTimeout(t);reject(Error('Fixture exited'));});});
  browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1600,height:1050},reducedMotion:'reduce'}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const hires=['Jinny','Orbit'].map((name,i)=>({key:name.toLowerCase(),id:'bac-'+name.toLowerCase(),name,persona:'guide',skills:[i?'web':'builder'],purpose:i?'Research public sources.':'Build small webpages.',tone:'kind',avatar:{body:i?'round':'classic',color:'green',accessory:'none'},protection:'standard',pending:0}));
  const now=Date.now()/1000;
  const plan=(id,created,roles)=>({id,kind:'crew-chat',status:'running',created,updated:created,events:[],result:{},payload:{crewRole:0,teamMode:'hired',roster:hires,collaboration:{task:'Build a small guide.',activeRole:roles[0]??0,summary:'A small team task.',tasks:roles.map(role=>({role,task:'Make a focused contribution.',expected:'A useful result.'})),visitorBindings:Object.fromEntries(roles.map((role,i)=>[role,hires[i]])),calledRoles:roles,outputs:{},handoffs:{},checks:[]}}});
  let jobs=[plan('first',now,[5])],resetAt=0;
  const applyState=s=>({...s,agents:hires,crewChats:jobs,crewChatReset:{at:resetAt,epoch:String(resetAt)}});
  for(const routePath of ['**/api/session','**/api/state'])await page.route(routePath,async route=>{const headers={...route.request().headers()};delete headers['if-none-match'];const response=await route.fetch({headers});await route.fulfill({json:applyState(await response.json())});});
  await page.goto('http://127.0.0.1:18275');await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.personalModels);
  await page.locator('.world-room-map [data-world-scenario=plan]').click();
  const inspect=()=>page.evaluate(()=>BacCampus.inspect());
  const settled=()=>page.waitForFunction(()=>{const v=BacCampus.inspect().visitorTravel;return v.length===2&&v.every(x=>['working','seated'].includes(x.phase));});
  const refresh=()=>page.evaluate(()=>BacStudio.refresh());
  await settled();const initial=(await inspect()).visitorTravel.find(v=>v.key==='jinny').position;
  const first=jobs[0],p=first.payload.collaboration;
  p.outputs[5]={name:'Jinny',answer:'Done.',files:[]};p.responseReady=true;p.finalAnswer='Finished.';p.activeRole=0;
  first.payload.roundtable={status:'reviewing',members:[hires[1]],replies:{orbit:{status:'running'}}};
  await refresh();await settled();
  let scene=await inspect();assert.deepEqual(scene.visitorTravel.find(v=>v.key==='jinny').position,initial,'Response-ready must keep the desk');assert.equal(scene.roundtable.visible,false,'Reactions use existing seats');
  assert.equal(scene.visitorTravel.find(v=>v.key==='orbit').phase,'seated');
  first.status='done';first.payload.roundtable.replies.orbit={status:'done',answer:'Looks good.'};await refresh();await settled();
  scene=await inspect();assert.deepEqual(scene.visitorTravel.find(v=>v.key==='jinny').position,initial);assert.equal(scene.visitorTravel.find(v=>v.key==='jinny').role,5);
  assert(scene.residents.every(r=>!r.visible),'No duplicate Lounge actors after completion');
  // Starting a new request must retain the actual previous identities until planning completes.
  const next=plan('second',now+1,[]);delete next.payload.collaboration.tasks;delete next.payload.collaboration.visitorBindings;jobs=[next,first];await refresh();await settled();
  scene=await inspect();assert.deepEqual(scene.visitorTravel.find(v=>v.key==='jinny').position,initial);assert(!scene.crewExchange[5].visible,'Never substitute Cody for the retained hire');
  await page.locator('[data-visitor-agent=jinny]').click();assert.equal(await page.locator('#studio-crew-name').innerText(),'Jinny');
  // Assign Orbit to that desk; Jinny goes directly to the standby seats in Open Task.
  Object.assign(next.payload.collaboration,{tasks:[{role:5,task:'Build the next page.'}],visitorBindings:{5:hires[1]},calledRoles:[5],activeRole:5});await refresh();await settled();
  scene=await inspect();assert.equal(scene.visitorTravel.find(v=>v.key==='jinny').phase,'seated');assert.equal(scene.visitorTravel.find(v=>v.key==='orbit').phase,'working');assert(scene.residents.every(r=>!r.visible));
  next.status='done';next.payload.collaboration.responseReady=true;next.payload.collaboration.outputs={5:{name:'Orbit',answer:'Done.',files:[]}};await refresh();await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.personalModels);await page.locator('.world-room-map [data-world-scenario=plan]').click();await settled();
  assert.equal((await inspect()).visitorTravel.find(v=>v.key==='orbit').phase,'working','Reload restores the completed desk assignment');
  // Explicitly no specialists releases the previous team; later planning must not resurrect it.
  const empty=plan('empty',now+2,[]);empty.status='done';jobs=[empty,next,first];await refresh();await settled();assert((await inspect()).visitorTravel.every(v=>v.phase==='seated'));
  const pending=plan('pending',now+3,[]);delete pending.payload.collaboration.tasks;delete pending.payload.collaboration.visitorBindings;jobs=[pending,empty,next,first];await refresh();await settled();assert((await inspect()).visitorTravel.every(v=>v.phase==='seated'));
  // Reset removes all retained assignments. Event Brief's own scene is covered separately.
  jobs=[];resetAt=now+4;await refresh();await settled();assert((await inspect()).visitorTravel.every(v=>v.phase==='seated'));assert.deepEqual(errors,[]);
  console.log('PASS: completion/response-ready/reactions retain positions; pending next plan preserves clickable identity; confirmed replacement uses standby seats; reload, empty plan and reset. Actual UI, simulated plans.');
 }finally{if(browser)await browser.close();server.kill('SIGTERM');}
})().catch(e=>{console.error(e);process.exitCode=1;});
