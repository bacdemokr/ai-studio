// Real UI/HTTP/SQLite coverage with disposable data and simulated inference.
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const port=Number(process.env.BAC_TEST_PORT||18264),host=process.env.BAC_TEST_HOST||'127.0.0.1',url='http://'+host+':'+port;
 const server=spawn('python3',['-B','tests/fixture_personal_models.py'],{env:{...process.env,BAC_TEST_PORT:String(port),BAC_TEST_VISITOR_DELAY:'6'},stdio:['ignore','pipe','pipe']});let browser;
 server.stderr.on('data',()=>{});
 try{
  await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Fixture startup timed out')),15000);server.stdout.on('data',b=>{if(b.toString().includes('PERSONAL MODEL FIXTURE READY')){clearTimeout(timer);resolve();}});server.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code));});});
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1600,height:1050},reducedMotion:'reduce'}),errors=[],writes=[];
  let mutationHeaders;page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST'&&r.url().includes('/api/'))mutationHeaders=r.headers();if(r.url().endsWith('/api/team-model'))writes.push(r.postDataJSON());});
  const navigate=async scenario=>{await page.locator('.world-room-map [data-world-scenario="'+scenario+'"]').click();await page.waitForFunction(s=>BacCampus.inspect().navigation.activeScenario===s&&!BacCampus.inspect().navigation.travelling,scenario);};
  const badge=page.locator('#studio-crew-model'),picker=page.locator('.team-model-dialog'),search=picker.locator('input'),pick=id=>picker.locator('[data-model-choice="'+id+'"]');
  const state=()=>page.evaluate(async()=>await(await fetch('/api/state',{headers:{'X-BaC-Agent':BacStudio.inspect().agentId,'X-BaC-Scenario':'plan'}})).json());
  const choose=async id=>{await badge.click();await search.fill(id);await pick(id).click();await picker.waitFor({state:'hidden'});await page.waitForFunction(id=>document.querySelector('#studio-crew-model').textContent===id,id);};
  await page.goto(url);await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.personalModels);
  await navigate('plan');await page.waitForFunction(()=>document.querySelector('#studio-crew-name').textContent==='Casey');
  assert(await badge.isEnabled(),'Idle Casey model badge should open the picker');
  const initial=(await state()).teamSelections;
  await choose('fixture-b');assert.deepEqual(writes.at(-1),{role:0,model:'fixture-b'});
  const changed=(await state()).teamSelections;
  assert.equal(changed.find(m=>m.role===0).id,'fixture-b');assert.deepEqual(changed.filter(m=>m.role!==0),initial.filter(m=>m.role!==0));
  await badge.focus();await page.keyboard.press('Enter');await search.fill('fixture-a');await search.press('ArrowDown');assert(await pick('fixture-a').evaluate(n=>n===document.activeElement));await page.keyboard.press('Escape');await picker.waitFor({state:'hidden'});
  assert.equal(await badge.innerText(),'fixture-b');
  // The next direct reply actually uses Casey's chosen model in this fixture.
  await page.locator('#studio-crew-prompt').fill('Hello');await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>document.querySelector('#studio-crew-conversation').textContent.includes('Simulated model: fixture-b'));
  await page.waitForFunction(()=>!document.querySelector('#studio-crew-model').disabled);await choose('fixture-a');
  await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.personalModels);await navigate('plan');
  await page.waitForFunction(()=>document.querySelector('#studio-crew-name').textContent==='Casey'&&document.querySelector('#studio-crew-model').textContent==='fixture-a');assert(await badge.isEnabled());
  await navigate('event-brief');assert(await badge.isDisabled(),'Event Brief retains its scenario-wide model');assert.equal(await badge.innerText(),'fixture-a');
  await navigate('plan');await choose('fixture-b');await navigate('event-brief');assert.equal(await badge.innerText(),'fixture-a','Casey selection must not change Event Brief');await navigate('plan');
  // Existing specialist-list edits and the new passport badge share one picker.
  await page.locator('#studio-crew-team-mode [data-team-mode=mixed]').click();await page.locator('#studio-standby').evaluate(n=>n.open=true);
  await page.locator('[data-standby-model="5"]').click();await search.fill('fixture-a');await pick('fixture-a').click();await picker.waitFor({state:'hidden'});
  assert.deepEqual(writes.at(-1),{role:5,model:'fixture-a'});assert.equal(await badge.innerText(),'fixture-b');
  await page.locator('#studio-standby').evaluate(n=>n.open=false);
  await page.locator('#studio-crew-prompt').fill('/goal Build a counter.');await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>document.querySelector('#studio-crew-conversation').textContent.includes('The team delivered the counter.'));
  await page.locator('[data-campus-agent="5"]').click();await page.waitForFunction(()=>document.querySelector('#studio-crew-name').textContent==='Cody'&&!document.querySelector('#studio-crew-model').disabled);
  await choose('fixture-b');assert.deepEqual(writes.at(-1),{role:5,model:'fixture-b'});
  await page.locator('[data-campus-agent="0"]').click();await page.waitForFunction(()=>document.querySelector('#studio-crew-name').textContent==='Casey');assert.equal(await badge.innerText(),'fixture-b');
  // Reserve a hired agent, then complete a real dispatcher job while Casey's picker is open.
  await page.evaluate(()=>BacStudio.setRoom('workshop'));await page.locator('#studio-name').fill('Pixel');await page.getByRole('button',{name:'Slack Announcer',exact:true}).click();await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Pixel'&&BacStudio.inspect().agents.every(a=>!a.pending));await navigate('plan');
  const start=async()=>{const headers={...mutationHeaders,'x-bac-agent':await page.evaluate(()=>BacStudio.inspect().agentId),'x-bac-scenario':'plan'};delete headers['content-length'];const r=await page.request.post(url+'/api/jobs',{headers,data:{kind:'crew-chat',crewRole:0,teamMode:'hired',prompt:'/goal Have Pixel build a counter.'}});assert.equal(r.status(),200,await r.text());return r.json();};
  await badge.click();await search.fill('fixture');await start();await page.evaluate(()=>BacStudio.refresh());
  assert(await pick('fixture-a').isDisabled(),'An already open picker must lock when a task starts');assert(await badge.isDisabled());
  await picker.locator('[data-model-close]').click();await page.waitForFunction(()=>document.querySelector('#studio-crew-conversation').textContent.includes('The team delivered the counter.'));await page.waitForFunction(()=>!document.querySelector('#studio-crew-model').disabled);await choose('fixture-a');
  // Server protection also covers a task starting between the UI check and save.
  await badge.click();await search.fill('fixture');
  await page.route('**/api/team-model',async route=>{await start();await route.continue();},{times:1});
  await pick('fixture-b').click();await picker.locator('.team-model-error').waitFor();assert.match(await picker.locator('.team-model-error').innerText(),/pending|current|finish/i);
  assert.equal((await state()).teamSelections.find(m=>m.role===0).id,'fixture-a');
  await page.evaluate(()=>BacStudio.refresh());assert(await pick('fixture-b').isDisabled());
  await picker.locator('[data-model-close]').click();await page.waitForFunction(()=>!document.querySelector('#studio-crew-model').disabled);
  // A hired participant still edits its personal model, not the borrowed role slot.
  await page.locator('[data-campus-agent="5"]').click();await page.waitForFunction(()=>document.querySelector('#studio-crew-name').textContent==='Pixel');
  assert(await badge.isEnabled());const count=writes.length;await badge.click();await search.fill('fixture-b');await pick('api/nvidia/fixture-b').click();await picker.waitFor({state:'hidden'});assert.equal(writes.length,count);
  // Losing API readiness locks built-in choices, including an already open picker.
  await page.locator('[data-campus-agent="0"]').click();await page.waitForFunction(()=>document.querySelector('#studio-crew-name').textContent==='Casey');
  await badge.click();await search.fill('fixture');await page.route('**/api/state',async route=>{const r=await route.fetch(),data=await r.json();data.teamConnection={...data.teamConnection,ready:false};await route.fulfill({json:data});});await page.evaluate(()=>BacStudio.refresh());assert(await pick('fixture-b').isDisabled());
  await page.unroute('**/api/state');await page.evaluate(()=>BacStudio.refresh());assert(await pick('fixture-b').isEnabled());await picker.locator('[data-model-close]').click();
  await badge.click();await search.fill('fixture');if(process.env.BAC_TEST_SCREENSHOT)await page.screenshot({path:process.env.BAC_TEST_SCREENSHOT});
  assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:true,host,checks:['Casey badge and keyboard picker','per-role persistence and next-response model','post-completion unlock','Event Brief isolation','existing specialist list','open-picker and save races','hired personal models preserved','disconnect/reconnect']}));
 }finally{if(browser)await browser.close();server.kill('SIGTERM');}
})().catch(e=>{console.error(e);process.exitCode=1;});
