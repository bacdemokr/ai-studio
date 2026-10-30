// Real HTTP fixture: current Hiring flow, saved identity and edit/reload behavior.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[],jobs=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/api/jobs'))jobs.push(r.url());});
  await page.goto(process.env.BAC_TEST_URL||process.env.BASE_URL||'http://127.0.0.1:8082');await page.waitForFunction(()=>BacStudio.inspect().runtime.testFixture);
  await page.locator('.world-room-map [data-world-room=workshop]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  assert.equal(await page.locator('#studio-tone-prompt').inputValue(),'Kind (Warm & encouraging)');
  assert.match(await page.locator('#studio-purpose').inputValue(),/^Check current weather/);
  assert.equal(await page.locator('#studio-apply-prompt').innerText(),'Suggest skills');
  assert.deepEqual(await page.locator('#studio-skill-picker input:checked').evaluateAll(xs=>xs.map(x=>x.value)),['weather']);
  assert.equal(await page.locator('#studio-accessory').inputValue(),'none');
  for(const [body,name] of [['classic','Jinny'],['round','Orbit'],['fox-companion','Rusty'],['operative','Smith'],['claw','Pixel'],['crab','Sage'],['cat','Mochi'],['bunny','Pip'],['panda','Bao']]){
   await page.locator('#studio-body-picker [data-body='+body+']').click();assert.equal(await page.locator('#studio-name').inputValue(),name);
  }
  await page.locator('#studio-name').fill('');
  await page.locator('#studio-body-picker [data-body=classic]').click();
  assert.equal(await page.locator('#studio-name').inputValue(),'');
  await page.locator('#studio-name').fill('Sage');
  for(const body of ['round','crab','claw']){
   await page.locator('#studio-body-picker [data-body='+body+']').click();
   assert.equal(await page.locator('#studio-name').inputValue(),'Sage');
  }
  await page.waitForTimeout(1800);
  assert.equal(await page.locator('#studio-name').inputValue(),'Sage');
await page.locator('[data-tone=cynical]').click();await page.locator('[data-role-template="2"]').click();
  assert.equal(await page.locator('#studio-tone-prompt').inputValue(),'Cynical (Dry humor & skepticism)');
  assert.match(await page.locator('#studio-purpose').inputValue(),/three relevant arXiv papers/);
  assert.deepEqual(await page.locator('#studio-skill-picker input:checked').evaluateAll(xs=>xs.map(x=>x.value)),['web']);
  await page.locator('#studio-tone-prompt').fill('Dry, curious and concise.');
  await page.getByRole('button',{name:'Web researcher',exact:true}).click();
  assert.equal(await page.locator('#studio-tone-prompt').inputValue(),'Dry, curious and concise.','Role preset preserves custom tone');
  await page.locator('#studio-tone-prompt').fill('Use weather metaphors and research jokes when discussing coding.');
  await page.locator('#studio-purpose').fill('Help me think through everyday decisions.');
  await page.locator('#studio-apply-prompt').click();
  assert.equal(await page.locator('#studio-skill-picker input:checked').count(),0,'Tone words must not suggest task skills');
  await page.locator('#studio-purpose').fill('Compare papers and summarize documents with evidence.');
  await page.locator('#studio-apply-prompt').click();
  assert.deepEqual(await page.locator('#studio-skill-picker input:checked').evaluateAll(xs=>xs.map(x=>x.value).sort()),['documents','web']);
  // Final edits save directly, without applying or suggesting again. Literal labels are ordinary text.
  const tone='Dry, curious and concise.\n한국어로 짧게 답해줘.',role='Compare papers and summarize documents with evidence.\nUse headings such as Tone: and Role: when relevant.';
  await page.locator('#studio-tone-prompt').fill(tone);await page.locator('#studio-purpose').fill(role);
  assert.equal(await page.evaluate(()=>BacStudio.inspect().agents.length),0,'Suggestions must not save the agent');
  await page.route('**/api/onboard',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Fixture save failed'})}),{times:1});
  await page.locator('#studio-create').click();
  await page.waitForFunction(()=>document.querySelector('#studio-alert')?.textContent.includes('Fixture save failed'));
  await page.locator('#studio-body-picker [data-body=round]').click();
  assert.equal(await page.locator('#studio-name').inputValue(),'Sage');
  await page.locator('#studio-body-picker [data-body=claw]').click();
  await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Sage'&&BacStudio.inspect().room==='lounge'&&!BacCampus.inspect().arrival,{},{timeout:20000});
  const original=await page.evaluate(()=>BacStudio.inspect().profile);
  assert.equal(original.tonePrompt,tone);assert.equal(original.purpose,role);assert.equal(original.avatar.body,'claw');
  await page.locator('#studio-edit-agent').click();await page.locator('#studio-name').fill('Sage edited');await page.locator('#studio-body-picker [data-body=round]').click();assert.equal(await page.locator('#studio-name').inputValue(),'Sage edited');
  const editedTone='Warm and concise.\nKeep technical terms in English.',editedRole='Compare supplied documents and explain the differences.';
  await page.locator('#studio-tone-prompt').fill(editedTone);await page.locator('#studio-purpose').fill(editedRole);await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Sage edited');
  assert.equal(await page.evaluate(()=>BacStudio.inspect().agents.length),1);
  await page.reload();await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Sage edited');await page.locator('.world-room-map [data-world-room=lounge]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);await page.locator('#studio-edit-agent').click();
  assert.equal(await page.locator('#studio-tone-prompt').inputValue(),editedTone);
  assert.equal(await page.locator('#studio-purpose').inputValue(),editedRole);
  if(process.env.BAC_TEST_ARTIFACT_DIR){await page.locator('.studio-customize').scrollIntoViewIfNeeded();await page.locator('.studio-customize').screenshot({path:process.env.BAC_TEST_ARTIFACT_DIR+'/tone-role.png'});}
  for(const width of [1600,1280,1024]){
   await page.setViewportSize({width,height:950});
   for(const control of ['#studio-tone-prompt','#studio-purpose','#studio-create']){await page.locator(control).scrollIntoViewIfNeeded();assert(await page.locator(control).isVisible());}
   assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),'Hiring overflow at '+width);
  }
  await page.locator('#studio-tone-prompt').fill('Unsaved tone');await page.locator('#studio-purpose').fill('Unsaved role');
  await page.locator('#studio-cancel-create').click();await page.locator('#studio-edit-agent').click();
  assert.equal(await page.locator('#studio-tone-prompt').inputValue(),editedTone);assert.equal(await page.locator('#studio-purpose').inputValue(),editedRole);
  await page.locator('#studio-cancel-create').click();
  await page.locator('.world-room-map [data-world-room=workshop]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('#studio-body-picker [data-body=classic]').click();
  assert.equal(await page.locator('#studio-name').inputValue(),'Jinny');
  assert.deepEqual(jobs,[]);assert.deepEqual(errors,[]);
  console.log('PASS: default, templates, custom tone/role, manual skills, distinct avatar, edit in place, reload persistence, responsive Hiring and no model jobs.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
