// Disposable fixture_scenarios.py only. Delay responses to exercise lifecycle races.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 let phase='running',disconnected=false,preparationRequests=0,release;
 const gate=new Promise(resolve=>release=resolve);
 const api=(path,body)=>page.evaluate(async({path,body})=>{
  const session=await fetch('/api/session').then(r=>r.json());
  const r=await fetch('/api/'+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-BaC-CSRF':session.csrf,'X-BaC-Scenario':'event-brief'},...(body?{body:JSON.stringify(body)}:{})});
  if(!r.ok)throw Error(await r.text());return r.json();
 },{path,body});
 const refresh=()=>page.evaluate(()=>BacStudio.refresh());
 const close=()=>page.locator('#studio-dialog-close').click();
 try{
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8083');await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.version==='SCENARIO TEST FIXTURE');
  await api('settings/connections',{source:'api',provider:'nvidia',apiKey:'fixture-key',model:'fixture-local-model'});
  await page.route('**/api/state',async route=>{
   const response=await route.fetch({headers:{...route.request().headers(),'if-none-match':''}}),state=await response.json();
   if(state.scenario==='event-brief'){
    if(state.preparation){
     state.preparation.status=phase;
     state.preparation.result=phase==='error'?{error:'Fixture: runtime preparation failed'}:{};
     state.preparation.payload.checks=state.preparation.payload.enabledRoles.map(role=>({name:['Riley','Dylan','Alex','Morgan'][role],required:true,status:phase==='done'?'ready':phase==='error'?'error':'preparing'}));
     state.scenarios.find(s=>s.id==='event-brief').busy=['queued','running'].includes(phase)||state.scenarios.find(s=>s.id==='event-brief').busy;
    }
    if(disconnected)state.teamConnection={...state.teamConnection,shared:true,ready:false,effectiveSource:null};
   }
   await route.fulfill({response,json:state});
  });
  await page.route('**/api/prepare-demo',async route=>{
   preparationRequests++;const response=await route.fetch();
   if(preparationRequests===1)await gate;
   await route.fulfill({response});
  });
  await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.version==='SCENARIO TEST FIXTURE');
  await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.gateway);
  // Let background preparation start before entering its room. The first response
  // stays pending while the form is opened and reopened.
  const until=Date.now()+15000;while(!preparationRequests&&Date.now()<until)await page.waitForTimeout(100);
  assert.equal(preparationRequests,1,'App boot starts Event Brief preparation before room entry');
  await page.locator('.world-room-map [data-world-scenario=event-brief]').click();
  await page.waitForFunction(()=>BacCampus.inspect().navigation.activeScenario==='event-brief'&&!BacCampus.inspect().navigation.travelling);
  await page.locator('#studio-room-action').click();
  await page.waitForFunction(()=>document.querySelector('#studio-prepare-demo')?.textContent==='Preparing…');
  assert.equal(await page.locator('#studio-launch-event').textContent(),'Preparing…');
  release();await page.waitForFunction(()=>document.querySelectorAll('#studio-demo-preparation .demo-ready-row').length===4);
  await close();
  assert.equal(await page.locator('#studio-crew-chat-connection').textContent(),'Preparing the Event Brief team…');
  assert(await page.locator('#studio-crew-prompt').isDisabled());
  assert(await page.locator('#studio-room-action').isEnabled(),'Can reopen preparation while it is running');
  await page.locator('#studio-room-action').click();
  assert.equal(await page.locator('#studio-prepare-demo').textContent(),'Preparing…');
  assert.equal(preparationRequests,1,'Reopening watches the preparation already started at app boot');
  phase='queued';await refresh();assert.equal(await page.locator('#studio-launch-event').textContent(),'Preparing…');
  phase='error';await refresh();
  assert.equal(await page.locator('#studio-prepare-demo').textContent(),'Retry preparation');
  assert(await page.locator('#studio-prepare-demo').isEnabled());assert(await page.locator('#studio-launch-event').isDisabled());
  phase='running';await page.locator('#studio-prepare-demo').click();
  await page.waitForFunction(()=>document.querySelector('#studio-prepare-demo')?.textContent==='Preparing…');
  phase='done';await refresh();
  await page.waitForFunction(()=>document.querySelector('#studio-launch-event')?.textContent==='Start the event plan'&&!document.querySelector('#studio-launch-event').disabled);
  const readyRequests=preparationRequests;
  await close();await page.locator('#studio-room-action').click();
  await page.waitForFunction(()=>!document.querySelector('#studio-launch-event').disabled);
  assert.equal(preparationRequests,readyRequests,'Completed foreground preparation is reused too');
  // A second tab can start work while this prepared form is open.
  const job=await api('jobs',{kind:'crew-chat',crewRole:0,prompt:'event hello [fixture:slow]'});
  await refresh();assert(await page.locator('#studio-launch-event').isDisabled(),'Do not offer a second launch while another tab is working');
  assert(await page.locator('#studio-prepare-demo').isDisabled(),'Do not offer conflicting preparation while the team is working');
  await page.waitForFunction(()=>!document.querySelector('#studio-launch-event').disabled);
  assert.equal((await api('state')).crewChats.find(j=>j.id===job.id).status,'done');
  disconnected=true;await refresh();
  assert(await page.locator('#studio-launch-event').isDisabled());
  assert.equal(await page.locator('#studio-event-connection').textContent(),'Model not connected. Enable Local or External Endpoint in Settings.');
  disconnected=false;await refresh();
  await close();assert(await page.locator('#studio-crew-prompt').isEnabled());
  assert.deepEqual(errors,[]);
  console.log('PASS: pending/queued/running/failed/ready preparation, reopen without duplicates, retry, other-tab work, and disconnected/reconnected model.');
 }finally{release();await page.unrouteAll({behavior:'wait'});await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
