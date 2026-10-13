// Real UI/WebGL with controlled API snapshots; never runs a model request.
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const port=Number(process.env.BAC_TEST_PORT||18287),server=spawn('python3',['-B','tests/fixture_visitor_teams.py'],{env:{...process.env,BAC_TEST_PORT:String(port)},stdio:['ignore','pipe','inherit']});let browser;
 try{
  await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('Fixture timeout')),15000);server.stdout.on('data',b=>{if(b.toString().includes('VISITOR FIXTURE READY')){clearTimeout(t);resolve();}});server.once('exit',()=>reject(Error('Fixture exited')));});
  browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1600,height:1050}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+port);await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
  for(const [name,role] of [['Jinny','Programmer'],['Orbit','Web researcher']]){
   await page.evaluate(()=>BacStudio.setRoom('workshop'));await page.locator('#studio-name').fill(name);
   await page.getByRole('button',{name:role,exact:true}).click();await page.locator('input[name=protection][value=standard]').check();
   await page.locator('#studio-create').click();await page.waitForFunction(name=>BacStudio.inspect().profile?.name===name&&BacStudio.inspect().room==='lounge',name);
  }
  let phase='previous',teamMode='hired';const now=Date.now()/1000;
  await page.route('**/api/state*',async route=>{
   const headers={...route.request().headers()};delete headers['if-none-match'];
   const response=await route.fetch({headers}),body=await response.json();
   if(route.request().headers()['x-bac-scenario']!=='plan'){await route.fulfill({response,json:body});return;}
   const jinny=body.agents.find(a=>a.name==='Jinny'),orbit=body.agents.find(a=>a.name==='Orbit');
   const tasks=[{role:8,agent:orbit.key,name:'Orbit',task:'Research a brief.',inputs:[],requiredFiles:[]},{role:5,agent:jinny.key,name:'Jinny',task:'Build a webpage.',inputs:[],requiredFiles:[]}];
   const base={kind:'crew-chat',events:[],result:{},updated:now,payload:{teamMode,includeHiredAgents:true,crewRole:0,prompt:'/goal Research and build'}};
   const previous={...base,id:'previous-plan',created:now-20,status:'done',payload:{...base.payload,collaboration:{task:'Research and build',summary:'Use Orbit and Jinny.',tasks,visitorBindings:{8:orbit,5:jinny},responseReady:true,activeRole:null,outputs:{},handoffs:{},calledRoles:[],checks:[]}}};
   const current={...base,id:'next-plan',created:now+1,status:'running',payload:{...base.payload,collaboration:{task:'Try again',activeRole:0,outputs:{},handoffs:{}}}};
   if(phase==='unbound')current.payload.collaboration.tasks=tasks;
   if(phase==='bound')Object.assign(current.payload.collaboration,{tasks,visitorBindings:{8:orbit,5:jinny},activeRole:8});
   if(phase==='standby')Object.assign(current.payload.collaboration,{tasks:tasks.map(t=>({...t,agent:'builtin',name:t.role===8?'Scout':'Cody'})),visitorBindings:{},activeRole:8});
   body.crewChats=phase==='previous'?[previous]:[current,previous];await route.fulfill({response,json:body});
  });
  await page.locator('.world-room-map [data-world-scenario=plan]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);await page.evaluate(()=>BacStudio.refresh());
  await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.length===2&&BacCampus.inspect().visitorTravel.every(v=>v.phase==='seated'));
  const samples=async()=>page.evaluate(async()=>{
   const seen=[];for(let i=0;i<16;i++){
    const snapshot=BacCampus.inspect();for(const r of snapshot.crewExchange.filter(r=>[5,8].includes(r.role)&&(r.visible||r.wanted||r.phase)))seen.push({role:r.role,visible:r.visible,phase:r.phase,wanted:r.wanted});
    await new Promise(r=>setTimeout(r,100));
   }return seen;
  });
  phase='planning';await page.evaluate(()=>BacStudio.refresh());const planning=await samples();
  if(process.argv.includes('--expect-bug')){
   assert(planning.some(r=>r.visible||r.wanted),'Expected reproduction of phantom standby entrance');
   console.log('REPRODUCED: new hired-only plan reused previous hired role slots as built-in actors:',JSON.stringify(planning));
   await page.screenshot({path:'/tmp/bac-phantom-standby-before.png'});return;
  }
  assert.deepEqual(planning,[],'Planning must not replay previous roles as standby agents');
  phase='unbound';await page.evaluate(()=>BacStudio.refresh());assert.deepEqual(await samples(),[],'Unconfirmed hired identities must not appear as standby');
  assert.equal(await page.locator('.crew-team-bubble').count(),0,'Casey must not announce unconfirmed standby names');
  phase='bound';await page.evaluate(()=>BacStudio.refresh());assert.deepEqual(await samples(),[],'Bound hired specialists must not spawn duplicate standby actors');
  assert.equal(await page.locator('.crew-team-bubble').textContent(),'We need Orbit and Jinny.','Casey must announce the confirmed hired identities');
  await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.some(v=>v.name==='Orbit'&&v.phase==='working'));
  await page.screenshot({path:'/tmp/bac-phantom-standby-after.png'});
  teamMode='mixed';phase='planning';await page.evaluate(()=>BacStudio.refresh());assert.deepEqual(await samples(),[],'Mixed planning must not borrow previous hired identities either');
  phase='unbound';await page.evaluate(()=>BacStudio.refresh());assert.deepEqual(await samples(),[],'Pending named hires must stay hidden until binding in Mixed too');
  phase='standby';await page.evaluate(()=>BacStudio.refresh());const standby=await samples();assert(standby.some(r=>r.role===5)&&standby.some(r=>r.role===8),'Explicit mixed standby assignments must still enter');
  assert.deepEqual(errors,[]);console.log('PASS: repeated hired-only planning, unbound/repaired selection and bound work never show Cody/Scout; Mixed preserves explicit standby entrances. Real browser, simulated snapshots.');
 }finally{if(browser)await browser.close();if(server.exitCode===null){server.kill('SIGTERM');await new Promise(r=>server.once('exit',r));}}
})().catch(e=>{console.error(e);process.exitCode=1;});
