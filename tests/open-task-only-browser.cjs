// Real UI with isolated data and simulated model connections. No paid inference.
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const server=spawn('python3',['-B','tests/fixture_personal_models.py'],{env:{...process.env,BAC_TEST_PORT:'18276'},stdio:['ignore','pipe','pipe']});let browser;
 server.stderr.on('data',()=>{});
 try{
  await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('Fixture timeout')),15000);server.stdout.on('data',b=>{if(b.toString().includes('READY')){clearTimeout(t);resolve();}});server.once('exit',()=>{clearTimeout(t);reject(Error('Fixture exited'));});});
  browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1600,height:1050},reducedMotion:'reduce'}),errors=[],requests=[];
  page.setDefaultTimeout(15000);
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
  await page.addInitScript(()=>sessionStorage.setItem('bac-stage3-scenario','event-brief'));
  await page.goto('http://127.0.0.1:18276');await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.personalModels);
  assert.equal(await page.locator('.world-room-map [data-world-scenario]').count(),1);
  await page.locator('.world-room-map [data-world-scenario=plan]').click();
  await page.waitForFunction(()=>BacCampus.inspect().navigation.activeScenario==='plan'&&!BacCampus.inspect().navigation.travelling);
  assert.equal(await page.locator('#studio-crew-name').innerText(),'Casey');
  assert.equal(await page.locator('[data-world-scenario=event-brief]').count(),0);
  await page.locator('#studio-config').click();
  await page.locator('#studio-route-plan').waitFor({state:'visible'});
  assert.equal(await page.locator('#studio-route-event-brief').count(),0);
  await page.getByRole('tab',{name:'Reset',exact:true}).click();
  assert.equal(await page.locator('#studio-settings-event-reset').count(),0);
  assert.match(await page.locator('#studio-dialog').innerText(),/Open Task/);
  await page.keyboard.press('Escape');
  await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.personalModels);
  await page.locator('.world-room-map [data-world-scenario=plan]').focus();
  await page.keyboard.press('Enter');
  await page.waitForFunction(()=>BacCampus.inspect().navigation.activeScenario==='plan'&&!BacCampus.inspect().navigation.overview&&!BacCampus.inspect().navigation.travelling);
  assert.equal(await page.locator('#studio-crew-name').innerText(),'Casey');
  assert(!requests.some(u=>/\/api\/(prepare-demo|event-plan|event-catalog|survey)/.test(u)), 'No retired background workflow requests');
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'/tmp/bac-open-task-only.png'});
  console.log('PASS: old saved selection, single Stage 03 map, direct navigation and keyboard entry, model/reset settings, reload, no Event Brief preparation. Actual UI; fixture connections.');
 }finally{await browser?.close();server.kill('SIGTERM');}
})().catch(e=>{console.error(e);process.exitCode=1;});
