// Disposable fixture only: fake credentials and deterministic catalog failures.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 const page=await browser.newPage({viewport:{width:1500,height:1100}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 let keySession='';page.on('request',r=>{keySession=r.headers()['x-bac-key-session']||keySession;});
 const api=(path,body)=>page.evaluate(async({path,body,keySession})=>{
  const session=await fetch('/api/session').then(r=>r.json());
  const r=await fetch('/api/'+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-BaC-CSRF':session.csrf,'X-BaC-Scenario':'plan','X-BaC-Key-Session':keySession},...(body?{body:JSON.stringify(body)}:{})});
  if(!r.ok)throw Error(await r.text());return r.json();
 },{path,body,keySession});
 const leaseTimer=setInterval(()=>api('credential-session',{}).catch(()=>{}),15000);
 try{
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8083');await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.version==='SCENARIO TEST FIXTURE');
  await api('settings/connections',{source:'api',provider:'nvidia',apiKey:'fixture-new-key',model:'fixture-local-model',contextWindow:131072});
  await page.locator('#studio-config').click();
  const open=()=>page.locator('[data-connection-edit=api]').click();
  await open();await page.waitForFunction(()=>document.querySelector('#studio-connect-models').options.length>0);
  assert(await page.locator('#studio-connect-key').isDisabled());assert(await page.locator('#studio-connect-url').isDisabled());
  assert.equal(await page.locator('#studio-connect-load,#studio-connect-context').count(),0);
  await page.locator('#studio-connect-cancel').click();
  // An old provider's delayed model response must not overwrite the new provider.
  let release,started;
  const ready=new Promise(r=>started=r),gate=new Promise(r=>release=r);
  await page.route('**/api/settings/connections/models',async route=>{
   const provider=route.request().postDataJSON().provider;
   if(provider==='nvidia'){started();await gate;await route.fulfill({json:{models:[{id:'stale-model'}]}});}
   else await route.fulfill({json:{models:[{id:'fixture-local-model'}]}});
  });
  await open();await ready;
  await page.locator('#studio-connect-provider').selectOption('anthropic');
  assert(await page.locator('#studio-connect-key').isEnabled());
  await page.locator('#studio-connect-key').fill('fixture-anthropic-key');await page.locator('#studio-connect-model').focus();
  await page.waitForFunction(()=>document.querySelector('#studio-connect-models option')?.value==='fixture-local-model');
  release();await page.waitForTimeout(100);
  assert.equal(await page.locator('#studio-connect-models option').first().getAttribute('value'),'fixture-local-model');
  await page.unroute('**/api/settings/connections/models');
  // Context is hidden, so changing provider must not silently inherit 131072.
  const request=page.waitForRequest(r=>r.url().endsWith('/api/settings/connections')&&r.method()==='POST');
  await page.locator('#studio-connect-model').fill('fixture-local-model');await page.locator('#studio-connect-apply').click();
  assert.equal((await request).postDataJSON().contextWindow,32768);
  await page.waitForFunction(()=>document.querySelector('#studio-connect-status').textContent==='Connected.');
  assert(await page.locator('#studio-connect-key').isDisabled());assert.equal(await page.locator('#studio-connect-key').inputValue(),'');
  // Failed model change leaves the established model intact, then allows retry.
  await page.locator('#studio-connect-model').fill('not-offered');await page.locator('#studio-connect-apply').click();
  await page.waitForFunction(()=>document.querySelector('#studio-connect-status').textContent.includes('unavailable'));
  assert.equal((await api('settings/connections')).connections.api.model,'fixture-local-model');
  assert(await page.locator('#studio-connect-model').isEnabled());assert(await page.locator('#studio-connect-url').isDisabled());
  await page.locator('#studio-connect-model').fill('fixture-other-model');await page.locator('#studio-connect-apply').click();
  await page.waitForFunction(()=>document.querySelector('#studio-connect-status').textContent==='Connected.');
  assert.equal((await api('settings/connections')).connections.api.model,'fixture-other-model');
  await page.screenshot({path:'/tmp/bac-connection-editor-qa.png'});
  await page.locator('#studio-dialog-close').click();
  await api('settings/connections',{source:'api',provider:'nvidia',apiKey:'fixture-new-key',model:'fixture-local-model'});
  await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.modelConnections?.connections.api.provider==='nvidia');
  await page.locator('.world-room-map [data-world-scenario=plan]').click();
  await page.locator('#studio-standby summary').click();await page.locator('[data-standby-model="0"]').click();
  await page.locator('.team-model-dialog input').fill('fixture-other');
  await page.route('**/api/team-model',r=>r.fulfill({status:409,json:{error:'Fixture busy. Try again.'}}));
  await page.locator('[data-model-choice="fixture-other-model"]').click();
  await page.locator('.team-model-error').waitFor({state:'visible'});
  assert.notEqual((await api('state')).teamSelections[0].id,'fixture-other-model');
  await page.unroute('**/api/team-model');
  let requests=0,finishSave,saveStarted;
  const saveGate=new Promise(r=>finishSave=r),saveReady=new Promise(r=>saveStarted=r);
  await page.route('**/api/team-model',async r=>{requests++;saveStarted();await saveGate;await r.continue();});
  await page.locator('[data-model-choice="fixture-other-model"]').click();await saveReady;
  assert(await page.locator('[data-model-choice="fixture-other-model"]').isDisabled());
  assert(await page.locator('[data-model-close]').isDisabled());
  finishSave();await page.locator('.team-model-dialog').waitFor({state:'hidden'});
  assert.equal(requests,1);assert.equal((await api('state')).teamSelections[0].id,'fixture-other-model');
  await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.version==='SCENARIO TEST FIXTURE');
  assert.equal((await api('state')).teamSelections[0].id,'fixture-other-model');
  assert.deepEqual(errors,[]);
  console.log('PASS: automatic catalog, provider race, key/endpoint locks, hidden context isolation, failed save preservation, direct per-agent save/error/retry and reload.');
 }finally{clearInterval(leaseTimer);await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
