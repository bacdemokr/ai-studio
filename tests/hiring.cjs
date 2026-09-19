// Disposable fixture: checks saved preferences and authored previews, not model quality.
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1100}}),errors=[],jobs=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/api/jobs'))jobs.push(r.url());});
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8082');await page.waitForFunction(()=>BacStudio.inspect().runtime.testFixture);
  assert.match(await page.locator('button[data-room=workshop]').innerText(),/Hiring/);
  assert.match(await page.locator('[data-persona=analyst]').innerText(),/Researcher/);
  assert.match(await page.locator('#studio-skill-picker').innerText(),/Build small apps/);
  await page.locator('#studio-name').fill('Sage');await page.locator('[data-persona=analyst]').click();
  const previews=[];
  for(const tone of ['kind','direct','playful','cynical']){
   await page.locator('[data-tone='+tone+']').click();
   assert.equal(await page.locator('[data-tone='+tone+']').getAttribute('aria-pressed'),'true');
   previews.push(await page.locator('#studio-voice-preview').innerText());
  }
  assert.equal(new Set(previews).size,4);
  await page.locator('#studio-verbosity').selectOption('brief');const brief=await page.locator('#studio-voice-preview').innerText();
  await page.locator('#studio-verbosity').selectOption('verbose');const verbose=await page.locator('#studio-voice-preview').innerText();
  assert(verbose.length>brief.length+100);assert.match(verbose,/evidence|sources/);
  assert.equal(await page.evaluate(()=>BacCampus.inspect().draft.tone),'cynical');
  await page.locator('#studio-create').click();await page.waitForFunction(()=>BacStudio.inspect().room==='lounge');
  assert.equal(await page.evaluate(()=>BacStudio.inspect().profile.tone),'cynical');
  assert.equal(await page.evaluate(()=>BacStudio.inspect().profile.verbosity),'verbose');
  assert.match(await page.locator('#studio-personality').innerText(),/Researcher · Cynical · Detailed/);
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);await page.mouse.move(1,1);
  await page.waitForFunction(()=>BacCampus.inspect().residents.some(r=>r.speech),null,{timeout:20000});
  assert.match(await page.evaluate(()=>BacCampus.inspect().residents[0].speech),/source|confident chart/i);
  await page.reload();await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Sage');
  await page.locator('#studio-edit-agent').click();
  assert.equal(await page.locator('[data-tone=cynical]').getAttribute('aria-pressed'),'true');
  assert.equal(await page.locator('#studio-verbosity').inputValue(),'verbose');
  // Editing the voice updates this resident without creating another identity or mission.
  await page.locator('[data-tone=playful]').click();await page.locator('#studio-verbosity').selectOption('brief');await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.tone==='playful'&&BacStudio.inspect().room==='lounge');
  assert.equal((await page.evaluate(()=>BacStudio.inspect().agents)).length,1);
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);await page.mouse.move(1,1);
  await page.waitForFunction(()=>BacCampus.inspect().residents[0].speech,null,{timeout:20000});
  assert.match(await page.evaluate(()=>BacCampus.inspect().residents[0].speech),/rumors|magnifying glass/);
  await page.locator('#studio-edit-agent').click();await page.locator('[data-tone=cynical]').click();await page.locator('#studio-verbosity').selectOption('balanced');
  await page.locator('#studio-room-heading').scrollIntoViewIfNeeded();
  await page.locator('.studio-voice-preview').scrollIntoViewIfNeeded();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  if(await page.locator('#studio-alert').isVisible())await page.locator('#studio-alert button').click();
  await page.locator('[data-persona=guide]').evaluate(button=>{const panel=document.getElementById('studio-workshop');panel.scrollTop+=button.closest('fieldset').getBoundingClientRect().top-panel.getBoundingClientRect().top-24;});
  if(process.env.SCREENSHOT_PATH)await page.screenshot({path:process.env.SCREENSHOT_PATH});
  for(const width of [1024,736,390]){
   await page.setViewportSize({width,height:950});
   for(const control of ['[data-persona=analyst]','[data-tone=cynical]','#studio-verbosity','#studio-create']){
    await page.locator(control).scrollIntoViewIfNeeded();
    assert(await page.locator(control).isVisible());
   }
   assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),'Hiring page horizontal overflow at '+width);
  }
  assert.deepEqual(jobs,[]);assert.deepEqual(errors,[]);
  console.log('PASS: Hiring copy, independent role/tone/length controls, live style preview, saved and reloaded voice, edit in place, tone-based ambient speech, mobile layout, no model jobs.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
