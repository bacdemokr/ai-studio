// Disposable real-browser settings journey. Model discovery/inference are simulated.
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const host=process.env.BAC_TEST_HOST||'127.0.0.1',port=Number(process.env.BAC_TEST_PORT||18245);
 const server=spawn('python3',['-B','tests/fixture_scenarios.py'],{env:{...process.env,BAC_TEST_HOST:'0.0.0.0',BAC_TEST_PORT:String(port)},stdio:['ignore','pipe','pipe']});
 server.stderr.on('data',()=>{});let browser;
 try{
  await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Fixture startup timed out')),15000);server.stdout.on('data',b=>{if(b.toString().includes('Scenario fixture')){clearTimeout(timer);resolve();}});server.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code));});});
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1440,height:1080},reducedMotion:'reduce'}),errors=[],writes=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(r.url().endsWith('/settings/connections/preferences')&&r.method()==='POST')writes.push(r.postDataJSON());});
  await page.goto('http://'+host+':'+port);await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.version==='SCENARIO TEST FIXTURE');
  const open=async()=>{await page.locator('#studio-config').click();await page.locator('#studio-model-connections').waitFor();await page.locator('#studio-dialog-body').evaluate(n=>n.scrollTop=0);};
  const close=()=>page.locator('#studio-dialog-close').click();
  const select=page.locator('#studio-route-plan'),eventSelect=page.locator('#studio-route-event-brief'),save=page.locator('#studio-connections-save');
  const saveChanges=async()=>{await save.click();await page.waitForFunction(()=>document.querySelector('#studio-connections-status').textContent.startsWith('Saved.'));assert(await save.isDisabled());};
  await open();assert.equal(await page.locator('select[data-route] option[value=auto]').count(),0);assert(!/Automatic/i.test(await page.locator('#studio-model-connections').innerText()));assert(await save.isDisabled());
  assert.equal(await page.locator('#studio-route-lounge').count(),0,'No Lounge override for individually configured agents');
  assert(await eventSelect.isVisible());assert(await select.isVisible());assert.equal(await page.locator('#studio-team-route').count(),0);
  const dialogBox=await page.locator('#studio-dialog').boundingBox();assert(dialogBox.width<=722&&dialogBox.height<=642,'Compact settings dimensions');
  assert(!(await page.locator('#studio-model-connections').innerText()).includes('Stage connections'));
  // Local only, both, API only, neither. An effective fallback never rewrites the chosen preference.
  if(await page.locator('[data-connection-enable=api]').isChecked()){await page.locator('[data-connection-enable=api]').uncheck();await page.waitForFunction(()=>document.querySelector('[data-connection-status=api]').textContent==='Disabled');}
  await page.locator('[data-connection-edit=local]').click();await page.waitForFunction(()=>document.querySelector('#studio-connect-models').options.length>0);
  await page.locator('#studio-connect-model').fill('fixture-local-model');await page.locator('#studio-connect-apply').click();await page.waitForFunction(()=>document.querySelector('#studio-connect-status').textContent==='Connected.');
  assert.match(await page.locator('#studio-connection-plan-effective').innerText(),/Using Local/);assert.equal(await select.inputValue(),'local');assert(await save.isDisabled());
  await page.locator('#studio-connect-cancel').click();await page.locator('[data-connection-edit=api]').click();
  await page.locator('#studio-connect-provider').selectOption('openai');await page.locator('#studio-connect-key').fill('fixture-key-not-real');await page.locator('#studio-connect-model').fill('fixture-local-model');
  await page.locator('#studio-connect-apply').click();await page.waitForFunction(()=>document.querySelector('#studio-connect-status').textContent==='Connected.');
  assert.equal(await page.locator('#studio-connect-key').inputValue(),'');await page.locator('#studio-connect-cancel').click();
  assert.match(await page.locator('#studio-connection-plan-effective').innerText(),/Using External/);
  assert.equal(await select.inputValue(),'api');assert.equal(await eventSelect.inputValue(),'api');assert(await save.isDisabled());await select.selectOption('local');assert.match(await page.locator('#studio-connection-plan-effective').innerText(),/Save to use Local/);await select.selectOption('api');await saveChanges();assert.equal(writes.at(-1).scenarios['event-brief'],'auto');
  await page.locator('[data-connection-enable=api]').uncheck();await page.waitForFunction(()=>document.querySelector('[data-connection-status=api]').textContent==='Disabled');
  assert.match(await page.locator('#studio-connection-plan-effective').innerText(),/External Endpoint unavailable · Using Local/);assert.equal(await select.inputValue(),'local');assert(await select.locator('option[value=api]').isDisabled());assert(await save.isDisabled());
  await page.locator('[data-connection-enable=local]').uncheck();await page.waitForFunction(()=>document.querySelector('#studio-connection-plan-effective').textContent==='No connection ready');
  assert.equal(await select.inputValue(),'');assert(await select.isDisabled());assert.equal(await eventSelect.inputValue(),'');assert(await save.isDisabled());
  await page.locator('[data-connection-enable=api]').check();await page.waitForFunction(()=>document.querySelector('[data-connection-status=api]').textContent==='Ready');
  await page.locator('[data-connection-enable=local]').check();await page.waitForFunction(()=>document.querySelector('[data-connection-status=local]').textContent==='Ready');
  // Each scenario is always directly selectable; neither choice overwrites the other.
  await page.locator('#studio-dialog-body').evaluate(n=>n.scrollTop=0);await page.screenshot({path:'/tmp/bac-model-settings.png'});
  await page.locator('#studio-route-event-brief').selectOption('local');assert(await save.isEnabled());
  // Temporary loss of both connections shows an honest empty state without losing the draft.
  for(const source of ['local','api']){await page.locator('[data-connection-enable='+source+']').uncheck();await page.waitForFunction(source=>document.querySelector('[data-connection-status='+source+']').textContent==='Disabled',source);}
  assert.equal(await eventSelect.inputValue(),'');assert(await eventSelect.isDisabled());
  for(const source of ['local','api']){await page.locator('[data-connection-enable='+source+']').check();await page.waitForFunction(source=>document.querySelector('[data-connection-status='+source+']').textContent==='Ready',source);}
  assert.equal(await eventSelect.inputValue(),'local');assert.match(await page.locator('#studio-connection-event-brief-effective').innerText(),/Save to use Local/);
  await page.locator('[data-connection-tab=location]').click();await page.locator('#studio-settings-model-tab').click();
  await Promise.all([page.waitForResponse(r=>r.url().endsWith('/settings/connections/check')&&r.status()===200),page.locator('#studio-connections-check').click()]);
  assert.equal(await page.locator('#studio-route-event-brief').inputValue(),'local');assert.equal(await page.locator('#studio-route-plan').inputValue(),'api');
  await saveChanges();assert.deepEqual(writes.at(-1),{lounge:'auto',scenarios:{'event-brief':'local',plan:'api'}});
  await close();await open();assert.equal(await select.inputValue(),'api');assert.equal(await eventSelect.inputValue(),'local');assert(await save.isDisabled());
  await page.screenshot({path:'/tmp/bac-model-settings-custom.png'});
  // Narrow view must not clip the controls or labels.
  await page.setViewportSize({width:540,height:900});
  assert(await page.locator('#studio-dialog-body').evaluate(n=>n.scrollWidth<=n.clientWidth+2));
  await select.scrollIntoViewIfNeeded();
  assert(await select.evaluate(n=>{const r=n.getBoundingClientRect();return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===n;}),'Open Task selector stays clickable above the footer');
  await page.screenshot({path:'/tmp/bac-model-settings-narrow.png'});await page.setViewportSize({width:1440,height:1080});
  await select.selectOption('local');await saveChanges();assert.deepEqual(writes.at(-1).scenarios,{'event-brief':'local',plan:'local'});await close();
  const choose=async id=>{await page.locator('.world-room-map [data-world-scenario="'+id+'"]').click();await page.waitForFunction(id=>BacCampus.inspect().navigation.activeScenario===id&&!BacCampus.inspect().navigation.travelling,id);};
  await choose('plan');await page.locator('#studio-local-task-warning').waitFor({state:'visible'});
  await choose('event-brief');assert(!await page.locator('#studio-local-task-warning').isVisible());
  await page.locator('#studio-team-setup').click();await page.locator('#studio-route-plan').selectOption('api');await saveChanges();await close();
  await choose('plan');await page.locator('#studio-local-task-warning').waitFor({state:'hidden'});
  await open();
  for(const tab of ['location','telegram','reset','model']){
   await page.locator('#studio-settings-'+tab+'-tab').click();
   await page.locator('#studio-settings-'+tab+'-panel').waitFor({state:'visible'});
   assert(await page.locator('#studio-dialog-body').evaluate(n=>n.scrollWidth<=n.clientWidth+2));
  }
  await close();
  // Simulate an earlier agent's saved shared choice; the new UI must retain its separate default.
  await page.evaluate(()=>BacStudio.setRoom('workshop'));
  await page.route('**/api/onboard',async route=>{await route.continue({postData:JSON.stringify({...route.request().postDataJSON(),model:'shared'})});});
  await page.locator('#studio-name').fill('Earlier agent');await page.locator('#studio-create').click();await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Earlier agent');
  assert.equal(await page.evaluate(()=>BacStudio.inspect().profile.model),'shared');
  await open();assert.equal(await page.locator('.connection-inherited').evaluate(n=>n.open),false);
  await page.locator('.connection-inherited summary').click();assert.equal(await page.locator('#studio-route-lounge').inputValue(),'local');assert.equal(await page.locator('select[data-route] option[value=auto]').count(),0);
  await page.locator('#studio-route-lounge').selectOption('api');await saveChanges();await close();await open();
  await select.selectOption('local');await saveChanges();assert.equal(writes.at(-1).lounge,'api','Team changes preserve earlier agents');
  await close();await page.reload();await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Earlier agent');
  const [reloaded]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/settings/connections')&&r.request().method()==='GET'),open()]);
  const restored=await reloaded.json();assert.equal(restored.loungePreference,'api','Reload preserves the saved preference');
  // The previous page's credential release can still be in flight; display the actual readiness snapshot.
  const loungeSource=restored.connections.api.ready?'api':'local';
  assert.equal(await select.inputValue(),'local');assert.equal(await eventSelect.inputValue(),'local');await page.locator('.connection-inherited summary').click();assert.equal(await page.locator('#studio-route-lounge').inputValue(),loungeSource);assert(await save.isDisabled());
  await page.locator('.connection-inherited summary').click();await page.locator('#studio-dialog-body').evaluate(n=>n.scrollTop=0);assert(await select.evaluate(n=>{const r=n.getBoundingClientRect();return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===n;}),'Both scenario selectors fit with earlier agents collapsed');await page.screenshot({path:'/tmp/bac-model-settings-existing.png'});
  assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:true,host,checks:['resolved Local/External labels with no Automatic option','independent Event Brief and Open Task selectors','separate choices survive save, reopen and polling','compact Settings dimensions','local/API readiness and honest fallback status','no unnecessary saves','individual and earlier agent settings preserved','scenario-specific Local warnings','narrow layout','no browser errors']}));
 }finally{if(browser)await browser.close();server.kill('SIGTERM');}
})().catch(e=>{console.error(e);process.exitCode=1;});
