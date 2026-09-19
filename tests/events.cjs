// End-to-end event planning with a disposable runtime fixture; no real LLM or mail send.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),args:['--enable-unsafe-swiftshader']});
 try{
  const context=await browser.newContext({viewport:{width:1600,height:1100},acceptDownloads:true}),page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));await page.goto(process.env.BASE_URL||'http://127.0.0.1:8082');await page.waitForFunction(()=>BacStudio.inspect().runtime.testFixture);
  await page.locator('button[data-room=mission]').click();await page.locator('#studio-room-action').click();
  await page.locator('[data-event-template=zurich]').waitFor();assert.equal(await page.locator('[data-event-template]').count(),3);
  assert.equal(await page.locator('#studio-crew-form [name=city]').inputValue(),'Zurich');assert.equal(await page.locator('#studio-crew-form [name=spark],#studio-crew-form [name=common],#studio-crew-form [name=workstation]').count(),0);
  await page.waitForFunction(()=>document.getElementById('studio-event-preview').textContent.includes('3 / 6'));
  await page.locator('[data-event-template=austin]').click();await page.waitForFunction(()=>document.getElementById('studio-event-preview').textContent.includes('10 min'));
  assert.equal(await page.locator('#studio-crew-form [name=city]').inputValue(),'Austin');assert.match(await page.locator('#studio-event-preview').innerText(),/instead of 15/);
  await page.locator('[data-event-template=singapore]').click();await page.waitForFunction(()=>document.getElementById('studio-event-preview').textContent.includes('6 / 6'));assert.equal(await page.locator('#studio-crew-form [name=days]').inputValue(),'2');
  await page.locator('#studio-crew-form [name=attendees]').fill('3000');await page.locator('#studio-crew-form [name=duration]').fill('30');await page.locator('#studio-crew-form [name=days]').fill('1');
  await page.waitForFunction(()=>document.getElementById('studio-event-preview').textContent.includes('exceed'));assert(await page.locator('#studio-launch-event').isDisabled());
  await page.locator('[data-event-template=zurich]').click();await page.waitForFunction(()=>!document.getElementById('studio-launch-event').disabled);
  if(process.env.SCREENSHOT_DIR){await page.screenshot({path:path.join(process.env.SCREENSHOT_DIR,'event-templates.png')});}
  await page.locator('#studio-launch-event').click();await page.waitForFunction(()=>BacStudio.inspect().jobs[0]?.status==='done');
  const original=await page.evaluate(()=>BacStudio.inspect().jobs[0]);assert.equal(original.payload.brief.schema,2);assert.equal(original.payload.assignments.length,4);assert.equal(Object.keys(original.payload.handoffs).length,5);assert.equal(original.payload.capacity.boothCount,3);
  assert(await page.locator('#studio-event-package').isVisible());assert.equal(await page.locator('#studio-event-package table').first().locator('tbody tr').count(),3);
  const excelPromise=page.waitForEvent('download');await page.locator('[data-package-download$=".xlsx"]').click();const excel=await excelPromise;
  const output=process.env.ARTIFACT_DIR||'/tmp';fs.mkdirSync(output,{recursive:true});const excelPath=path.join(output,'event-fixture.xlsx');await excel.saveAs(excelPath);assert.equal(fs.readFileSync(excelPath).subarray(0,2).toString(),'PK');
  await page.locator('[data-package-tab=invitations]').click();assert.match(await page.locator('.event-mail-body').innerText(),/Hello \[First name\]/);assert.match(await page.locator('.event-invitation aside').innerText(),/fictional|unconfirmed/);
  const emlPromise=page.waitForEvent('download');await page.locator('[data-package-download$=".eml"]').click();const eml=await emlPromise;await eml.saveAs(path.join(output,'event-fixture.eml'));assert.match(fs.readFileSync(path.join(output,'event-fixture.eml'),'utf8'),/X-Unsent: 1/);
  await page.locator('[data-package-tab=audience]').click();const popup=context.waitForEvent('page');await page.getByRole('link',{name:'Try the survey'}).click();const survey=await popup;survey.on('pageerror',e=>errors.push(e.message));await survey.waitForLoadState();
  await survey.locator('#topic').selectOption('agents');await survey.locator('#experience').selectOption('some');await survey.locator('#rating').selectOption('5');await survey.getByRole('button').click();await survey.waitForFunction(()=>document.getElementById('notice').textContent.includes('saved'));
  await survey.locator('#topic').selectOption('cudax');await survey.getByRole('button').click();await survey.waitForFunction(()=>!document.querySelector('button').disabled);await survey.close();
  await page.locator('[data-survey-action=refresh]').click();await page.waitForFunction(()=>document.querySelector('.event-survey').textContent.includes('1 response'));
  assert.match(await page.locator('.event-vote').last().innerText(),/CUDA-X agents\s*1/);
  if(process.env.SCREENSHOT_DIR){await page.evaluate(()=>document.getElementById('studio-event-package').scrollIntoView({block:'start'}));await page.screenshot({path:path.join(process.env.SCREENSHOT_DIR,'event-audience-feedback.png')});}
  const stranger=await browser.newContext();await stranger.request.get('http://127.0.0.1:8082/api/session');assert.equal((await stranger.request.get('http://127.0.0.1:8082/api/survey-report?id='+original.id)).status(),404);await stranger.close();
  await page.locator('[data-survey-action=replan]').click();await page.waitForFunction(id=>BacStudio.inspect().jobs[0]?.id!==id&&BacStudio.inspect().jobs[0]?.status==='done',original.id);
  const next=await page.evaluate(()=>BacStudio.inspect().jobs[0]);assert.deepEqual(next.payload.brief.topicWeights,[0,0,1]);assert.equal(next.payload.brief.attendees,120);assert.equal(next.payload.capacity.boothCount,2);assert.equal((await page.evaluate(()=>BacStudio.inspect().jobs)).length,2);
  await page.locator('button[data-room=lounge]').click();assert(!(await page.locator('#studio-event-package').isVisible()));await page.locator('button[data-room=mission]').click();assert(await page.locator('#studio-event-package').isVisible());
  for(const width of [736,390]){
   await page.setViewportSize({width,height:950});assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),'Package overflow');
   await page.locator('#studio-room-action').click();await page.locator('[data-event-template=zurich]').waitFor();assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),'Brief overflow');
   await page.locator('#studio-dialog-close').click();
  }
  assert.deepEqual(errors,[]);console.log('PASS: three templates, constrained live calculation, sequential specialist handoffs, XLSX/EML downloads, readable invitation, real anonymous survey, deduplication, owner isolation, feedback-driven new plan, mobile layout.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
