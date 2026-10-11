// Disposable fixture_scenarios.py: exercise startup, navigation and shared warmup.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 const context=await browser.newContext({viewport:{width:1500,height:1000}});
 let release,entered;const gate=new Promise(resolve=>release=resolve),intercepted=new Promise(resolve=>entered=resolve);
 try {
  const base=process.env.BAC_TEST_URL||'http://127.0.0.1:8083',page=await context.newPage(),errors=[];
  let inference=0,requests=0;
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(r.url().endsWith('/api/jobs')&&r.method()==='POST')inference++;});
  await page.route('**/api/prepare-demo',async route=>{
   requests++;entered();assert.equal(route.request().headers()['x-bac-scenario'],'event-brief');
   assert.equal(route.request().postDataJSON().background,true);
   const response=await route.fetch();await gate;await route.fulfill({response});
  });
  const prep=()=>page.evaluate(()=>fetch('/api/state',{headers:{'X-BaC-Scenario':'event-brief'}}).then(r=>r.json()).then(s=>s.preparation));
  const started=page.waitForRequest(r=>r.url().endsWith('/api/prepare-demo'),{timeout:15000});
  await page.goto(base);await page.waitForFunction(()=>window.BacStudio?.inspect().agentId);
  await started;await intercepted;
  assert.equal(requests,1,'Prepare begins before visiting Stage 3');
  assert.equal(await page.locator('#studio-crew-form').count(),0);
  // Pending background POST must not block navigating to either scenario.
  await page.locator('.world-room-map [data-world-scenario=plan]').click();
  await page.waitForFunction(()=>BacCampus.inspect().navigation.activeScenario==='plan'&&!BacCampus.inspect().navigation.travelling);
  await page.locator('.world-room-map [data-world-scenario=event-brief]').click();
  await page.waitForFunction(()=>BacCampus.inspect().navigation.activeScenario==='event-brief'&&!BacCampus.inspect().navigation.travelling);
  release();await page.unrouteAll({behavior:'wait'});
  const deadline=Date.now()+15000;
  while((await prep())?.status!=='done'&&Date.now()<deadline)await page.waitForTimeout(200);
  assert.equal((await prep())?.status,'done');
  const first=await prep();assert.equal(first.payload.background,true);assert.deepEqual(first.payload.checks.map(c=>c.status),['ready','ready','ready','ready']);
  const second=await context.newPage();await second.goto(base);await second.waitForFunction(()=>window.BacStudio?.inspect().agentId);
  await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().agentId);
  await page.waitForTimeout(1700);assert.equal((await prep()).id,first.id);
  await page.locator('.world-room-map [data-world-scenario=event-brief]').click();
  await page.waitForFunction(()=>BacCampus.inspect().navigation.activeScenario==='event-brief'&&!BacCampus.inspect().navigation.travelling);
  await page.locator('#studio-room-action').click();
  await page.waitForFunction(()=>document.querySelectorAll('#studio-demo-preparation .demo-ready-row[data-status=ready]').length===4);
  await page.locator('#studio-dialog-close').click();await page.locator('#studio-room-action').click();
  assert.equal((await prep()).id,first.id);
  // A different personal agent still uses this participant's existing crew.
  const selected=await page.evaluate(async()=>{
   const session=await fetch('/api/session').then(r=>r.json());
   const post=(path,body)=>fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-BaC-CSRF':session.csrf},body:JSON.stringify(body)}).then(r=>r.json());
   const profile={name:'Scout',persona:'analyst',skills:['weather'],protection:'standard'};
   await post('onboard',profile);const agent=await post('agents',{...profile,name:'Pixel'});
   sessionStorage.setItem('bac-selected-agent',agent.agentId);return agent.agentId;
  });
  await page.reload();await page.waitForFunction(id=>window.BacStudio?.inspect().agentId===id,selected);
  assert.equal((await prep()).id,first.id);assert.equal(inference,0);assert.deepEqual(errors,[]);
  // Connection can become ready after boot, without entering either scenario.
  const late=await browser.newContext({storageState:await context.storageState()}),latePage=await late.newPage();let ready=false,lateRequests=0;
  latePage.on('request',r=>{if(r.url().endsWith('/api/prepare-demo'))lateRequests++;});
  for(const endpoint of ['session','runtime'])await latePage.route('**/api/'+endpoint,async route=>{
   const response=await route.fetch(),json=await response.json(),runtime=endpoint==='session'?json.runtime:json;
   runtime.gateway=true;runtime.modelConnections={enabled:true,connections:{api:{enabled:true,ready}}};
   await route.fulfill({json});
  });
  await latePage.route('**/api/state',async route=>{
   const response=await route.fetch({headers:{...route.request().headers(),'if-none-match':''}}),state=await response.json();
   if(state.scenario==='event-brief')state.preparation=null;
   await route.fulfill({response,json:state});
  });
  await latePage.goto(base);await latePage.waitForFunction(()=>window.BacStudio?.inspect().agentId);
  assert.equal(lateRequests,0,'No failed preparation while the model is disconnected');ready=true;
  await latePage.waitForRequest(r=>r.url().endsWith('/api/prepare-demo'),{timeout:15000});
  assert.equal(lateRequests,1);await latePage.unrouteAll({behavior:'wait'});await late.close();
  console.log('PASS: startup without stage visit, nonblocking navigation, ready form/reopen, tab/reload/agent deduplication, late connection and no inference. Fixture runtime.');
 } finally {release();for(const page of context.pages())await page.unrouteAll({behavior:'ignoreErrors'});await context.unrouteAll({behavior:'wait'});await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
