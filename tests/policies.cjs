// Policy UX and account boundaries against an explicit OpenShell/model fixture.
const assert=require('node:assert/strict');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),args:['--enable-unsafe-swiftshader']});try{
 const context=await browser.newContext({viewport:{width:1600,height:1150}}),page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(process.env.BASE_URL||'http://127.0.0.1:8082');await page.waitForFunction(()=>BacStudio.inspect().runtime.testFixture);
 // A ready-made crew can run before personal onboarding, with no OpenShell dependency.
 await page.locator('button[data-room=mission]').click();await page.locator('#studio-room-action').click();assert(await page.locator('[name=personalLead]').isDisabled());await page.locator('#studio-crew-form button').click();await page.waitForFunction(()=>BacStudio.inspect().jobs[0]?.status==='done');
 assert.equal(await page.evaluate(()=>BacStudio.inspect().profile),null);
 let roster=await page.evaluate(()=>BacStudio.inspect().jobs[0].payload.roster);assert.deepEqual(roster.map(m=>m.name),['Milo','Nova','Atlas','Momo','Pico']);assert(roster.every(m=>m.protection==='standard'&&!m.key));
 await page.locator('button[data-room=workshop]').click();await page.locator('#studio-name').fill('Orbit');await page.locator('[name=protection][value=openshell]').check();await page.locator('#studio-create').click();await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Orbit');await page.locator('#studio-alert button').click();
 const orbit=await page.evaluate(()=>BacStudio.inspect().agentId);assert.equal(await page.evaluate(()=>BacStudio.inspect().profile.protection),'openshell');
 await page.locator('#studio-agent-policy').click();await page.locator('.studio-policy-status').filter({hasText:'WAITING FOR FIRST MISSION'}).waitFor();assert.match(await page.locator('.studio-policy-status').innerText(),/TEST FIXTURE/);
 await page.locator('[data-policy-try]').click();await page.waitForFunction(()=>BacStudio.inspect().jobs[0]?.status==='error');
 await page.locator('#studio-agent-policy').click();await page.locator('.studio-policy-status').filter({hasText:'POLICY LOADED'}).waitFor();assert.match(await page.locator('.studio-policy-evidence').innerText(),/DENIED/);
 assert.equal(await page.locator('.studio-permission[data-allowed=true]').count(),0);
 await page.locator('[data-policy-permission=weather]').click();await page.waitForFunction(()=>document.querySelector('[data-policy-permission=weather]').closest('article').dataset.allowed==='true');await page.locator('#studio-alert button').click();
 assert.equal(await page.locator('.studio-permission[data-allowed=true]').count(),1);
 await page.locator('[data-policy-try]').click();await page.waitForFunction(()=>BacStudio.inspect().jobs[0]?.status==='done'&&BacStudio.inspect().jobs[0]?.kind==='chat');
 await page.locator('#studio-agent-policy').click();await page.locator('.studio-policy-evidence li[data-action=allow]').waitFor();
 await page.screenshot({path:process.env.POLICY_SCREENSHOT||'/tmp/bac-policy-test.png',fullPage:true});
 await page.locator('[data-policy-permission=weather]').click();await page.waitForFunction(()=>document.querySelector('[data-policy-permission=weather]').closest('article').dataset.allowed==='false');await page.locator('#studio-alert button').click();
 await page.locator('[data-policy-try]').click();await page.waitForFunction(()=>BacStudio.inspect().jobs[0]?.status==='error');
 await page.locator('#studio-agent-policy').click();await page.locator('[data-policy-mode=standard]').click();await page.waitForFunction(()=>BacStudio.inspect().profile.protection==='standard');await page.locator('#studio-alert button').click();assert(await page.locator('[data-policy-permission=weather]').isDisabled());
 // The same web mission works without a sandbox when the attendee explicitly turns it off.
 await page.locator('button[data-room=lounge]').click();await page.locator('[data-studio-mission=weather]').click();await page.locator('#studio-send').click();await page.waitForFunction(()=>BacStudio.inspect().jobs[0]?.status==='done');
 await page.locator('#studio-add-agent').click();await page.locator('#studio-name').fill('Scout');await page.locator('[name=protection][value=openshell]').check();await page.locator('#studio-create').click();await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Scout');await page.locator('#studio-alert button').click();
 const scout=await page.evaluate(()=>BacStudio.inspect().agentId);await page.locator('#studio-agent-policy').click();await page.locator('.studio-policy-status').filter({hasText:'WAITING FOR FIRST MISSION'}).waitFor();assert.equal(await page.locator('.studio-permission[data-allowed=true]').count(),0);
 await page.locator('#studio-policy-agent').selectOption(orbit);await page.waitForFunction(k=>BacStudio.inspect().agentId===k,orbit);await page.locator('.studio-policy-status').filter({hasText:'OPENSHELL OFF'}).waitFor();
 await page.reload();await page.waitForFunction(()=>BacStudio.inspect().room==='policies');await page.locator('.studio-policy-status').filter({hasText:'OPENSHELL OFF'}).waitFor();
 const other=await browser.newContext(),foreign=await other.newPage();await foreign.goto('http://127.0.0.1:8082');await foreign.waitForFunction(()=>BacStudio.inspect().runtime.testFixture);
 assert.equal(await foreign.evaluate(async key=>{const s=await(await fetch('/api/session')).json();return(await fetch('/api/agent-policy',{method:'POST',headers:{'Content-Type':'application/json','X-BaC-CSRF':s.csrf,'X-BaC-Agent':key},body:JSON.stringify({mode:'standard'})})).status;},scout),404);
 assert.equal(await page.evaluate(async key=>(await fetch('/api/agent-policy',{method:'POST',headers:{'Content-Type':'application/json','X-BaC-Agent':key},body:JSON.stringify({mode:'standard'})})).status,orbit),403);await other.close();
 for(const width of [736,390]){await page.setViewportSize({width,height:950});assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),'Policies overflow at '+width);}
 assert.deepEqual(errors,[]);console.log('PASS: no-onboarding preset crew, OpenShell onboarding, deny → weather-only approval → allow → revoke → deny, explicit off, isolated policies, reload, account/CSRF, mobile. Network decisions are explicitly simulated fixture evidence.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
