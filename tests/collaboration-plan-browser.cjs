// Command scope regression checks. Run against fixture_scenarios.py only.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[],submitted=[];
  page.on('pageerror',e=>{errors.push(e.message);console.error('PAGE ERROR',e.message);});
  page.on('request',r=>{if(r.method()==='POST'&&new URL(r.url()).pathname==='/api/jobs')submitted.push(r.postDataJSON());});
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8083');
  await page.waitForFunction(()=>window.BacStudio&&window.BacCampus?.inspect().navigation?.overview);
  assert.equal(await page.evaluate(()=>BacStudio.inspect().runtime.version),'SCENARIO TEST FIXTURE');
  await page.locator('.world-campus-room[data-world-room=workshop]').click();
  await page.locator('#studio-name').fill('Command fixture guest');await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Command fixture guest'&&!BacCampus.inspect().arrival);
  const lounge=async()=>{await page.locator('.world-room-map [data-world-room=lounge]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);};
  const choose=async id=>{await page.locator('.world-room-map [data-world-scenario="'+id+'"]').click();await page.waitForFunction(id=>BacCampus.inspect().navigation.activeScenario===id&&!BacCampus.inspect().navigation.travelling,id);await page.locator('#studio-crew-prompt').waitFor({state:'visible'});};
  const personal=page.locator('#studio-prompt'),crew=page.locator('#studio-crew-prompt'),menu=page.locator('#studio-crew-prompt-commands');
  await lounge();assert(!/\/plan/.test(await personal.getAttribute('placeholder')));
  await personal.fill('/');assert.equal(await page.locator('#studio-prompt-commands').count(),0);
  for(const prompt of ['/plan Build a page','  \n /PLANS\nAnalyze this']){
   await personal.fill(prompt);const count=submitted.length;await page.locator('#studio-send').click();
   assert.match(await page.locator('#studio-chat-error').innerText(),/Casey in Open Task/);
   assert.equal(await personal.inputValue(),prompt);assert.equal(submitted.length,count);
   assert.equal(await page.evaluate(()=>BacStudio.inspect().room),'lounge');
  }
  // Ordinary words and mentions are still direct Lounge messages.
  for(const prompt of ['Please plan a workshop','Explain /plan','/planet facts']){
   await personal.fill(prompt);assert.equal(await page.locator('#studio-chat-error').isVisible(),false);await page.locator('#studio-send').click();
   await page.waitForFunction(()=>document.querySelector('#studio-prompt').value==='');
   assert.equal(submitted.at(-1).kind,'chat');assert.equal(submitted.at(-1).prompt,prompt);
   await page.waitForFunction(()=>BacStudio.inspect().jobs.every(j=>!['queued','running','stopping'].includes(j.status)));
  }
  // A second Lounge agent enables the Run all path, which must reject too.
  await page.evaluate(async()=>{const s=await fetch('/api/session').then(r=>r.json());const r=await fetch('/api/agents',{method:'POST',headers:{'Content-Type':'application/json','X-BaC-CSRF':s.csrf},body:JSON.stringify({name:'Second guest',skills:['web']})});if(!r.ok)throw Error(await r.text());await BacStudio.refresh();});
  await personal.fill('/plan Do not fan out');await page.locator('#studio-run-options').click();
  const beforeAll=submitted.length;await page.locator('#studio-send-all').click();
  assert.match(await page.locator('#studio-chat-error').innerText(),/Casey in Open Task/);assert.equal(submitted.length,beforeAll);
  await choose('plan');assert.equal(await crew.inputValue(),'/plan ');
  for(const prefix of ['/','/pl']){await crew.fill(prefix);await menu.waitFor({state:'visible'});await crew.press('Enter');assert.equal(await crew.inputValue(),'/plan ');assert.equal(await menu.isVisible(),false);}
  await crew.fill('/p');await menu.getByRole('option').click();assert.equal(await crew.inputValue(),'/plan ');
  await crew.fill('/pla');await crew.press('Escape');assert.equal(await menu.isVisible(),false);
  await crew.fill('/plan');assert.equal(await page.locator('#studio-crew-send').isDisabled(),true);
  await crew.fill('/plans SINGLE_QA Design a simple desktop page');await page.locator('#studio-crew-send').click();
  await page.waitForFunction(async()=>{const s=await fetch('/api/state',{headers:{'X-BaC-Scenario':'plan'}}).then(r=>r.json());return s.crewChats.some(j=>j.payload.collaboration&&j.status==='done');});
  await page.waitForFunction(()=>!document.querySelector('#studio-crew-prompt').disabled);
  await page.waitForFunction(()=>document.querySelector('#studio-crew-prompt').value==='/plan ');assert.equal(submitted.at(-1).crewRole,0);
  await page.locator('[data-crew-member="7"]').click();
  assert.equal(await crew.inputValue(),'');assert(!/\/plan/.test(await crew.getAttribute('placeholder')));
  await crew.fill('/pl');assert.equal(await menu.isVisible(),false);
  await crew.fill('/plan Reassign');const beforeSpecialist=submitted.length;await page.locator('#studio-crew-send').click();
  assert.match(await page.locator('#studio-crew-chat-error').innerText(),/Casey in Open Task/);assert.equal(submitted.length,beforeSpecialist);
  await crew.fill('Explain your design');assert.equal(await page.locator('#studio-crew-chat-error').isVisible(),false);await page.locator('#studio-crew-send').click();await page.waitForFunction(()=>document.querySelector('#studio-crew-prompt').value==='');assert.equal(submitted.at(-1).crewRole,7);
  await choose('event-brief');assert.equal(await crew.inputValue(),'');assert(!/\/plan/.test(await crew.getAttribute('placeholder')));
  await crew.fill('/');assert.equal(await menu.isVisible(),false);
  await crew.fill('/plan');const beforeEvent=submitted.length;await page.locator('#studio-crew-send').click();
  assert.match(await page.locator('#studio-crew-chat-error').innerText(),/Plan an event/);assert.equal(submitted.length,beforeEvent);
  assert.equal(await page.locator('#studio-room-action').innerText(),'Plan an event');
  // Model readiness belongs to its own area, including after navigating back.
  let loungeReady=false,teamReady=true;
  await page.route('**/api/runtime*',async route=>{const response=await route.fetch(),body=await response.json();await route.fulfill({response,json:{...body,ready:loungeReady,model:loungeReady,teamReady,teamModel:teamReady}});});
  await page.waitForFunction(()=>!BacStudio.inspect().runtime.ready,null,{timeout:15000});
  await lounge();assert.equal(await personal.isDisabled(),true);assert.match(await page.locator('.campus-sim').innerText(),/Model not connected/);assert.equal(await page.locator('#studio-send').isDisabled(),true);
  await choose('plan');assert.equal(await crew.isDisabled(),false);assert.match(await page.locator('.campus-sim').innerText(),/Ready/);
  loungeReady=true;teamReady=false;
  await page.waitForFunction(()=>BacStudio.inspect().runtime.ready&&!BacStudio.inspect().runtime.teamReady,null,{timeout:15000});
  assert.equal(await crew.isDisabled(),true);await lounge();assert.equal(await personal.isDisabled(),false);
  assert.match(await page.locator('.campus-sim').innerText(),/Ready/);await personal.fill('Hello');assert.equal(await page.locator('#studio-chat-error').isVisible(),false);assert.equal(await page.locator('#studio-send').isDisabled(),false);
  assert(!/\/plan/.test(await personal.getAttribute('placeholder')));
  await page.screenshot({path:'/tmp/lounge-command-scope.png'});
  assert.deepEqual(errors,[]);
  console.log('PASS: Lounge hints, no autocomplete or redirect, aliases, preserved drafts, direct chat, Run all, Casey suggestions/plan, specialist and Event Brief guards, independent model readiness, immediate connection badge refresh, cleared command guidance, zero browser errors.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
