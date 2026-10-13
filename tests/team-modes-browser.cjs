const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const port=Number(process.env.BAC_TEST_PORT||18285),server=spawn('python3',['-B','tests/fixture_visitor_teams.py'],{env:{...process.env,BAC_TEST_PORT:String(port),BAC_TEST_VISITOR_DELAY:'6'},stdio:['ignore','pipe','inherit']});let browser;
 try{
  await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('Fixture timeout')),15000);server.stdout.on('data',b=>{if(b.toString().includes('VISITOR FIXTURE READY')){clearTimeout(t);resolve();}});server.once('exit',()=>reject(Error('Fixture exited')));});
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1600,height:1050},reducedMotion:'reduce'}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+port);await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
  const choose=async id=>{await page.locator('.world-room-map [data-world-scenario="'+id+'"]').click();await page.waitForFunction(id=>BacCampus.inspect().navigation.activeScenario===id&&!BacCampus.inspect().navigation.travelling,id);};
  const teamControl=page.locator('#studio-crew-team-mode');
  const mode={selectOption:async value=>teamControl.locator('[data-team-mode="'+value+'"]').click(),inputValue:async()=>teamControl.locator('[aria-pressed=true]').getAttribute('data-team-mode'),isDisabled:async()=>teamControl.locator('button').first().isDisabled(),isVisible:async()=>teamControl.isVisible()};
  await choose('plan');assert.equal(await mode.inputValue(),'hired');assert.deepEqual(await teamControl.locator('button').allTextContents(),['Hired only','Hired + Standby']);
  await page.locator('#studio-crew-prompt').fill('/goal Build a counter.');await page.locator('#studio-crew-send').click();
  await page.locator('#studio-crew-chat-error').filter({hasText:'No hired agents are ready'}).waitFor({state:'visible'});
  assert.equal(await page.locator('#studio-crew-chat-error').innerText(),'No hired agents are ready. Hire an agent or choose Hired + Standby.');
  for(const [name,role] of [['Pixel','Programmer'],['Orbit','Web researcher']]){
   await page.locator('.world-room-map [data-world-room=workshop]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
   await page.locator('#studio-name').fill(name);await page.getByRole('button',{name:role,exact:true}).click();await page.locator('input[name=protection][value=standard]').check();
   assert(await page.locator('#studio-skill-picker input[value="'+(role==='Programmer'?'builder':'web')+'"]').isChecked());
   await page.locator('#studio-create').click();await page.waitForFunction(name=>BacStudio.inspect().profile?.name===name&&BacStudio.inspect().room==='lounge',name);
  }
  await choose('plan');await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.length===2&&BacCampus.inspect().visitorTravel.every(v=>v.phase==='seated'));
  assert.equal(await mode.inputValue(),'hired');assert.equal(await page.locator('[data-standby-role="5"]').count(),0);
  assert.equal(await page.evaluate(()=>BacCampus.inspect().residents.filter(r=>r.visible).length),0);
  await page.screenshot({path:'/tmp/bac-hired-only-benches.png'});
  // Room-only movement has no pending model calls.
  const state=()=>page.evaluate(async()=>{const r=await fetch('/api/state',{headers:{'X-BaC-Agent':BacStudio.inspect().agentId,'X-BaC-Scenario':'plan'}});return r.json();});
  assert(!(await state()).crewChats.some(j=>['queued','running'].includes(j.status)));
  await page.locator('#studio-crew-prompt').fill('/goal Have Pixel do the coding. Build a counter.');await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.some(v=>v.name==='Pixel'&&v.phase==='working'));
  assert(await mode.isDisabled());assert.equal(await mode.inputValue(),'hired');
  assert.equal(await page.evaluate(()=>BacCampus.inspect().visitorTravel.find(v=>v.name==='Orbit')?.phase),'seated');
  await page.screenshot({path:'/tmp/bac-hired-only-working.png'});
  await page.waitForFunction(()=>!document.querySelector('#studio-crew-team-mode button').disabled);
  await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.length===2&&BacCampus.inspect().visitorTravel.every(v=>v.phase==='seated'));
  const job=(await state()).crewChats.find(j=>j.payload.teamMode==='hired');assert.equal(job.status,'done');assert.equal(job.payload.collaboration.visitorBindings[5].name,'Pixel');
  await mode.selectOption('mixed');await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.length===2&&BacCampus.inspect().visitorTravel.every(v=>v.phase==='seated'));
  await choose('event-brief');assert.equal(await mode.isVisible(),false);assert.equal(await page.locator('#studio-crew-name').innerText(),'Riley');
  await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.length===0);
  await choose('plan');await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.length===2);
  await page.locator('#studio-bac-reset').click();await page.locator('#studio-team-reset-confirm').click();
  await page.waitForFunction(()=>document.querySelector('#studio-crew-team-mode [aria-pressed=true]').dataset.teamMode==='hired'&&!document.querySelector('#studio-crew-team-mode button').disabled);
  await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.length===2&&BacCampus.inspect().visitorTravel.every(v=>v.phase==='seated'));
  assert.equal((await state()).agents.length,2);
  await mode.selectOption('mixed');await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().profile?.name==='Orbit');await choose('plan');assert.equal(await mode.inputValue(),'hired');
  assert.deepEqual(errors,[]);
  console.log('PASS: empty hired-only, visible Coding/Web research templates, all hires follow and sit, no idle model work, hired-only dispatch, desk movement, return to bench, mode switching, Event Brief isolation, Reset and data preservation. Real browser, simulated inference.');
 }finally{if(browser)await browser.close();if(server.exitCode===null){server.kill('SIGTERM');await new Promise(r=>server.once('exit',r));}}
})().catch(e=>{console.error(e);process.exitCode=1;});
