// Real HTTP fixture: current Hiring flow, saved identity and edit/reload behavior.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[],jobs=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/api/jobs'))jobs.push(r.url());});
  await page.goto(process.env.BAC_TEST_URL||process.env.BASE_URL||'http://127.0.0.1:8082');await page.waitForFunction(()=>BacStudio.inspect().runtime.testFixture);
  await page.locator('.world-room-map [data-world-room=workshop]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  assert.match(await page.locator('#studio-purpose').inputValue(),/Tone:.*Kind[\s\S]*Role:.*weather/);
  assert.deepEqual(await page.locator('#studio-skill-picker input:checked').evaluateAll(xs=>xs.map(x=>x.value)),['weather']);
  assert.equal(await page.locator('#studio-accessory').inputValue(),'none');
  for(const [body,name] of [['classic','Jinny'],['round','Orbit'],['rover','Scout'],['operative','Smith'],['claw','Pixel'],['crab','Sage']]){
   await page.locator('#studio-body-picker [data-body='+body+']').click();assert.equal(await page.locator('#studio-name').inputValue(),name);
  }
  await page.locator('#studio-body-picker [data-body=claw]').click();await page.locator('#studio-name').fill('Sage');await page.locator('[data-tone=cynical]').click();await page.locator('[data-role-template="2"]').click();
  assert.match(await page.locator('#studio-purpose').inputValue(),/Tone: Cynical[\s\S]*Role: .*three relevant arXiv papers/);
  assert.deepEqual(await page.locator('#studio-skill-picker input:checked').evaluateAll(xs=>xs.map(x=>x.value)),['web']);
  await page.locator('#studio-purpose').fill('Tone: Dry, curious and concise.\nRole: Compare papers and summarize documents with evidence.');
  await page.locator('#studio-apply-prompt').click();
  assert.deepEqual(await page.locator('#studio-skill-picker input:checked').evaluateAll(xs=>xs.map(x=>x.value).sort()),['documents','web']);
  await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Sage'&&BacStudio.inspect().room==='lounge'&&!BacCampus.inspect().arrival,{},{timeout:20000});
  const original=await page.evaluate(()=>BacStudio.inspect().profile);
  assert.equal(original.tonePrompt,'Dry, curious and concise.');assert.equal(original.avatar.body,'claw');
  await page.locator('#studio-edit-agent').click();await page.locator('#studio-name').fill('Sage edited');await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Sage edited');
  assert.equal(await page.evaluate(()=>BacStudio.inspect().agents.length),1);
  await page.reload();await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Sage edited');await page.locator('.world-room-map [data-world-room=lounge]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);await page.locator('#studio-edit-agent').click();
  assert.equal(await page.locator('#studio-purpose').inputValue(),'- Tone: Dry, curious and concise.\n- Role: Compare papers and summarize documents with evidence.');
  for(const width of [1024,736,390]){
   await page.setViewportSize({width,height:950});
   for(const control of ['#studio-purpose','#studio-create']){await page.locator(control).scrollIntoViewIfNeeded();assert(await page.locator(control).isVisible());}
   assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),'Hiring overflow at '+width);
  }
  assert.deepEqual(jobs,[]);assert.deepEqual(errors,[]);
  console.log('PASS: default, templates, custom tone/role, manual skills, distinct avatar, edit in place, reload persistence, responsive Hiring and no model jobs.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
