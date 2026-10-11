const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const port=Number(process.env.BAC_TEST_PORT||18240);
 const server=spawn('python3',['-B','tests/fixture_visitor_teams.py'],{env:{...process.env,BAC_TEST_PORT:String(port),BAC_TEST_VISITOR_DELAY:'10'},stdio:['ignore','pipe','inherit']});let browser;
 try{
  await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Fixture startup timed out')),15000);server.stdout.on('data',b=>{if(b.toString().includes('VISITOR FIXTURE READY')){clearTimeout(timer);resolve();}});server.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code));});});
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1600,height:1050},reducedMotion:'reduce'}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+port);await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
  const choose=async id=>{await page.locator('.world-room-map [data-world-scenario="'+id+'"]').click();await page.waitForFunction(id=>BacCampus.inspect().navigation.activeScenario===id&&!BacCampus.inspect().navigation.travelling,id);};
  const state=()=>page.evaluate(async()=>{const response=await fetch('/api/state',{headers:{'X-BaC-Agent':BacStudio.inspect().agentId,'X-BaC-Scenario':'plan'}});if(!response.ok)throw Error(await response.text());return response.json();});
  const toggle=page.getByRole('switch',{name:'Include hired agents'});
  // A first-time visitor can still use the backup team without hiring anyone.
  await choose('plan');assert.equal(await toggle.isChecked(),false);await page.locator('#studio-crew-prompt').fill('/goal Build a counter.');await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>document.querySelector('#studio-crew-conversation').textContent.includes('The team delivered the counter.'));
  assert.match(await page.locator('#studio-crew-conversation').innerText(),/Cody/);
  await page.evaluate(()=>BacStudio.setRoom('workshop'));await page.locator('#studio-name').fill('Pixel');
  await page.getByRole('button',{name:'Weather buddy',exact:true}).click();
  await page.locator('input[name="protection"][value="openshell"]').check();
  await page.locator('#studio-create').click();await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Pixel');
  const original=await page.evaluate(()=>BacStudio.inspect().profile);
  await choose('plan');await page.locator('#studio-crew-prompt').fill('/goal Pixel이 Coding작업들을 대신하게 해줘. Build a counter.');await page.locator('#studio-crew-send').click();
  await page.locator('#studio-crew-chat-error').filter({hasText:'Turn on Include hired agents to assign Pixel'}).waitFor({state:'visible'});
  assert.equal((await state()).crewChats.filter(j=>j.payload.collaboration).length,1);
  assert.match(await page.locator('#studio-crew-prompt').inputValue(),/Pixel/);
  await toggle.check();await choose('event-brief');assert.equal(await toggle.isVisible(),false);
  await choose('plan');assert.equal(await toggle.isChecked(),true);
  await page.screenshot({path:'/tmp/bac-hired-team-toggle.png'});
  await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>document.querySelectorAll('[data-collaboration-job]').length>=2&&document.querySelector('#studio-crew-conversation').textContent.includes('Hired team: Pixel'));
  assert.equal(await toggle.isChecked(),true);assert.equal(await toggle.isDisabled(),true);
  await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().profile?.name==='Pixel');
  await choose('plan');assert.equal(await toggle.isChecked(),true);assert.equal(await toggle.isDisabled(),true);
  await page.waitForFunction(()=>BacCampus.inspect().visitorTravel?.some(v=>v.name==='Pixel'&&v.phase==='working'));
  await page.locator('[data-visitor-agent]').filter({hasText:'Pixel'}).click();
  await page.waitForFunction(()=>document.querySelector('#studio-crew-name').textContent==='Pixel');
  assert.equal(await toggle.isVisible(),false);
  assert.equal(await page.evaluate(()=>BacCampus.inspect().residents.find(r=>r.key===BacStudio.inspect().agentId).visible),false);
  await page.screenshot({path:'/tmp/bac-visitor-working-ui.png'});
  let job;for(let i=0;i<150;i++){const value=await state();job=value.crewChats.find(j=>j.payload.collaboration?.visitorBindings?.[5]?.name==='Pixel');if(job?.status==='done')break;await page.waitForTimeout(100);}
  assert.equal(job.status,'done');assert.equal(job.payload.includeHiredAgents,true);assert.equal(job.payload.collaboration.outputs[5].agentId,original.id);
  await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.length===0&&BacCampus.inspect().residents.find(r=>r.key===BacStudio.inspect().agentId).visible);
  const value=await state();assert.deepEqual(value.profile.skills,original.skills);assert.equal(value.agents.length,1);
  const html=job.payload.collaboration.webpages[5][0];
  await page.locator('[data-preview-file="'+html+'"]').filter({visible:true}).first().click();
  await page.locator('#studio-app-frame[data-ready="true"]').waitFor({state:'visible'});const frame=page.frameLocator('#studio-app-frame');await frame.getByRole('button',{name:'0',exact:true}).click();assert.equal(await frame.getByRole('button').innerText(),'1');await page.locator('#studio-dialog-close').click();
  await page.locator('[data-campus-agent="5"]').click();
  await page.waitForFunction(()=>document.querySelector('#studio-crew-name').textContent==='Pixel');
  assert(!await page.locator('[data-standby-role="5"]').textContent().then(text=>text.includes('With team')));
  await page.locator('#studio-crew-policy').click();
  await page.waitForFunction(()=>document.querySelector('#studio-policy-content').textContent.includes('Access applies only to Pixel'));
  assert.equal(await page.locator('#studio-policy-agent option:checked').innerText(),'Pixel');
  await page.locator('#studio-surface-close').click();
  await page.locator('.studio-team-utilities button').filter({hasText:/^Files$/}).click();
  await page.waitForFunction(()=>document.querySelector('#studio-workspace-browser h3')?.textContent==='Pixel files');
  await page.waitForFunction(()=>document.querySelector('#studio-file-folders')?.textContent.includes('counter.html'));
  assert.match(await page.locator('#studio-file-folders').innerText(),/counter.html/);await page.locator('#studio-dialog-close').click();
  await page.locator('#studio-crew-name').click();await page.waitForFunction(()=>document.querySelector('#studio-identity-viewer h3')?.textContent==='Pixel');await page.locator('#studio-dialog-close').click();
  // Direct follow-up must reach Pixel, not the fallback Cody occupying this task slot.
  await page.locator('#studio-crew-prompt').fill('Hello Pixel.');await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>BacStudio.inspect().room==='lounge'&&document.querySelector('#studio-conversation').textContent.includes('Fixture personal reply.'));
  await choose('event-brief');assert.equal(await page.locator('#studio-crew-name').innerText(),'Riley');
  await choose('plan');await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().profile?.name==='Pixel');
  assert.equal((await state()).crewChats.find(j=>j.id===job.id).payload.collaboration.visitorBindings[5].name,'Pixel');
  await choose('plan');
  assert.equal(await toggle.isChecked(),false);
  await page.waitForFunction(()=>document.querySelector('[data-campus-agent="5"] b')?.textContent==='Pixel');
  await page.locator('[data-campus-agent="5"]').click();
  await page.waitForFunction(()=>document.querySelector('#studio-crew-name').textContent==='Pixel');
  // Switching off after a hired-team run must not reuse that run's identities or reservations.
  await page.locator('[data-campus-agent="0"]').click();
  await page.waitForFunction(()=>document.querySelector('#studio-crew-name').textContent==='Casey');
  await page.locator('#studio-crew-prompt').fill('/goal Build a counter.');await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>BacCampus.inspect().crewLabels?.some(c=>c.name==='Cody')||document.querySelector('[data-campus-agent="5"] b')?.textContent==='Cody');
  let backup;for(let i=0;i<100;i++){backup=(await state()).crewChats.find(j=>j.id!==job.id&&j.payload.includeHiredAgents===false&&j.created>job.created);if(backup?.status==='done')break;await page.waitForTimeout(100);}
  assert.equal(backup.status,'done');assert.equal(backup.payload.roster,undefined);assert.equal(backup.payload.roundtable,undefined);
  assert.equal(backup.payload.collaboration.visitorBindings,undefined);
  assert.equal(await page.evaluate(()=>BacCampus.inspect().visitorTravel.length),0);
  await toggle.check();await page.locator('#studio-bac-reset').click();await page.locator('#studio-team-reset-confirm').click();
  await page.waitForFunction(()=>!document.querySelector('#studio-crew-include-hired').checked&&!document.querySelector('#studio-crew-include-hired').disabled);
  assert.equal((await state()).profile.id,original.id);
  assert.deepEqual(errors,[]);await page.screenshot({path:'/tmp/bac-visitor-teams-browser.png'});
  console.log('PASS: default OFF, named-agent opt-in, locked running choice, ON hired Pixel coding, identity/policy/files, generated preview, Event Brief isolation, reload OFF, and ON-to-OFF built-in team without reservations. Model inference simulated.');
 }finally{if(browser)await browser.close();if(server.exitCode===null){server.kill('SIGTERM');await new Promise(resolve=>server.once('exit',resolve));}}
})().catch(error=>{console.error(error);process.exitCode=1;});
