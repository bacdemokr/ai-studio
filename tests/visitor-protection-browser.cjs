// Real UI with injected native-policy evidence. No real OpenShell or model calls.
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const port=Number(process.env.BAC_TEST_PORT||18288),server=spawn('python3',['-B','tests/fixture_visitor_teams.py'],{env:{...process.env,BAC_TEST_PORT:String(port)},stdio:['ignore','pipe','inherit']});let browser;
 try{
  await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Fixture timeout')),15000);server.stdout.on('data',b=>{if(b.toString().includes('VISITOR FIXTURE READY')){clearTimeout(timer);resolve();}});server.once('exit',()=>reject(Error('Fixture exited')));});
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1600,height:1050},reducedMotion:'reduce'}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+port);await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
  await page.evaluate(()=>BacStudio.setRoom('workshop'));
  await page.locator('#studio-name').fill('Orbit');await page.getByRole('button',{name:'Web researcher',exact:true}).click();
  await page.locator('input[name=protection][value=openshell]').check();await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Orbit'&&BacStudio.inspect().room==='lounge');
  const owner=await page.evaluate(()=>BacStudio.inspect().agentId),started=Date.now()/1000;
  let events=[];
  await page.route('**/api/state*',async route=>{
   const headers={...route.request().headers()};delete headers['if-none-match'];
   const response=await route.fetch({headers}),state=await response.json();state.protectionEvents=events;
   if(headers['x-bac-scenario']==='plan'){
    const orbit=state.agents.find(a=>a.key===owner);
    state.crewChats=[{id:'protected-plan',owner,kind:'crew-chat',status:'running',created:started,events:[],result:{},payload:{teamMode:'hired',crewRole:0,prompt:'/goal Orbit, research a source.',collaboration:{task:'Research',activeRole:8,tasks:[{role:8,agent:owner,task:'Read source',inputs:[],requiredFiles:[]}],visitorBindings:{8:orbit},calledRoles:[8],handoffs:{},outputs:{}}}}];
   }
   await route.fulfill({response,json:state});
  });
  await page.locator('.world-room-map [data-world-scenario=plan]').click();
  await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.some(v=>v.name==='Orbit'&&v.phase==='working'));
  const event=(id,action='deny',source='OpenShell policy log')=>({id,owner,role:null,host:'example.com',action,source,time:Date.now()/1000,observedAt:Date.now()/1000});
  // A runtime error or model-written [blocked] text is not policy evidence.
  events=[event('tool-error','deny','OpenClaw tool activity')];await page.evaluate(()=>BacStudio.refresh());
  assert.equal((await page.evaluate(()=>BacCampus.inspect())).protectionHits.length,0);
  events.push(event('visitor-denied'));await page.evaluate(()=>BacStudio.refresh());
  await page.waitForFunction(()=>BacCampus.inspect().protectionHits.some(h=>h.id==='visitor-denied'&&h.visible));
  assert.match(await page.locator('.world-protection-hit:visible').innerText(),/Request blocked.*example.com.*OpenShell/s);
  assert(await page.evaluate(owner=>!!BacCampus.protectionReplyDelay(owner,null),owner));
  assert.equal(await page.evaluate(()=>BacCampus.inspect().residents.find(r=>r.key===BacStudio.inspect().agentId).visible),false);
  await page.screenshot({path:'/tmp/bac-visitor-openshell-denied.png'});
  await page.waitForFunction(()=>!BacCampus.inspect().protectionHits.length);
  await page.evaluate(()=>BacStudio.refresh());assert.equal((await page.evaluate(()=>BacCampus.inspect())).protectionHits.length,0,'No replay');
  events.push(event('visitor-allowed','allow'));await page.evaluate(()=>BacStudio.refresh());
  await page.waitForFunction(()=>BacCampus.inspect().protectionHits.some(h=>h.id==='visitor-allowed'&&h.visible));
  assert.match(await page.locator('.world-protection-allow:visible').innerText(),/Request allowed.*example.com/s);
  await page.waitForFunction(()=>!BacCampus.inspect().protectionHits.length);
  await page.locator('.world-room-map [data-world-scenario=event-brief]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  events.push(event('wrong-room'));await page.evaluate(()=>BacStudio.refresh());
  await page.waitForTimeout(200);assert.equal(await page.locator('.world-protection-hit:visible').count(),0,'Personal policy event must not attach to Event Brief crew');
  assert.deepEqual(errors,[]);console.log('PASS: hired Open Task denial/allow on visitor, verified-evidence-only notices, expiry/deduplication and Event Brief isolation. Policy evidence simulated.');
 }finally{if(browser)await browser.close();if(server.exitCode===null){server.kill('SIGTERM');await new Promise(r=>server.once('exit',r));}}
})().catch(e=>{console.error(e);process.exitCode=1;});
