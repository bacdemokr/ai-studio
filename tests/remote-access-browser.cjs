// Run against fixture_scenarios.py only. BAC_TEST_REMOTE_URL uses a real LAN
// HTTP origin; otherwise forward a private-IP origin to the disposable server,
// preserving Host/Origin and the browser's HTTP security context. No live model,
// credentials or preview data are used.
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 const local=process.env.BAC_TEST_URL||'http://127.0.0.1:8083';
 const origin=process.env.BAC_TEST_REMOTE_URL||'http://10.0.0.5:8083',page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[],failures=[];
 page.setDefaultTimeout(15000);
 page.on('pageerror',e=>errors.push(e.message));
 page.on('response',r=>{if(r.status()>=400&&new URL(r.url()).pathname.startsWith('/api/'))failures.push([new URL(r.url()).pathname,r.status()]);});
 let keySession='';page.on('request',r=>{keySession=r.headers()['x-bac-key-session']||keySession;});
 if(!process.env.BAC_TEST_REMOTE_URL)await page.route(origin+'/**',async route=>{
  const req=route.request(),headers=await req.allHeaders();headers.host=new URL(origin).host;
  const response=await route.fetch({url:req.url().replace(origin,local),headers});
  await route.fulfill({response});
 });
 const api=(path,body,scenario='plan')=>page.evaluate(async({path,body,scenario,keySession})=>{
  const session=await fetch('/api/session').then(r=>r.json());
  const r=await fetch('/api/'+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-BaC-CSRF':session.csrf,'X-BaC-Scenario':scenario,'X-BaC-Key-Session':keySession},...(body?{body:JSON.stringify(body)}:{})});
  if(!r.ok)throw Error(await r.text());return r.json();
 },{path,body,scenario,keySession});
 const choose=async scenario=>{
  await page.locator('.world-room-map [data-world-scenario="'+scenario+'"]').click();
  await page.waitForFunction(s=>BacCampus.inspect().navigation.activeScenario===s&&!BacCampus.inspect().navigation.travelling,scenario);
 };
 const close=()=>page.locator('#studio-dialog-close').click();
 async function copyAndPaste(selector,expected){
  await page.locator(selector).click();
  assert.match(await page.locator(selector).innerText(),/Copied/);
  assert.equal(await page.locator(selector).evaluate(e=>e===document.activeElement),true,'Copy restores button focus');
  // Read back only our just-written fixture content, using an actual paste.
  await page.locator(selector).evaluate(button=>{
   const input=document.createElement('textarea');input.id='qa-paste';
   (button.closest('dialog[open]')||document.fullscreenElement||document.body).append(input);input.focus();
  });
  await page.keyboard.press(process.platform==='darwin'?'Meta+V':'Control+V');
  await page.waitForFunction(text=>document.getElementById('qa-paste').value===text,expected);
  await page.locator('#qa-paste').evaluate(e=>e.remove());
 }
 try{
  // Keep a separate API client's session-only key active (like the development
  // helper), without competing for the single interactive browser slot. Remote configuration
  // must not lock the key field or claim that this new tab already owns it.
  const presenter=await browser.newContext();
  const session=await (await presenter.request.get(local+'/api/session')).json();
  const configured=await presenter.request.post(local+'/api/settings/connections',{headers:{'X-BaC-CSRF':session.csrf,'X-BaC-Key-Session':'fixture-presenter'},data:{source:'api',provider:'nvidia',apiKey:'fixture-presenter-key',model:'fixture-local-model'}});
  assert.ok(configured.ok(),await configured.text());
  await page.goto(origin);await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.version==='SCENARIO TEST FIXTURE');
  assert.deepEqual(await page.evaluate(()=>({secure:isSecureContext,clipboard:typeof navigator.clipboard})),{secure:false,clipboard:'undefined'});
  assert(await page.locator('#studio-config').isVisible());
  await page.locator('#studio-config').click();await page.locator('[data-connection-tab=location]').click();
  await page.locator('#studio-location-city').fill('Seoul');await page.locator('#studio-save-settings').click();
  await page.waitForFunction(()=>document.querySelector('#studio-settings-status').textContent.startsWith('Saved.'));await close();
  assert.equal((await api('settings')).location.city,'Seoul');
  await page.locator('#studio-config').click();await page.locator('[data-connection-tab=telegram]').click();
  await page.locator('#studio-settings-reset-tab').click();await page.locator('#studio-settings-model-tab').click();
  await page.locator('[data-connection-edit=api]').click();
  assert(await page.locator('#studio-connect-key').isEnabled(),'Another browser key must not lock this editor');
  await page.locator('#studio-connect-key').fill('fixture-remote-key');
  await page.locator('#studio-connect-model').focus();
  await page.waitForFunction(()=>document.querySelector('#studio-connect-models').options.length>0);
  await page.locator('#studio-connect-model').fill('fixture-local-model');await page.locator('#studio-connect-apply').click();
  await page.waitForFunction(()=>document.querySelector('#studio-connect-status').textContent==='Connected.');
  assert.equal((await api('settings/connections')).connections.api.model,'fixture-local-model');
  await page.locator('#studio-connect-cancel').click();await page.locator('#studio-route-plan').selectOption('api');await page.locator('#studio-connections-save').click();
  await page.waitForFunction(()=>document.querySelector('#studio-connections-status').textContent.startsWith('Saved.'));await close();
  await presenter.close();
  console.log('PASS: remote Settings, all tabs, persisted location, model catalog/connection and stage choices.');

  await page.locator('.world-campus-room[data-world-room=workshop]').click();await page.locator('#studio-name').fill('Remote QA');await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Remote QA'&&!BacCampus.inspect().arrival);
  const instruction='# Remote QA\nRead the brief.\n한국어도 복사됩니다.';
  await page.route('**/api/agent-documents*',r=>r.fulfill({json:{name:'Remote QA',description:'Fixture instructions',documents:[{filename:'AGENTS.md',group:'agent',status:'ready',content:instruction,updated:1}]}}));
  await page.locator('#studio-agent-code').click();await copyAndPaste('[data-code-copy="0"]',instruction);await close();
  await page.locator('#studio-agent-name').click();await copyAndPaste('#studio-identity-copy',instruction);await close();
  await page.locator('#studio-focus').click();
  assert(await page.evaluate(()=>!!document.fullscreenElement));
  await page.locator('#studio-agent-code').click();await copyAndPaste('[data-code-copy="0"]',instruction);
  // A denied modern clipboard must also fall back successfully.
  await page.evaluate(()=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:()=>Promise.reject(new Error('Permission denied'))}}));
  await copyAndPaste('[data-code-copy="0"]',instruction);
  await page.evaluate(()=>delete navigator.clipboard);await close();await page.locator('#studio-focus').click();
  console.log('PASS: actual HTTP clipboard readback for Instructions/documents, fullscreen and permission-denied fallback.');

  await choose('plan');await page.locator('#studio-team-setup').click();await page.locator('#studio-model-connections').waitFor();await close();
  await page.locator('#studio-standby summary').click();await page.locator('[data-standby-model="0"]').click();
  await page.locator('.team-model-dialog input').fill('fixture-other');await page.locator('[data-model-choice="fixture-other-model"]').click();
  await page.locator('.team-model-dialog').waitFor({state:'hidden'});
  assert.equal((await api('state')).teamSelections[0].id,'fixture-other-model');
  await api('upload',{crewRole:0,name:'remote-notes.md',content:'Remote file preview and download.'});
  await page.reload();await page.waitForFunction(()=>window.BacCampus?.inspect().navigation.overview);
  // A real network reload revokes the previous document's session-only key.
  // Reconnect this tab before submitting work; host-saved api.cfg keys differ.
  assert.equal((await api('settings')).profiles.nvidia.hasKey,false);
  // Reload can start background crew preparation. Wait for it before changing host connections.
  const deadline=Date.now()+15000;
  while(true){
   const state=await api('state',undefined,'event-brief');
   if(!['queued','running','waiting','stopping'].includes(state.preparation?.status))break;
   if(Date.now()>deadline)throw Error('Background preparation did not finish');
   await page.waitForTimeout(100);
  }
  await api('settings/connections',{source:'api',provider:'nvidia',apiKey:'fixture-remote-key',model:'fixture-local-model'});
  await page.evaluate(()=>BacStudio.refresh());await choose('plan');
  await page.locator('.studio-team-utilities').getByRole('button',{name:'Files',exact:true}).click();await page.locator('[data-browse-file="inbox/remote-notes.md"]').click();
  assert.equal(await page.locator('#studio-dialog-body pre').innerText(),'Remote file preview and download.');
  const pendingDownload=page.waitForEvent('download');await page.locator('#studio-download').click();const download=await pendingDownload;
  assert.equal(download.suggestedFilename(),'remote-notes.md');assert.equal(await fs.readFile(await download.path(),'utf8'),'Remote file preview and download.');await close();
  await page.locator('#studio-crew-prompt').fill('/goal PARTIAL_QA Build a calculator.');await page.locator('#studio-crew-send').click();
  await page.waitForFunction(async()=>{
   const state=await fetch('/api/state',{headers:{'X-BaC-Scenario':'plan'}}).then(r=>r.json());
   return state.crewChats.some(j=>j.payload.collaboration&&j.status==='done');
  },null,{polling:500});
  for(const width of [1280,2560]){
   await page.setViewportSize({width,height:1000});
   for(const full of [false,true]){
    if(full)await page.locator('#studio-focus').click();
    await page.locator('button[data-surface=usage]').click();await page.locator('#studio-usage-time').waitFor({state:'visible'});
    assert.match(await page.locator('#studio-usage-time').innerText(),/Casey/);
    await page.locator('#studio-surface-close').click();
    await page.locator('#studio-config').click();await page.locator('#studio-model-connections').waitFor();await close();
    if(full)await page.locator('#studio-focus').click();
   }
  }
  console.log('PASS: remote per-agent model, file preview/download and Usage/Settings at 1280/2560 widths, windowed/fullscreen.');
  await choose('event-brief');await page.locator('#studio-room-action').click();
  await page.waitForFunction(()=>document.querySelector('#studio-launch-event')&&!document.querySelector('#studio-launch-event').disabled);
  await page.locator('#studio-launch-event').click();
  await page.waitForFunction(()=>BacStudio.inspect().jobs.some(j=>j.kind==='crew'&&j.status==='done'),{},{timeout:30000});
  await page.locator('button[data-surface=deliverables]').click();await page.locator('.event-showcase-preview[data-ready=true]').waitFor();
  await page.locator('[data-result-json$="-themes.json"]').click();await page.locator('#studio-json-browse').waitFor();
  const json=await page.locator('#studio-json-raw').textContent();await copyAndPaste('#studio-json-copy',json);await close();
  await page.locator('#studio-surface-close').click();
  await page.locator('button[data-surface=usage]').click();assert.match(await page.locator('#studio-usage-time').innerText(),/Riley/);
  await page.screenshot({path:'/tmp/bac-remote-usage-qa.png'});await page.locator('#studio-surface-close').click();
  await page.locator('#studio-bac-reset').click();await page.locator('#studio-team-reset-confirm').click();
  await page.waitForFunction(()=>document.querySelector('#studio-bac-reset').disabled);
  assert.deepEqual(errors,[]);assert.deepEqual(failures,[]);
  console.log('PASS: remote Event Brief run, HTML results, nested JSON preview/copy, usage and scenario reset; no API/page errors.');
 }catch(error){await page.screenshot({path:'/tmp/bac-remote-failure.png'});throw error;}
 finally{await page.unrouteAll({behavior:'ignoreErrors'});await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
