// Run against python3 tests/fixture_studio.py. This is a test double, not model quality validation.
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),args:['--enable-webgl','--ignore-gpu-blocklist','--enable-unsafe-swiftshader']});
 try{
  const context=await browser.newContext({viewport:{width:1500,height:1100},acceptDownloads:true});
  const page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8082');
  await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
  assert(await page.locator('#studio-name').isVisible());
  assert.equal(await page.locator('[data-world-skill]').count(),9);
  await page.locator('#studio-name').fill('Riley');await page.locator('[data-persona="maker"]').click();await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Riley');
  assert.match(await page.locator('#studio-personality').innerText(),/Inventive/);
  await page.locator('#campus-viewport').scrollIntoViewIfNeeded();
  const first=await page.evaluate(()=>BacCampus.inspect().robots);await page.waitForFunction(initial=>JSON.stringify(BacCampus.inspect().robots)!==JSON.stringify(initial),first,{timeout:12000});
  await page.locator('#campus-motion').click();const paused=await page.evaluate(()=>BacCampus.inspect().robots);await page.waitForTimeout(300);assert.deepEqual(paused,await page.evaluate(()=>BacCampus.inspect().robots));await page.locator('#campus-motion').click();
  await page.locator('[data-world-skill="builder"]').click();await page.locator('#studio-send').click();
  await page.waitForFunction(()=>BacStudio.inspect().jobs[0]?.status==='done');
  await page.locator('#studio-result [data-studio-file]').click();await page.locator('#studio-app-frame').waitFor({state:'visible'});
  assert.equal(await page.locator('#studio-app-frame').getAttribute('sandbox'),'allow-scripts');
  const download=page.waitForEvent('download');await page.locator('#studio-download').click();assert((await download).suggestedFilename().endsWith('.html'));await page.locator('#studio-dialog-close').click();
  await page.locator('[data-studio-mission="memory"]').click();await page.locator('#studio-send').click();await page.waitForFunction(()=>BacStudio.inspect().jobs[0]?.status==='done'&&BacStudio.inspect().jobs.length===2);
  await page.reload();await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Riley');await page.locator('#studio-memory').click();assert.match(await page.locator('#studio-dialog pre').innerText(),/Vegetarian/);await page.locator('#studio-dialog-close').click();
  await page.locator('[data-world-skill="documents"]').click();await page.locator('#studio-sample-document').click();await page.waitForFunction(()=>document.querySelector('#studio-files').textContent.includes('sample-bac-brief'));
  await page.locator('#studio-edit-agent').click();await page.locator('#studio-edit-form [name="persona"]').selectOption('analyst');await page.locator('#studio-edit-form button').click();await page.waitForFunction(()=>BacStudio.inspect().profile.persona==='analyst');
  await page.locator('#studio-plan').click();await page.locator('#studio-crew-form [name="spark"]').fill('0');await page.locator('#studio-crew-form [name="workstation"]').fill('0');await page.locator('#studio-crew-form button').click();
  await page.waitForFunction(()=>BacStudio.inspect().jobs[0]?.status==='waiting');
  await page.locator('#studio-board-tab').click();assert(await page.locator('#studio-board').isVisible());assert.equal(await page.locator('[data-role-output]').count(),3);await page.locator('#studio-campus-tab').click();
  await page.locator('[data-decision="approve-equipment"]').click();await page.waitForFunction(()=>BacStudio.inspect().jobs[0]?.status==='done');
  await page.locator('[data-safety="shared"]').click();assert.match(await page.locator('#studio-dialog-body').innerText(),/One brief. Five accountable roles/);assert.equal(await page.locator('.studio-handoff-list>li').count(),5);assert.match(await page.locator('.studio-handoff-list>li').last().innerText(),/Riley, Nova, Atlas, Momo/);await page.locator('#studio-dialog-close').click();
  await page.locator('#studio-board-tab').click();await page.locator('#studio-board-shared').click();assert.equal(await page.locator('.studio-handoff-list>li').count(),5);await page.locator('#studio-dialog-close').click();assert.equal(await page.locator('[data-role-output]').count(),5);await page.locator('[data-role-output="4"]').click();assert.match(await page.locator('#studio-dialog pre').innerText(),/Fixture deliverable/);await page.locator('#studio-dialog-close').click();await page.locator('#studio-campus-tab').click();
  await page.locator('#studio-focus').click();assert(await page.locator('.world-expanded').isVisible());await page.keyboard.press('Escape');assert.equal(await page.locator('.world-expanded').count(),0);
  await page.locator('#studio-schedule').click();await page.locator('#studio-schedule-form button').click();await page.waitForFunction(()=>BacStudio.inspect().jobs[0]?.kind==='reminder');await page.locator('[data-decision="cancel"]').click();await page.waitForFunction(()=>BacStudio.inspect().jobs[0]?.status==='cancelled');
  // Recovery is deliberate and preserves the failed run as evidence.
  await page.locator('#studio-prompt').fill('[fixture:fail-once] Make a draft');await page.locator('#studio-send').click();await page.waitForFunction(()=>BacStudio.inspect().jobs[0]?.status==='error');
  await page.locator('[data-safety="recovery"]').click();assert.match(await page.locator('#studio-dialog-body').innerText(),/TEST FIXTURE: model unavailable/);
  const evidenceDownload=page.waitForEvent('download');await page.locator('#studio-help-download').click();assert((await evidenceDownload).suggestedFilename().startsWith('bac-evidence-'));
  await page.locator('#studio-retry').click();await page.waitForFunction(()=>BacStudio.inspect().jobs[0]?.status==='done');assert((await page.evaluate(()=>BacStudio.inspect().jobs)).some(j=>j.status==='error'));
  await page.locator('#studio-security').click();assert.match(await page.locator('.studio-security-label').innerText(),/ILLUSTRATIVE/);
  for(const expected of ['DENIED','REVIEW','ALLOWED','DENIED']){await page.locator('#studio-security-next').click();assert.equal(await page.locator('.studio-boundary-gate small').innerText(),expected);}
  await page.locator('#studio-security-host').click();await page.locator('#studio-security-refresh').waitFor({state:'visible'});assert.match(await page.locator('.studio-security-label').innerText(),/NO COMPLETE HOST PROOF/);assert.equal(await page.locator('.studio-proof-steps [data-passed=true]').count(),0);await page.locator('#studio-dialog-close').click();
  await page.locator('#studio-route').click();assert.match(await page.locator('.studio-route-grid').innerText(),/NeMoReef|NEMOREEF/);await page.locator('#studio-route-start').click();
  await page.locator('#studio-help').click();await page.locator('#studio-local-fallback').click();assert(await page.locator('#bac-playground').isVisible());await page.locator('[data-mode="campus"]').click();
  await page.locator('#studio-reset').click();await page.locator('#studio-confirm-reset').click();await page.waitForFunction(()=>BacStudio.inspect().jobs.length===0);assert.equal(await page.evaluate(()=>BacStudio.inspect().profile.name),'Riley');await page.locator('#studio-memory').click();assert.match(await page.locator('#studio-dialog pre').innerText(),/Vegetarian/);await page.locator('#studio-dialog-close').click();
  // Session separation and CSRF protect native gateway access from other participants/sites.
  const other=await browser.newContext();const p2=await other.newPage();await p2.goto('http://127.0.0.1:8082');await p2.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);assert.equal(await p2.evaluate(()=>BacStudio.inspect().profile),null);assert.equal((await p2.evaluate(()=>BacStudio.inspect().jobs)).length,0);
  assert.equal(await page.evaluate(async()=> (await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:'bad csrf'})})).status),403);
  for(const width of [736,390]){await page.setViewportSize({width,height:950});for(const mode of ['campus','playground','crew']){await page.locator('[data-mode="'+mode+'"]').click();assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),mode+' overflow at '+width);}}
  await page.locator('[data-mode="campus"]').click();await page.emulateMedia({reducedMotion:'reduce'});await page.waitForFunction(()=>BacCampus.inspect().motion===false);
  assert.deepEqual(errors,[]);
  console.log('PASS: persistent onboarding, persona editing, world hotspots/motion, actual backend task lifecycle, sandboxed HTML/download, memory after refresh, document sample, crew handoff/approval, campus and mission-control parity, scheduled cancellation, shared inputs/evidence export, deliberate retry, reset/memory preservation, security walkthrough versus host evidence, cohort routing, fallbacks, session isolation, CSRF, responsive layout, reduced motion. Test model: explicit fixture.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
