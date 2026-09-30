const assert=require('node:assert/strict'),{chromium}=require('playwright');
const base=process.env.BASE_URL||'http://127.0.0.1:18082';
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH,args:['--enable-unsafe-swiftshader']});
 const failures=[];
 async function check(name,run){const page=await browser.newPage({viewport:{width:1600,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));try{await run(page);assert.deepEqual(errors,[]);console.log('PASS: '+name);}catch(e){failures.push(name+': '+e.message);console.error('FAIL: '+name+': '+e.message);}finally{await page.close();}}
 async function start(page){await page.goto(base);await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);}
 await check('late upload failure preserves the Settings dialog',async page=>{
  await start(page);
  await page.evaluate(async()=>{const s=await(await fetch('/api/session')).json();await fetch('/api/onboard',{method:'POST',headers:{'Content-Type':'application/json','X-BaC-CSRF':s.csrf,'X-BaC-Agent':s.agentId},body:JSON.stringify({name:'Upload race',skills:['documents']})});});
  await page.reload();await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Upload race');
  await page.locator('.world-room-map [data-world-room=lounge]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  let release,started=false;
  await page.route('**/api/upload',async route=>{started=true;await new Promise(resolve=>release=resolve);await route.fulfill({status:503,json:{error:'Upload temporarily unavailable'}});});
  await page.locator('#studio-upload').setInputFiles({name:'brief.txt',mimeType:'text/plain',buffer:Buffer.from('Example brief')});
  while(!started)await pause(20);
  await page.locator('#studio-config').click();await page.locator('#studio-config-form').waitFor();
  release();await page.waitForFunction(()=>!document.querySelector('#studio-attach').disabled);
  assert.equal(await page.locator('#studio-config-form').count(),1,'late upload must not replace Settings');
  assert.match(await page.locator('#studio-alert').innerText(),/brief.txt.*Upload temporarily unavailable/);
 });
 for(const crew of [true,false])await check((crew?'team':'lounge')+' Stop stays pending across polling and retries after failure',async page=>{
  let tick=0,calls=0,release,jobStatus='running';
  await page.route(/\/api\/(session|state)$/,async route=>{
   const response=await route.fetch({headers:{...route.request().headers(),'if-none-match':''}}),state=await response.json();
   const job={id:'0123456789abcdef01234567',kind:crew?'crew-chat':'chat',status:jobStatus,created:Date.now()/1000,payload:{prompt:'Example request',...(crew?{crewRole:0}:{})},result:{},events:[{title:'Working '+(++tick)}]};
   if(crew)state.crewChats=[job];else{state.jobs=[job];state.profile={name:'Stop race',skills:['documents'],avatar:{body:'classic',color:'green'}};}
   await route.fulfill({response,json:state});
  });
  await page.route('**/api/decision',async route=>{const attempt=++calls;await new Promise(resolve=>release=resolve);if(attempt===1)await route.fulfill({status:503,json:{error:'Stop temporarily unavailable'}});else{jobStatus='cancelled';await route.fulfill({json:{cancelled:true}});}});
  await start(page);
  await page.locator('.world-room-map [data-world-room='+(crew?'mission':'lounge')+']').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  if(crew)await page.locator('[data-campus-agent="0"]').click();
  const button=page.locator(crew?'[data-crew-chat-stop]':'[data-chat-stop]');await button.waitFor();
  await button.click();while(!calls)await pause(20);
  await page.waitForTimeout(2200);
  const disabled=await button.isDisabled();await button.evaluate(node=>node.click());await pause(100);
  const count=calls;release();await page.waitForFunction(selector=>!document.querySelector(selector)?.disabled,crew?'[data-crew-chat-stop]':'[data-chat-stop]');
  assert.equal(disabled,true,'polling must keep Stop disabled while its request is pending');
  assert.equal(count,1,'one pending stop request per job');
  await button.click();while(calls<2)await pause(20);release();
  await button.waitFor({state:'detached'});
  if(crew)assert(await page.locator('#studio-crew-chat-error').isHidden());
 });
 await check('model save survives close/reopen and preserves failed selections for retry',async page=>{
  let release,calls=0,selected='model/old';
  const runtime={ready:true,model:true,teamModel:true,teamReady:true,testFixture:true,teamModels:[{id:'model/old',label:'Original model'},{id:'model/new',label:'New model'}]};
  await page.route(/\/api\/(session|state)$/,async route=>{const response=await route.fetch({headers:{...route.request().headers(),'if-none-match':''}});await route.fulfill({response,json:{...await response.json(),runtime,teamSelections:[{role:0,id:selected}]}});});
  await page.route('**/api/runtime',r=>r.fulfill({json:runtime}));
  await page.route('**/api/team-model',async route=>{calls++;if(calls===1){await new Promise(resolve=>release=resolve);await route.fulfill({status:503,json:{error:'Model service unavailable'}});}else{selected=route.request().postDataJSON().model;await route.fulfill({json:{teamSelections:[{role:0,id:selected}]}});}});
  await start(page);
  async function open(){await page.locator('#studio-config').click();await page.locator('#studio-open-team-settings').click();}
  await open();await page.locator('[data-team-model="0"]').click();
  await page.locator('.team-model-dialog input').fill('no-such-model');assert.equal(await page.locator('[data-model-choice]').count(),0);
  await page.locator('.team-model-dialog input').fill('New model');await page.locator('[data-model-choice="model/new"]').click();
  await page.locator('[data-team-apply-all]').click();while(!calls)await pause(20);
  await page.locator('#studio-dialog-close').click();await open();
  const disabled=await page.locator('[data-team-model="0"]').isDisabled();release();
  await page.waitForFunction(()=>document.querySelector('#studio-team-model-status')?.textContent.includes('Model service unavailable'));
  assert.equal(disabled,true,'reopened model controls must show the pending save');
  assert.match(await page.locator('[data-team-model="0"]').innerText(),/New model/,'failed model selection is kept');
  assert(await page.locator('[data-team-apply-all]').isEnabled(),'failed selection can be retried');
  await page.locator('[data-team-apply-all]').click();await page.getByText('Model changes applied. Used from the next request.',{exact:true}).waitFor();
  assert.equal(calls,2);assert.equal(selected,'model/new');
 });
 await browser.close();if(failures.length)throw new Error(failures.join('\n'));
})().catch(e=>{console.error(e);process.exitCode=1;});
