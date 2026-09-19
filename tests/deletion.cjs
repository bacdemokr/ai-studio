// Run against tests/fixture_studio.py: real UI/API, explicitly simulated model.
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),args:['--enable-unsafe-swiftshader']});
 try{
  const context=await browser.newContext({viewport:{width:1600,height:1100}}),page=await context.newPage(),errors=[];
  const base=process.env.BASE_URL||'http://127.0.0.1:8082';page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.waitForFunction(()=>BacStudio.inspect().runtime.testFixture);
  const keys=[];
  for(const name of ['Jinny','Orbit','Scout']){
   if(keys.length)await page.locator('#studio-add-agent').click();
   await page.locator('#studio-name').fill(name);await page.locator('#studio-create').click();await page.waitForFunction(n=>BacStudio.inspect().profile?.name===n,name);
   keys.push(await page.evaluate(()=>BacStudio.inspect().agentId));await page.locator('#studio-alert button').click();
  }
  // Deletion always shows the selected identity; dismissing never changes the collection.
  await page.locator('#studio-delete-agent').click();assert.equal(await page.locator('#studio-dialog h3').innerText(),'Delete Scout?');
  assert.match(await page.locator('#studio-dialog').innerText(),/saved memory and workspace files/);
  assert.equal(await page.evaluate(()=>document.activeElement.id),'studio-delete-cancel');await page.keyboard.press('Escape');
  assert.equal((await page.evaluate(()=>BacStudio.inspect().agents)).length,3);
  // Scheduled work has an actionable route to cancellation.
  await page.locator('#studio-schedule').click();await page.locator('#studio-schedule-form button').click();await page.waitForFunction(()=>BacStudio.inspect().jobs[0]?.status==='queued');
  await page.locator('#studio-delete-agent').click();assert.equal(await page.locator('#studio-delete-confirm').count(),0);
  await page.locator('#studio-delete-view-work').click();await page.locator('#studio-result [data-decision=cancel]').click();await page.waitForFunction(()=>BacStudio.inspect().jobs[0]?.status==='cancelled');
  await page.locator('button[data-room=lounge]').click();
  const api=async(p,endpoint,body,key,csrf=true)=>p.evaluate(async({endpoint,body,key,csrf})=>{
   const session=await (await fetch('/api/session')).json();const headers={'Content-Type':'application/json','X-BaC-Agent':key};if(csrf)headers['X-BaC-CSRF']=session.csrf;
   const r=await fetch('/api/'+endpoint,{method:'POST',headers,body:JSON.stringify(body)});return {status:r.status,body:await r.json()};
  },{endpoint,body,key,csrf});
  assert.equal((await api(page,'delete-agent',{name:'Scout'},keys[2],false)).status,403);
  const outsider=await browser.newContext(),foreign=await outsider.newPage();await foreign.goto(base);await foreign.waitForFunction(()=>BacStudio.inspect().runtime.testFixture);
  assert.equal((await api(foreign,'delete-agent',{name:'Scout'},keys[2])).status,404);await outsider.close();
  // Another tab recovers when the selected identity disappears, without stale writes.
  const twin=await context.newPage();twin.on('pageerror',e=>errors.push(e.message));await twin.goto(base);await twin.waitForFunction(()=>BacStudio.inspect().agents?.length===3);
  await twin.locator('button[data-room=lounge]').click();await twin.locator('[data-agent-key="'+keys[2]+'"]').click();await twin.waitForFunction(k=>BacStudio.inspect().agentId===k,keys[2]);
  // A server failure leaves the agent visible and the confirmation retryable.
  await page.route('**/api/delete-agent',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'TEST FIXTURE: cleanup unavailable'})}),{times:1});
  await page.locator('#studio-delete-agent').click();await page.locator('#studio-delete-confirm').click();await page.locator('#studio-delete-error').waitFor({state:'visible'});
  assert.equal(await page.locator('[data-resident]').count(),3);assert.match(await page.locator('#studio-delete-error').innerText(),/cleanup unavailable/);
  await page.locator('#studio-delete-confirm').click();await page.waitForFunction(()=>BacStudio.inspect().agents.length===2);
  assert.equal(await page.locator('[data-resident]').count(),2);assert.equal((await page.evaluate(()=>BacCampus.inspect().residents)).length,2);
  await twin.waitForFunction(k=>BacStudio.inspect().agentId!==k,keys[2]);assert.equal((await twin.evaluate(()=>BacStudio.inspect().agents)).length,2);await twin.close();
  // Delete the original auth-linked agent, then add a new one and reload.
  assert.equal(await page.evaluate(()=>BacStudio.inspect().agentId),keys[0]);await page.locator('#studio-alert button').click();
  await page.locator('#studio-delete-agent').click();await page.locator('#studio-delete-confirm').click();await page.waitForFunction(()=>BacStudio.inspect().agents.length===1);
  assert.equal(await page.evaluate(()=>BacStudio.inspect().agentId),keys[1]);await page.locator('#studio-alert button').click();
  await page.locator('#studio-add-agent').click();await page.locator('#studio-name').fill('Newcomer');await page.locator('#studio-create').click();await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Newcomer');await page.locator('#studio-alert button').click();
  await page.reload();await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Newcomer');assert.equal((await page.evaluate(()=>BacStudio.inspect().agents)).length,2);
  // Last deletion returns to a fresh creator; old IDs and conversations are never reused.
  for(const count of [1,0]){await page.locator('#studio-delete-agent').click();await page.locator('#studio-delete-confirm').click();await page.waitForFunction(n=>BacStudio.inspect().agents.length===n,count);await page.locator('#studio-alert button').click();}
  assert.equal(await page.evaluate(()=>BacStudio.inspect().room),'workshop');assert.equal((await page.evaluate(()=>BacCampus.inspect().residents)).length,0);
  await page.reload();await page.waitForFunction(()=>BacStudio.inspect().runtime.testFixture);assert.equal((await page.evaluate(()=>BacStudio.inspect().agents)).length,0);
  const fresh=await page.evaluate(()=>BacStudio.inspect().agentId);assert(!keys.includes(fresh));
  await page.locator('#studio-name').fill('Fresh start');await page.locator('#studio-create').click();await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Fresh start');await page.locator('#studio-alert button').click();
  await page.setViewportSize({width:390,height:900});await page.locator('#studio-delete-agent').click();
  assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),'Mobile overflow');assert(await page.locator('#studio-delete-cancel').isVisible());await page.locator('#studio-delete-cancel').click();
  assert.deepEqual(errors,[]);console.log('PASS: named confirmation/cancel, pending-work guidance, ownership/CSRF, retry, 3D removal, cross-tab recovery, original/last agent deletion, fresh creation and mobile controls.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
