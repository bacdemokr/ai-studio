// Real Hiring UI and navigation, controlled finished-job snapshots; no model calls.
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const port=Number(process.env.BAC_TEST_PORT||18288),server=spawn('python3',['-B','tests/fixture_visitor_teams.py'],{env:{...process.env,BAC_TEST_PORT:String(port)},stdio:['ignore','pipe','inherit']});let browser;
 try{
  await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('Fixture timeout')),15000);server.stdout.on('data',b=>{if(b.toString().includes('VISITOR FIXTURE READY')){clearTimeout(t);resolve();}});server.once('exit',()=>reject(Error('Fixture exited')));});
  browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1600,height:1050}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+port);await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
  for(const name of ['Jinny','Orbit','Scout','Smith','Pixel','Sage']){
   await page.evaluate(()=>BacStudio.setRoom('workshop'));await page.locator('#studio-name').fill(name);
   await page.getByRole('button',{name:name==='Jinny'?'Programmer':'Weather buddy',exact:true}).click();
   await page.locator('input[name=protection][value=standard]').check();await page.locator('#studio-create').click();
   await page.waitForFunction(name=>BacStudio.inspect().profile?.name===name&&BacStudio.inspect().room==='lounge',name);
  }
  let done=false,number=1;const now=Date.now()/1000;
  await page.route('**/api/state*',async route=>{
   const headers={...route.request().headers()};delete headers['if-none-match'];
   const response=await route.fetch({headers}),body=await response.json(),jinny=body.agents.find(a=>a.name==='Jinny');
   body.crewChats=[{id:'navigation-job-'+number,kind:'crew-chat',status:done?'done':'running',created:now+number,updated:now+number,events:[],result:{},payload:{teamMode:'hired',crewRole:0,prompt:'/goal Build a page',collaboration:{task:'Build a page',summary:'Jinny builds the page.',tasks:[{role:5,agent:jinny.key,name:'Jinny',task:'Build a page.',inputs:[],requiredFiles:[]}],visitorBindings:{5:jinny},responseReady:done,activeRole:done?null:5,outputs:{},handoffs:{},calledRoles:[5],checks:[]}}}];
   await route.fulfill({response,json:body});
  });
  const lounge=page.locator('.world-room-map [data-world-room=lounge]'),mission=page.locator('.world-room-map [data-world-scenario=plan]');
  const jinny=()=>page.evaluate(()=>BacCampus.inspect().visitorTravel.find(v=>v.name==='Jinny'));
  const allSeated=()=>page.waitForFunction(()=>{const v=BacCampus.inspect().visitorTravel;return v.length===6&&v.every(a=>a.phase==='seated'&&a.role===null);});
  await mission.click();await page.evaluate(()=>BacStudio.refresh());
  await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.find(v=>v.name==='Jinny')?.phase==='working');
  done=true;await page.evaluate(()=>BacStudio.refresh());const desk=(await jinny()).position;
  assert.equal((await jinny()).phase,'working','Finishing alone must not move Jinny');
  // Full return, then re-entry through the actual navigation buttons.
  await lounge.click();await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.length===0);
  assert.equal(await page.evaluate(()=>BacCampus.inspect().residents.filter(r=>r.visible).length),6);
  await mission.click();await allSeated();assert((await jinny()).position[2]>desk[2]);
  // A fresh task puts Jinny at the desk again. Interrupt the return before it finishes.
  number++;done=false;await page.evaluate(()=>BacStudio.refresh());
  await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.find(v=>v.name==='Jinny')?.phase==='working');
  done=true;await page.evaluate(()=>BacStudio.refresh());await lounge.click();
  await page.waitForFunction(z=>{const v=BacCampus.inspect().visitorTravel.find(v=>v.name==='Jinny');return v?.phase==='returning'&&v.position[2]>z+.7;},desk[2]);
  const turning=(await jinny()).position;
  await page.evaluate(()=>{
   window.returnTrace=[];window.traceReturning=true;
   const tick=()=>{if(!window.traceReturning)return;const v=BacCampus.inspect().visitorTravel.find(v=>v.name==='Jinny');if(v)returnTrace.push({phase:v.phase,role:v.role,position:v.position});requestAnimationFrame(tick);};tick();
  });
  await mission.click();await page.evaluate(()=>BacStudio.refresh());await allSeated();
  const trace=await page.evaluate(()=>{window.traceReturning=false;return window.returnTrace;});
  assert(trace.length>10,'Sample the moving actor, not just its final seat');
  const minimumZ=Math.min(...trace.map(v=>v.position[2]));
  assert(minimumZ>=turning[2]-.1,`Jinny must not revisit the old desk: departure z=${turning[2]}, minimum z=${minimumZ}, desk z=${desk[2]}`);
  assert(trace.filter(v=>v.phase!=='returning').every(v=>v.role===null),'Old work must not be reassigned during navigation');
  assert.equal(await page.locator('[data-visitor-agent]').count(),6,'One scene actor per hire');
  assert.deepEqual(errors,[]);
  console.log('PASS: six real hires, full Lounge return and rapid button re-entry; no old-desk detour or duplicate actor. Simulated jobs, real animated UI.');
 }finally{if(browser)await browser.close();if(server.exitCode===null){server.kill('SIGTERM');await new Promise(r=>server.once('exit',r));}}
})().catch(e=>{console.error(e);process.exitCode=1;});
