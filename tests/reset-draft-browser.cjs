// Isolated visitor fixture: a slow reset must not accept and then erase a new draft.
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const port=Number(process.env.BAC_TEST_PORT||18445),server=spawn('python3',['-B','tests/fixture_visitor_teams.py'],{env:{...process.env,BAC_TEST_PORT:String(port)},stdio:['ignore','pipe','inherit']});let browser,release;
 try{
  await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Fixture timeout')),15000);server.stdout.on('data',b=>{if(b.toString().includes('VISITOR FIXTURE READY')){clearTimeout(timer);resolve();}});server.once('exit',()=>reject(Error('Fixture exited')));});
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1600,height:1050},reducedMotion:'reduce'}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+port);await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
  await page.locator('.world-room-map [data-world-scenario=plan]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('#studio-crew-team-mode [data-team-mode=mixed]').click();
  await page.locator('#studio-crew-prompt').fill('/goal Build a counter.');await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>document.querySelector('#studio-crew-conversation').textContent.includes('The team delivered the counter.'));
  for(const fail of [true,false]){
   const draft='/goal Keep this draft if reset fails.';await page.locator('#studio-crew-prompt').fill(draft);
   let started;const ready=new Promise(r=>started=r),gate=new Promise(r=>release=r);
   await page.route('**/api/bac-reset',async route=>{started();await gate;if(fail)await route.fulfill({status:503,json:{error:'Fixture reset unavailable'}});else await route.continue();},{times:1});
   await page.locator('#studio-bac-reset').click();await page.locator('#studio-team-reset-confirm').click();await ready;
   assert(await page.locator('#studio-crew-prompt').isDisabled(),'Reset acknowledgement pending: new typing would be erased');
   assert(await page.locator('#studio-crew-team-mode button').first().isDisabled(),'Pending reset must lock team selection');
   assert(await page.locator('#studio-crew-document-add').isDisabled(),'Pending reset must lock uploads');
   release();await page.waitForFunction(()=>!document.querySelector('#studio-crew-prompt').disabled);
   if(fail){assert.equal(await page.locator('#studio-crew-prompt').inputValue(),draft);assert.match(await page.locator('#studio-team-reset-status').innerText(),/Fixture reset unavailable/);}
   else{
    assert.equal(await page.locator('#studio-crew-prompt').inputValue(),'/goal ');
    assert.equal(await page.locator('#studio-crew-team-mode [aria-pressed=true]').getAttribute('data-team-mode'),'hired');
    await page.locator('#studio-crew-prompt').fill('/goal New draft after reset.');
    await page.evaluate(()=>BacStudio.refresh());assert.equal(await page.locator('#studio-crew-prompt').inputValue(),'/goal New draft after reset.');
   }
  }
  assert.deepEqual(errors,[]);console.log('PASS: reset locks composer/mode/upload before server acknowledgement; failure preserves draft; completion clears once and new draft survives polling.');
 }finally{release?.();if(browser)await browser.close();server.kill('SIGTERM');}
})().catch(e=>{console.error(e);process.exitCode=1;});
