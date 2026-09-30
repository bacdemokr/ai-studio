const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 const page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 const models=[{id:'nvidia/nvidia/nemotron-3-ultra-nvfp4',label:'Nemotron 3 Ultra'},{id:'nvidia/nvidia/nemotron-3.5-lightning',label:'Nemotron 3.5 Lightning'},{id:'example/new-model',label:'New model'}];
 const runtime={ready:false,gateway:true,model:false,teamModel:true,teamReady:true,teamModels:models,testFixture:true};
 let connectionCalls=0,personalWrites=0,selectionCalls=0;
 let selections=Array.from({length:9},(_,role)=>({role,id:models[role===0?0:1].id}));
 try{
  await page.route('**/api/session',async r=>{const response=await r.fetch(),state=await response.json();await r.fulfill({json:{...state,runtime}})});
  await page.route('**/api/state',async r=>{const response=await r.fetch();await r.fulfill({json:{...await response.json(),teamSelections:selections}})});
  await page.route('**/api/runtime',r=>r.fulfill({json:runtime}));
  await page.route('**/api/settings',async r=>{if(r.request().method()==='POST')personalWrites++;await r.fulfill({json:{provider:'local',providers:{local:{label:'Local',baseUrl:'http://localhost:8000/v1'}},profiles:{local:{model:'local-test',contextWindow:32768}},location:{city:'Zurich'}}})});
  await page.route('**/api/telegram',r=>r.fulfill({json:{connected:false}}));
  await page.route('**/api/settings/team-model',r=>{connectionCalls++;return r.fulfill({status:400,json:{error:'Use api.cfg'}})});
  await page.route('**/api/team-model',r=>{selectionCalls++;assert.equal(r.request().postDataJSON().model,'example/new-model');selections=selections.map(m=>m.role===0?{...m,id:'example/new-model'}:m);return r.fulfill({json:{teamSelections:selections}})});
  await page.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8082');await page.waitForFunction(()=>window.BacStudio?.inspect().agentId);
  await page.locator('#studio-config').click();assert.match(await page.locator('#studio-settings-model-panel').innerText(),/STAGES 01 \/ 02/);
  await page.locator('#studio-open-team-settings').click();
  assert.equal(await page.locator('#studio-team-api-key,#studio-team-connect').count(),0);
  assert.match(await page.locator('.studio-team-api-card').innerText(),/api.cfg/);
  assert.match(await page.locator('.studio-team-api-card').innerText(),/\.\/bac start/);
  assert.equal(await page.locator('.studio-team-api-state').innerText(),'Connected');
  await page.locator('#studio-team-config-form [data-team-model="0"]').click();await page.locator('.team-model-dialog input').fill('new-model');await page.locator('[data-model-choice="example/new-model"]').click();assert.equal(selectionCalls,0);assert(await page.locator('[data-team-apply-all]').isEnabled());await page.locator('[data-team-apply-all]').click();await page.getByText('Model changes applied. Used from the next request.',{exact:true}).waitFor();assert.equal(selectionCalls,1);assert.equal(personalWrites,0);
  assert.match(await page.locator('#studio-team-model-status').innerText(),/Model changes applied/);
  assert.match(await page.locator('#studio-team-config-form [data-team-model="0"]').innerText(),/New model/);
  await page.waitForTimeout(1700);
  await page.locator('#studio-team-config-form [data-team-model="0"]').click();assert(await page.locator('[data-model-apply]').isDisabled());assert.equal(await page.locator('[data-model-choice="example/new-model"]').getAttribute('aria-pressed'),'true');
  await page.locator('[data-model-choice="nvidia/nvidia/nemotron-3-ultra-nvfp4"]').click();assert.equal(selectionCalls,1);assert(await page.locator('[data-team-apply-all]').isEnabled());assert.match(await page.locator('#studio-team-model-status').innerText(),/Unsaved/);
  assert.equal(connectionCalls,0);await page.locator('#studio-dialog-close').click();
  await page.locator('#studio-config').click();await page.locator('#studio-settings-reset-tab').click();assert.equal(await page.locator('#studio-settings-reset-panel #studio-bac-reset').count(),0);await page.locator('#studio-dialog-close').click();
  await page.locator('.world-room-map [data-world-room="mission"]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);await page.locator('[data-campus-agent="0"]').click();
  await page.locator('#studio-bac-reset').click();await page.getByText('BaC reset.',{exact:true}).waitFor();assert(await page.locator('#studio-bac-reset').isEnabled());
  assert.deepEqual(errors,[]);console.log('PASS: CLI-managed key guidance, no browser key writes, model selection, Settings scope and reset.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
