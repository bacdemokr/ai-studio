// Disposable fixture_scenarios.py only; never run this against the user's preview.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8083');
  await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.version==='SCENARIO TEST FIXTURE');
  async function api(scenario,path,body){return page.evaluate(async({scenario,path,body})=>{
   const session=await fetch('/api/session').then(r=>r.json());
   const r=await fetch('/api/'+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-BaC-CSRF':session.csrf,'X-BaC-Scenario':scenario},...(body?{body:JSON.stringify(body)}:{})});
   if(!r.ok)throw new Error(path+': '+await r.text());return r.json();
  },{scenario,path,body});}
  async function choose(id){await page.locator('.world-room-map [data-world-scenario="'+id+'"]').click();await page.waitForFunction(id=>BacCampus.inspect().navigation.activeScenario===id&&!BacCampus.inspect().navigation.travelling,id);}
  await api('plan','settings/connections',{source:'api',provider:'nvidia',model:'fixture-other-model',apiKey:'fixture-key'});
  await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.modelConnections?.connections.api.ready);
  await choose('event-brief');
  assert.equal(await page.locator('#studio-crew-name').textContent(),'Riley');
  assert.equal(await page.locator('#studio-crew-role').textContent(),'Event coordinator');
  assert.equal(await page.locator('#studio-crew-model').textContent(),'fixture-other-model');
  let state=await api('event-brief','state');assert(state.teamSelections.slice(0,4).every(r=>r.id==='fixture-other-model'));
  const docs=await api('event-brief','agent-documents?role=0');
  assert.equal(docs.name,'Riley');assert(docs.documents.some(d=>d.path==='SOUL.md'&&d.content.includes('fixed team')));
  await choose('plan');assert.equal(await page.locator('#studio-crew-name').textContent(),'Casey');
  const ultra='nvidia/nvidia/nemotron-3-ultra-nvfp4',lightning='nvidia/nvidia/nemotron-3.5-lightning';
  await api('plan','team-model',{role:0,model:lightning});
  await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.version==='SCENARIO TEST FIXTURE');await choose('plan');
  await page.waitForFunction(()=>document.querySelector('#studio-crew-model').textContent==='Nemotron 3.5 Lightning');
  state=await api('plan','state');assert.equal(state.teamSelections[5].id,ultra);
  await choose('event-brief');assert.equal(await page.locator('#studio-crew-name').textContent(),'Riley');assert.equal(await page.locator('#studio-crew-model').textContent(),'fixture-other-model');
  await api('event-brief','settings/connections',{source:'local',provider:'local',baseUrl:'http://127.0.0.1:8000/v1',model:'fixture-local-model'});
  await api('event-brief','settings/connections/preferences',{scenarios:{'event-brief':'local',plan:'api'}});
  await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.version==='SCENARIO TEST FIXTURE');await choose('event-brief');
  await page.waitForFunction(()=>document.querySelector('#studio-crew-model').textContent==='fixture-local-model');
  state=await api('event-brief','state');assert(state.teamSelections.slice(0,4).every(r=>r.id==='fixture-local-model'));
  await choose('plan');assert.equal(await page.locator('#studio-crew-name').textContent(),'Casey');await page.waitForFunction(()=>document.querySelector('#studio-crew-model').textContent==='Nemotron 3.5 Lightning');
  assert.deepEqual(errors,[]);console.log('PASS: Riley/Casey identities, Instructions, shared event API/local models, independent Open Task selections, reload and floor switching.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
