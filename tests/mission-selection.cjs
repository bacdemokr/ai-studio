// Message templates prepare an editable draft without submitting a model job.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[],jobs=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/api/jobs'))jobs.push(r.url());});
  await page.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8082');await page.waitForFunction(()=>BacStudio.inspect().runtime.testFixture);
  await page.locator('.world-room-map [data-world-room=workshop]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('#studio-name').fill('Template tester');await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().room==='lounge'&&!BacCampus.inspect().navigation.travelling);
  const owner=await page.evaluate(()=>BacStudio.inspect().agentId);
  assert.equal(await page.locator('#studio-equipped [data-try-skill]').count(),1);
  await page.locator('[data-try-skill=weather]').click();assert.match(await page.locator('#studio-prompt').inputValue(),/weather/i);
  assert.deepEqual(jobs,[]);assert.equal(await page.evaluate(()=>BacStudio.inspect().jobs.length),0);
  await page.locator('#studio-edit-agent').click();await page.locator('#studio-skill-picker input[value=writer]').check();await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile.skills.includes('writer')&&!document.querySelector('#studio-passport').hidden);
  assert.equal(await page.evaluate(()=>BacStudio.inspect().agentId),owner);
  await page.locator('[data-try-skill=writer]').click();assert.match(await page.locator('#studio-prompt').inputValue(),/invit|draft|message/i);
  await page.locator('#studio-prompt').fill('My own revision');assert.equal(await page.locator('#studio-prompt').inputValue(),'My own revision');
  assert.deepEqual(jobs,[]);assert.deepEqual(errors,[]);
  console.log('PASS: equipped skill templates, editable drafts, adding a skill in place, same identity and no automatic model requests.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
