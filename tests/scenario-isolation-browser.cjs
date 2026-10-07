// Integration coverage against fixture_scenarios.py only. Never resets a real preview.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:8083';
const ULTRA = 'nvidia/nvidia/nemotron-3-ultra-nvfp4';
const LIGHTNING = 'nvidia/nvidia/nemotron-3.5-lightning';
const active = job => ['queued', 'running', 'waiting', 'stopping'].includes(job.status);
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', args:['--enable-unsafe-swiftshader']});
  const page = await browser.newPage({viewport:{width:1500,height:1000}});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('dialog', dialog => dialog.accept());
  async function api(scenario, path, body) {
    return page.evaluate(async ({scenario,path,body}) => {
      const session = await fetch('/api/session').then(r => r.json());
      const response = await fetch('/api/'+path, {method:body ? 'POST':'GET', headers:{'Content-Type':'application/json','X-BaC-CSRF':session.csrf,'X-BaC-Scenario':scenario}, ...(body ? {body:JSON.stringify(body)}:{})});
      if (!response.ok) throw new Error(path+': '+response.status+' '+await response.text());
      return response.json();
    }, {scenario,path,body});
  }
  const state = scenario => api(scenario, 'state');
  const leaseTimer=setInterval(()=>api('plan','credential-session',{}).catch(()=>{}),15000);
  async function waitFor(check, detail, timeout=30000) {
    const until = Date.now()+timeout;
    while (Date.now()<until) {const result=await check(); if(result)return result; await new Promise(r=>setTimeout(r,250));}
    throw new Error('Timed out: '+detail);
  }
  async function choose(id) {
    await page.locator('.world-room-map [data-world-scenario="'+id+'"]').click();
    await page.locator('#studio-crew-passport').waitFor({state:'visible'});
    await page.waitForFunction(id=>BacCampus.inspect().navigation.activeScenario===id&&!BacCampus.inspect().navigation.travelling,id);
  }
  async function close() {if(await page.locator('#studio-dialog').evaluate(el=>el.open))await page.locator('#studio-dialog-close').click();}
  async function settings() {await page.locator('#studio-config').click();await page.locator('[data-connection-tab=reset]').click();}
  async function reset(scenario, all=false) {
    await settings();
    assert((await page.locator('#studio-settings-reset-panel').textContent()).includes(scenario==='plan'?'Open Task':'Event Brief'));
    await page.locator(all?'#studio-reset-all':'#studio-settings-bac-reset').click();
    await waitFor(async()=>{const s=await state(scenario);return !s.bacResetting&&!s.crewChats.length&&(s.crewDocuments||[]).length===0&&(!all||!s.agents.length);}, 'reset finished');
    await page.waitForFunction(()=>document.querySelector('#studio-settings-bac-reset')?.disabled);
    await close();
  }
  async function upload() {
    await page.locator('#studio-crew-document-input').setInputFiles({name:'notes.md',mimeType:'text/markdown',buffer:Buffer.from('Quarterly revenue: 100, 120, 150. Use this supplied data.')});
    await page.locator('[data-crew-document="inbox/notes.md"]').waitFor();
    await page.waitForFunction(()=>!document.querySelector('#studio-crew-document-add').disabled);
  }
  async function model(scenario, id) {
    if(scenario==='event-brief'){
      await api(scenario,'settings/connections',{source:'api',provider:'nvidia',model:id,apiKey:'fixture-key'});
    }else{
      if(!await page.locator('#studio-standby').evaluate(e=>e.open))await page.locator('#studio-standby summary').click();
      await page.locator('[data-standby-model="0"]').click();
      await page.getByRole('searchbox',{name:'Search API models'}).fill(id===LIGHTNING?'lightning':'ultra');
      await page.locator('[data-model-choice="'+id+'"]').click();
    }
    await waitFor(async()=> (await state(scenario)).teamSelections.some(r=>r.role===0&&r.id===id),'model applied');
    await close();
  }
  async function plan(prompt) {
    await page.locator('#studio-crew-prompt').fill('/plan '+prompt);await page.locator('#studio-crew-send').click();
    const job = await waitFor(async()=> (await state('plan')).crewChats.find(j=>j.payload.prompt.includes(prompt)), 'plan created');
    const result = await waitFor(async()=>{const j=(await state('plan')).crewChats.find(j=>j.id===job.id);return j&&!active(j)&&j;}, prompt+' completed',60000);
    assert.equal(result.status,'done',JSON.stringify(result.result));
    await page.waitForFunction(()=>!document.querySelector('#studio-crew-prompt').disabled);
    return result;
  }
  try {
    await page.goto(BASE);
    await page.waitForFunction(()=>window.BacStudio&&window.BacCampus?.inspect().navigation?.overview);
    await page.waitForFunction(()=>BacStudio.inspect().runtime.version==='SCENARIO TEST FIXTURE');
    await api('plan','settings/connections',{source:'api',provider:'nvidia',apiKey:'fixture-key',model:'fixture-local-model'});
    await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.modelConnections?.connections.api.ready);
    await page.locator('.world-campus-room[data-world-room=workshop]').click();
    await page.locator('#studio-name').fill('Isolation QA');await page.locator('#studio-create').click();
    await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Isolation QA'&&!BacCampus.inspect().arrival);
    await choose('plan');await upload();
    await page.locator('[data-crew-document="inbox/notes.md"]').uncheck();
    await choose('event-brief');await api('event-brief','upload',{crewRole:0,name:'notes.md',content:'Event notes: attendee count 25.'});
    await page.locator('[data-crew-document="inbox/notes.md"]').waitFor();
    assert.equal(await page.locator('[data-crew-document="inbox/notes.md"]').isChecked(),true,'Document selection must be separate per scenario');
    await choose('plan');assert.equal(await page.locator('[data-crew-document="inbox/notes.md"]').isChecked(),false);
    await reset('plan');await upload();
    assert.equal(await page.locator('[data-crew-document="inbox/notes.md"]').isChecked(),true,'Reset must discard stale excluded-file choices');
    assert.equal((await state('event-brief')).crewDocuments.length,1,'Other scenario upload must survive');
    console.log('PASS documents: independent selections, same-name reupload after reset, other scenario preserved');
    await model('plan',LIGHTNING);await choose('event-brief');
    assert.equal((await state('event-brief')).teamSelections.find(r=>r.role===0).id,'fixture-local-model');
    await model('event-brief',LIGHTNING);await model('event-brief',ULTRA);
    await choose('plan');assert.equal((await state('plan')).teamSelections.find(r=>r.role===0).id,LIGHTNING);
    await page.reload();await page.waitForFunction(()=>window.BacCampus?.inspect().navigation?.overview);await choose('plan');
    assert.equal((await state('plan')).teamSelections.find(r=>r.role===0).id,LIGHTNING);
    console.log('PASS models: search, apply, scenario isolation, reload persistence');
    await page.route('**/api/state',route=>route.request().headers()['x-bac-scenario']==='event-brief'?route.fulfill({status:503,json:{error:'Fixture: temporary failure'}}):route.continue());
    await page.locator('.world-room-map [data-world-scenario="event-brief"]').click();
    await page.waitForFunction(()=>BacCampus.inspect().navigation.activeScenario==='plan');
    await page.unroute('**/api/state');
    assert.equal((await state('plan')).crewDocuments.length,1);
    await choose('event-brief');await choose('plan');
    console.log('PASS navigation: failed switch restores previous scenario, retry succeeds');
    const cases = [
      ['SOLO_QA: explain a simple concept','complete',0],
      ['SINGLE_QA: suggest a desktop layout','complete',1],
      ['CALCULATOR_QA: analyze supplied numbers, build a calculator, include independent review','complete',3],
      ['RESEARCH_QA: research and review public information','complete',2],
      ['PARTIAL_QA: create a prototype and deploy it','partial',3],
      ['UNSUPPORTED_QA: deploy with an unavailable tool','unavailable',0],
      ['REVISION_QA: analyze these totals with review and correct a blocking error','complete',2],
    ];
    for(const [prompt,outcome,count] of cases){
      const job=await plan(prompt);
      assert.equal(job.payload.collaboration.outcome,outcome);
      assert.equal(job.payload.collaboration.tasks.length,count);
      if(prompt.startsWith('CALCULATOR'))assert(job.payload.collaboration.outputs['4'],'Explicit reviewer must deliver');
      if(prompt.startsWith('REVISION'))assert(job.payload.collaboration.revision,'Reviewer feedback must request a bounded correction');
      console.log('PASS plan:',prompt.split(':')[0],outcome,count+' specialists');
    }
    const codeJob=(await state('plan')).crewChats.find(j=>j.payload.prompt.includes('CALCULATOR_QA'));
    const html=Object.values(codeJob.payload.collaboration.webpages).flat()[0];assert(html);
    const file=await api('plan','file?job='+codeJob.id+'&path='+encodeURIComponent(html));
    assert(file.content.includes('Calculator QA'),'Cody artifact must be readable');
    await choose('event-brief');
    await page.locator('#studio-crew-prompt').fill('event hello [fixture:slow]');await page.locator('#studio-crew-send').click();
    await page.waitForFunction(()=>document.querySelector('#studio-crew-prompt').disabled);
    await reset('event-brief');assert.equal((await state('plan')).crewChats.length,cases.length);
    console.log('PASS event: reset while active, Open Task history/results preserved');
    await choose('plan');await page.locator('#studio-crew-prompt').fill('hello [fixture:error]');await page.locator('#studio-crew-send').click();
    await waitFor(async()=> (await state('plan')).crewChats.some(j=>j.status==='error'), 'visible model error');
    await page.waitForFunction(()=>!document.querySelector('#studio-crew-prompt').disabled);
    await page.locator('#studio-crew-prompt').fill('hello [fixture:slow]');await page.locator('#studio-crew-send').click();
    const stop=page.locator('#studio-crew-conversation [data-crew-chat-stop]').last();await stop.click();
    await waitFor(async()=>!(await state('plan')).crewChats.some(active),'stop drains work');
    await page.waitForFunction(()=>!document.querySelector('#studio-crew-prompt').disabled);
    console.log('PASS recovery: error and Stop both restore composer');
    await choose('event-brief');await page.locator('#studio-crew-prompt').fill('event hello');await page.locator('#studio-crew-send').click();
    await waitFor(async()=> (await state('event-brief')).crewChats.some(j=>j.status==='done'),'event reply');
    await choose('plan');
    await page.locator('#studio-crew-prompt').fill('/plan ASSEMBLY_QA: research and build a desktop page with review');await page.locator('#studio-crew-send').click();
    await waitFor(async()=> (await state('plan')).crewChats.some(j=>active(j)&&j.payload.collaboration?.activeRole===8),'researcher starts');
    assert.equal(await page.locator('#studio-crew-prompt').isDisabled(),true);
    await choose('event-brief');assert((await state('plan')).crewChats.some(active),'Scenario switch must not stop other work');
    assert.equal(await page.locator('#studio-crew-prompt').isDisabled(),false);
    await choose('plan');await reset('plan');
    assert((await state('event-brief')).crewChats.some(j=>j.status==='done'),'Reset during plan must preserve event history');
    console.log('PASS running plan: switch preserves work, Casey is locked, reset stops it without clearing Event Brief');
    await api('plan','jobs',{kind:'crew-chat',crewRole:0,prompt:'hello [fixture:slow]'});
    await choose('event-brief');await api('event-brief','jobs',{kind:'crew-chat',crewRole:0,prompt:'event hello [fixture:slow]'});
    await reset('event-brief',true);
    for(const scenario of ['plan','event-brief']){const s=await state(scenario);assert.equal(s.crewChats.length,0);assert.equal(s.crewDocuments.length,0);assert.equal(s.scenarios.find(r=>r.id===scenario).hasWork,false);assert.equal(s.teamSelections.find(r=>r.role===0).id,scenario==='plan'?LIGHTNING:ULTRA);}
    assert.deepEqual(errors,[]);
    console.log('PASS Reset all: both histories/documents cleared, lounge removed, both model choices retained; no browser errors');
  } catch(error) {await page.screenshot({path:'/tmp/scenario-isolation-failure.png'});throw error;}
  finally {clearInterval(leaseTimer);await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
